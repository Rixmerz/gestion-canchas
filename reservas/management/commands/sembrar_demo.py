"""
Carga un recinto de demostración: usuarios de los dos perfiles, canchas y un
escenario de reservas relativo al momento actual.

    python manage.py sembrar_demo

Es idempotente: se puede volver a ejecutar sin duplicar nada.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from reservas import reglas
from reservas.models import Cancha, Falta, Reserva, Usuario
from reservas.permisos import NOMBRE_GRUPO, crear_grupo_administradores

CANCHAS = [
    ("Cancha 1 — Techada", Cancha.Tipo.FUTBOL_7, "Pasto sintético", 45000, True),
    ("Cancha 2 — Norte", Cancha.Tipo.FUTBOL_7, "Pasto sintético", 40000, True),
    ("Cancha 3 — Baby", Cancha.Tipo.BABY, "Cemento pulido", 28000, True),
    ("Cancha 4 — En mantención", Cancha.Tipo.FUTBOL_11, "Pasto natural", 90000, False),
]

CLIENTES = [
    ("cmunoz", "Carlos", "Muñoz", "carlos.munoz@example.cl", "+56 9 8123 4567"),
    ("drojas", "Daniela", "Rojas", "daniela.rojas@example.cl", "+56 9 7654 3210"),
    ("ivera", "Ignacio", "Vera", "ignacio.vera@example.cl", "+56 9 5544 3322"),
    ("pcardenas", "Paulina", "Cárdenas", "p.cardenas@example.cl", "+56 9 6677 8899"),
]

CLAVE = "canchas2026"


class Command(BaseCommand):
    help = "Crea usuarios, canchas y un escenario de reservas para demostrar el MVP."

    @transaction.atomic
    def handle(self, *args, **opciones):
        grupo = crear_grupo_administradores()

        superusuario, creado = Usuario.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "Super",
                "last_name": "Usuario",
                "email": "admin@example.cl",
                "rol": Usuario.Rol.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if creado:
            superusuario.set_password(CLAVE)
            superusuario.save()

        # M-05: administrador normal — accede al admin sin ser superusuario.
        encargado, creado = Usuario.objects.get_or_create(
            username="encargado",
            defaults={
                "first_name": "Marcela",
                "last_name": "Pinto",
                "email": "encargado@example.cl",
                "rol": Usuario.Rol.ADMIN,
                "is_staff": True,
                "is_superuser": False,
            },
        )
        if creado:
            encargado.set_password(CLAVE)
            encargado.save()
        encargado.groups.add(grupo)

        for nombre, tipo, superficie, precio, activa in CANCHAS:
            Cancha.objects.update_or_create(
                nombre=nombre,
                defaults={
                    "tipo": tipo,
                    "superficie": superficie,
                    "precio_hora": precio,
                    "activa": activa,
                },
            )

        clientes = {}
        for username, nombre, apellido, correo, telefono in CLIENTES:
            cliente, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nombre,
                    "last_name": apellido,
                    "email": correo,
                    "telefono": telefono,
                    "rol": Usuario.Rol.CLIENTE,
                },
            )
            if creado:
                cliente.set_password(CLAVE)
                cliente.save()
            clientes[username] = cliente

        # Escenario limpio de reservas.
        Falta.objects.all().delete()
        Reserva.objects.all().delete()
        Usuario.objects.update(bloqueado=False, bloqueado_en=None)

        ahora = timezone.now()
        duracion = timedelta(minutes=60)

        def bloque(horas):
            inicio = timezone.localtime(ahora + timedelta(hours=horas)).replace(
                minute=0, second=0, microsecond=0
            )
            return inicio, reglas.sumar(inicio, duracion)

        canchas = {c.nombre: c for c in Cancha.objects.all()}

        # 1) Reserva real, ya pagada y confirmada por el encargado.
        inicio, fin = bloque(4)
        Reserva.objects.create(
            cancha=canchas["Cancha 1 — Techada"],
            cliente=clientes["drojas"],
            inicio=inicio,
            fin=fin,
            estado=Reserva.Estado.PAGADA,
            precio=45000,
            creada_en=ahora - timedelta(hours=3),
            vence_en=ahora - timedelta(hours=3) + reglas.VENTANA_DE_PAGO,
            pagada_en=ahora - timedelta(hours=2, minutes=50),
            confirmada_por=encargado,
        )

        # 2) Solicitud viva: la ventana de pago está corriendo.
        inicio, fin = bloque(6)
        Reserva.objects.create(
            cancha=canchas["Cancha 2 — Norte"],
            cliente=clientes["cmunoz"],
            inicio=inicio,
            fin=fin,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            precio=40000,
            creada_en=ahora - timedelta(minutes=5),
            vence_en=reglas.calcular_vence_en(ahora - timedelta(minutes=5), inicio),
        )

        # 3) Ignacio Vera: 9 faltas. Una más y queda bloqueado (RN-05).
        ignacio = clientes["ivera"]
        for numero in range(9):
            momento = timezone.localtime(ahora - timedelta(days=numero + 1)).replace(
                hour=21, minute=0, second=0, microsecond=0
            )
            reserva = Reserva.objects.create(
                cancha=canchas["Cancha 3 — Baby"],
                cliente=ignacio,
                inicio=momento,
                fin=reglas.sumar(momento, duracion),
                estado=Reserva.Estado.VENCIDA,
                precio=28000,
                creada_en=momento - timedelta(hours=2),
                vence_en=momento - timedelta(hours=1, minutes=30),
                vencida_en=momento - timedelta(hours=1, minutes=30),
            )
            Falta.objects.create(
                cliente=ignacio,
                reserva=reserva,
                motivo="No pagó dentro de la ventana de 30 minutos (RN-02).",
                registrada_en=momento - timedelta(hours=1, minutes=30),
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Escenario cargado.\n"
                f"  Superusuario      : admin / {CLAVE}\n"
                f"  Admin. de recinto : encargado / {CLAVE}  (grupo «{NOMBRE_GRUPO}», sin ser superusuario)\n"
                f"  Clientes          : cmunoz, drojas, ivera, pcardenas / {CLAVE}\n"
                "  Ignacio Vera (ivera) tiene 9 faltas: una más y queda bloqueado (RN-05)."
            )
        )
