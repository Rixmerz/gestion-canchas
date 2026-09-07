"""
Pruebas del MVP: una por criterio de aceptación (docs/01-problema-y-solucion.md §6).

    python manage.py test
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import reglas, servicios
from .models import Cancha, Falta, Reserva, Usuario
from .permisos import NOMBRE_GRUPO

CLAVE = "clave-de-prueba-3821"


class BaseDelRecinto(TestCase):
    """Un recinto con una cancha, un cliente y un administrador no superusuario."""

    def setUp(self):
        self.cancha = Cancha.objects.create(
            nombre="Cancha 1", tipo=Cancha.Tipo.FUTBOL_7, precio_hora=40000
        )
        self.cliente = Usuario.objects.create_user(
            username="cmunoz", password=CLAVE, first_name="Carlos", rol=Usuario.Rol.CLIENTE
        )
        self.otro_cliente = Usuario.objects.create_user(
            username="drojas", password=CLAVE, first_name="Daniela", rol=Usuario.Rol.CLIENTE
        )
        self.encargado = Usuario.objects.create_user(
            username="encargado", password=CLAVE, rol=Usuario.Rol.ADMIN, is_staff=True
        )
        self.encargado.groups.add(Group.objects.get(name=NOMBRE_GRUPO))

    def bloque(self, horas=3):
        """Un bloque en punto, `horas` más adelante."""
        inicio = timezone.localtime(timezone.now() + timedelta(hours=horas)).replace(
            minute=0, second=0, microsecond=0
        )
        return inicio

    def solicitar(self, cliente=None, horas=3, cancha=None):
        return servicios.solicitar_reserva(
            cliente or self.cliente, cancha or self.cancha, self.bloque(horas)
        )


class SolicitarReserva(BaseDelRecinto):
    """M-08: el cliente aparta el bloque, no lo reserva."""

    def test_un_anonimo_no_puede_solicitar(self):
        respuesta = self.client.post(
            reverse("reservas:solicitar"),
            {"cancha_id": self.cancha.pk, "inicio": self.bloque().isoformat()},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("reservas:login"), respuesta.url)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_el_cliente_autenticado_crea_una_solicitud_pendiente(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(
            reverse("reservas:solicitar"),
            {"cancha_id": self.cancha.pk, "inicio": self.bloque().isoformat(), "volver_a": "/"},
        )
        self.assertEqual(respuesta.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertEqual(reserva.cliente, self.cliente)
        self.assertEqual(reserva.precio, self.cancha.precio_hora)

    def test_el_bloque_dura_una_hora(self):
        reserva = self.solicitar()
        self.assertEqual(reglas.diferencia(reserva.fin, reserva.inicio), timedelta(hours=1))

    def test_un_administrador_no_solicita_canchas(self):
        with self.assertRaises(reglas.ReglaViolada):
            self.solicitar(cliente=self.encargado)

    def test_no_se_puede_solicitar_una_cancha_inactiva(self):
        self.cancha.activa = False
        self.cancha.save()
        with self.assertRaises(reglas.ReglaViolada):
            self.solicitar()


class AnticipacionMinima(BaseDelRecinto):
    """M-09 · RN-01."""

    def test_rechaza_a_menos_de_30_minutos(self):
        inicio = timezone.now() + timedelta(minutes=20)
        with self.assertRaises(reglas.ReglaViolada) as caso:
            servicios.solicitar_reserva(self.cliente, self.cancha, inicio)
        self.assertEqual(caso.exception.regla, "RN-01")
        self.assertEqual(Reserva.objects.count(), 0)

    def test_acepta_a_mas_de_30_minutos(self):
        inicio = timezone.now() + timedelta(minutes=45)
        reserva = servicios.solicitar_reserva(self.cliente, self.cancha, inicio)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)


class VentanaDePago(BaseDelRecinto):
    """M-10 · RN-02."""

    def test_la_ventana_dura_30_minutos_para_un_bloque_lejano(self):
        reserva = self.solicitar(horas=5)
        self.assertEqual(
            reglas.diferencia(reserva.vence_en, reserva.creada_en), reglas.VENTANA_DE_PAGO
        )

    def test_la_ventana_no_pasa_del_inicio_del_bloque(self):
        """
        En el límite de RN-01 la ventana de 30 minutos terminaría después del
        pitazo inicial, así que se recorta al inicio del bloque. El caso se
        prueba sobre la regla pura, porque exige un instante exacto que el
        reloj del servicio no puede reproducir.
        """
        creada = timezone.now()
        inicio = creada + reglas.ANTICIPACION_MINIMA
        self.assertEqual(
            reglas.en_utc(reglas.calcular_vence_en(creada, inicio)), reglas.en_utc(inicio)
        )

    def test_la_ventana_nunca_supera_el_inicio_del_bloque(self):
        for horas in (1, 3, 24):
            with self.subTest(horas=horas):
                reserva = self.solicitar(horas=horas)
                self.assertLessEqual(reglas.en_utc(reserva.vence_en), reglas.en_utc(reserva.inicio))
                servicios.cancelar_reserva(reserva)


class SinSolapamiento(BaseDelRecinto):
    """M-11 · RN-06: resuelve la sobreventa (P2)."""

    def test_dos_clientes_no_pueden_tomar_el_mismo_bloque(self):
        self.solicitar()
        with self.assertRaises(reglas.ReglaViolada) as caso:
            self.solicitar(cliente=self.otro_cliente)
        self.assertEqual(caso.exception.regla, "RN-06")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_el_bloque_siguiente_si_esta_disponible(self):
        self.solicitar(horas=3)
        self.solicitar(cliente=self.otro_cliente, horas=4)
        self.assertEqual(Reserva.objects.vigentes().count(), 2)

    def test_una_reserva_cancelada_libera_el_bloque(self):
        reserva = self.solicitar()
        servicios.cancelar_reserva(reserva)
        self.solicitar(cliente=self.otro_cliente)
        self.assertEqual(Reserva.objects.vigentes().count(), 1)

    def test_la_base_de_datos_tambien_impide_el_duplicado(self):
        """La restricción única cubre la carrera que el servicio no alcanza a ver."""
        from django.db import IntegrityError, transaction

        reserva = self.solicitar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reserva.objects.create(
                cancha=self.cancha,
                cliente=self.otro_cliente,
                inicio=reserva.inicio,
                fin=reserva.fin,
                estado=Reserva.Estado.PENDIENTE_PAGO,
                precio=1000,
                vence_en=reserva.vence_en,
            )


class ConfirmacionDelPago(BaseDelRecinto):
    """M-12 · RN-03: solicitar no es reservar."""

    def test_el_administrador_confirma_y_queda_la_trazabilidad(self):
        reserva = self.solicitar()
        servicios.confirmar_pago(reserva, self.encargado)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.confirmada_por, self.encargado)
        self.assertIsNotNone(reserva.pagada_en)

    def test_un_cliente_no_puede_confirmar_su_propio_pago(self):
        reserva = self.solicitar()
        with self.assertRaises(reglas.ReglaViolada) as caso:
            servicios.confirmar_pago(reserva, self.cliente)
        self.assertEqual(caso.exception.regla, "RN-03")

    def test_la_reserva_pagada_ya_no_vence(self):
        reserva = self.solicitar()
        servicios.confirmar_pago(reserva, self.encargado)
        Reserva.objects.filter(pk=reserva.pk).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(servicios.vencer_reservas_pendientes(), 0)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(Falta.objects.count(), 0)

    def test_no_se_confirma_una_reserva_ya_vencida(self):
        reserva = self.solicitar()
        Reserva.objects.filter(pk=reserva.pk).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        reserva.refresh_from_db()
        with self.assertRaises(reglas.ReglaViolada) as caso:
            servicios.confirmar_pago(reserva, self.encargado)
        self.assertEqual(caso.exception.regla, "RN-02")


class VencimientoYFaltas(BaseDelRecinto):
    """M-13 · RN-04: resuelve las reservas fantasma (P3)."""

    def vencer(self, reserva):
        Reserva.objects.filter(pk=reserva.pk).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        return servicios.vencer_reservas_pendientes()

    def test_la_reserva_no_pagada_vence_y_genera_una_falta(self):
        reserva = self.solicitar()
        self.assertEqual(self.vencer(reserva), 1)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.VENCIDA)
        self.assertIsNotNone(reserva.vencida_en)
        self.assertEqual(Falta.objects.filter(cliente=self.cliente).count(), 1)

    def test_el_bloque_vencido_vuelve_a_estar_disponible(self):
        reserva = self.solicitar()
        self.vencer(reserva)
        nueva = self.solicitar(cliente=self.otro_cliente)
        self.assertEqual(nueva.estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_barrer_dos_veces_no_duplica_la_falta(self):
        reserva = self.solicitar()
        self.vencer(reserva)
        servicios.vencer_reservas_pendientes()
        self.assertEqual(Falta.objects.count(), 1)

    def test_el_comando_de_consola_hace_el_barrido(self):
        from io import StringIO

        from django.core.management import call_command

        reserva = self.solicitar()
        Reserva.objects.filter(pk=reserva.pk).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        salida = StringIO()
        call_command("vencer_reservas", stdout=salida)
        self.assertIn("1 reserva", salida.getvalue())
        self.assertEqual(Falta.objects.count(), 1)


class BloqueoPorFaltas(BaseDelRecinto):
    """M-15 · RN-05."""

    def acumular_faltas(self, cantidad, cliente=None):
        cliente = cliente or self.cliente
        for numero in range(cantidad):
            momento = timezone.now() - timedelta(days=numero + 1)
            reserva = Reserva.objects.create(
                cancha=self.cancha,
                cliente=cliente,
                inicio=momento,
                fin=momento + timedelta(hours=1),
                estado=Reserva.Estado.VENCIDA,
                precio=1000,
                vence_en=momento,
                vencida_en=momento,
            )
            Falta.objects.create(cliente=cliente, reserva=reserva, motivo="prueba")

    def test_con_nueve_faltas_todavia_puede_reservar(self):
        self.acumular_faltas(9)
        servicios.evaluar_bloqueo(self.cliente)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.bloqueado)
        self.assertEqual(self.solicitar().estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_la_decima_falta_bloquea_automaticamente(self):
        self.acumular_faltas(9)
        reserva = self.solicitar()
        Reserva.objects.filter(pk=reserva.pk).update(
            vence_en=timezone.now() - timedelta(minutes=1)
        )
        servicios.vencer_reservas_pendientes()

        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.faltas_vigentes(), 10)
        self.assertTrue(self.cliente.bloqueado)
        self.assertIsNotNone(self.cliente.bloqueado_en)

    def test_el_cliente_bloqueado_no_puede_solicitar(self):
        self.acumular_faltas(10)
        servicios.evaluar_bloqueo(self.cliente)
        with self.assertRaises(reglas.ReglaViolada) as caso:
            self.solicitar()
        self.assertEqual(caso.exception.regla, "RN-05")

    def test_el_desbloqueo_anula_las_faltas_para_que_no_se_repita(self):
        self.acumular_faltas(10)
        servicios.evaluar_bloqueo(self.cliente)
        servicios.desbloquear(self.cliente)

        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.bloqueado)
        self.assertEqual(self.cliente.faltas_vigentes(), 0)
        self.assertEqual(self.cliente.faltas.count(), 10, "las faltas se conservan como historial")
        # Un barrido posterior no lo vuelve a bloquear.
        servicios.vencer_reservas_pendientes()
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.bloqueado)


class RolesYAcceso(BaseDelRecinto):
    """M-03, M-04, M-05, M-14: quién ve y hace qué."""

    def test_el_cliente_no_entra_al_panel_de_faltas(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("reservas:faltas")).status_code, 403)

    def test_el_administrador_ve_el_panel_de_faltas(self):
        self.client.force_login(self.encargado)
        self.assertEqual(self.client.get(reverse("reservas:faltas")).status_code, 200)

    def test_el_administrador_no_superusuario_entra_al_django_admin(self):
        self.assertFalse(self.encargado.is_superuser)
        self.assertTrue(self.encargado.is_staff)
        self.client.force_login(self.encargado)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/admin/reservas/reserva/").status_code, 200)
        self.assertEqual(self.client.get("/admin/reservas/falta/").status_code, 200)

    def test_el_cliente_no_entra_al_django_admin(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get("/admin/", follow=True)
        self.assertNotEqual(respuesta.status_code, 200 if respuesta.redirect_chain == [] else 0)
        self.assertContains(respuesta, "Iniciar sesión", status_code=200)

    def test_el_cliente_solo_ve_sus_propias_reservas(self):
        mia = self.solicitar()
        ajena = self.solicitar(cliente=self.otro_cliente, horas=5)
        self.client.force_login(self.cliente)
        contenido = self.client.get(reverse("reservas:mis_reservas")).content.decode()
        self.assertIn(f">{mia.pk}<", contenido)
        self.assertNotIn(f">{ajena.pk}<", contenido)

    def test_el_registro_crea_siempre_un_cliente(self):
        respuesta = self.client.post(
            reverse("reservas:registro"),
            {
                "username": "nuevo",
                "first_name": "Ana",
                "last_name": "Soto",
                "email": "ana@example.cl",
                "password1": "UnaClaveLarga2026",
                "password2": "UnaClaveLarga2026",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        nuevo = Usuario.objects.get(username="nuevo")
        self.assertEqual(nuevo.rol, Usuario.Rol.CLIENTE)
        self.assertFalse(nuevo.is_staff)
        self.assertFalse(nuevo.is_superuser)


class VistaDeFaltas(BaseDelRecinto):
    """M-14: saber quién entorpece el sistema (P4)."""

    def test_ordena_de_mas_a_menos_faltas(self):
        for cliente, cantidad in ((self.cliente, 2), (self.otro_cliente, 5)):
            for numero in range(cantidad):
                momento = timezone.now() - timedelta(days=numero + 1)
                reserva = Reserva.objects.create(
                    cancha=self.cancha,
                    cliente=cliente,
                    inicio=momento,
                    fin=momento + timedelta(hours=1),
                    estado=Reserva.Estado.VENCIDA,
                    precio=1000,
                    vence_en=momento,
                )
                Falta.objects.create(cliente=cliente, reserva=reserva, motivo="prueba")

        resumen = list(servicios.resumen_de_faltas())
        self.assertEqual([c.username for c in resumen], ["drojas", "cmunoz"])
        self.assertEqual([c.total_faltas for c in resumen], [5, 2])

    def test_no_lista_clientes_sin_faltas(self):
        self.assertEqual(list(servicios.resumen_de_faltas()), [])


class ZonaHoraria(BaseDelRecinto):
    """M-16 · RN-07: Santiago de Chile."""

    def test_la_configuracion_apunta_a_santiago(self):
        from django.conf import settings

        self.assertEqual(settings.TIME_ZONE, "America/Santiago")
        self.assertTrue(settings.USE_TZ)

    def test_se_guarda_en_utc_y_se_muestra_en_santiago(self):
        reserva = self.solicitar()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio.utcoffset(), timedelta(0))  # UTC en la base de datos
        local = timezone.localtime(reserva.inicio)
        self.assertIn(local.utcoffset(), (timedelta(hours=-3), timedelta(hours=-4)))

    def test_la_agenda_se_arma_en_hora_local(self):
        dia = timezone.localdate() + timedelta(days=2)
        bloques = servicios.bloques_del_dia(self.cancha, dia)
        self.assertEqual(len(bloques), 14)  # 09:00 a 23:00, bloques de una hora
        primero = timezone.localtime(bloques[0]["inicio"])
        ultimo = timezone.localtime(bloques[-1]["fin"])
        self.assertEqual((primero.hour, primero.minute), (9, 0))
        self.assertEqual((ultimo.hour, ultimo.minute), (23, 0))


class Agenda(BaseDelRecinto):
    """M-07."""

    def test_la_agenda_es_publica(self):
        self.assertEqual(self.client.get(reverse("reservas:agenda")).status_code, 200)

    def test_marca_el_bloque_tomado_como_no_disponible(self):
        # Un bloque dentro del horario del recinto, pasado mañana a las 20:00.
        inicio = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
        reserva = servicios.solicitar_reserva(self.cliente, self.cancha, inicio)
        dia = timezone.localtime(reserva.inicio).date()
        bloques = servicios.bloques_del_dia(self.cancha, dia)
        tomado = next(b for b in bloques if b["inicio"] == reserva.inicio)
        self.assertFalse(tomado["disponible"])
        self.assertEqual(tomado["ocupante"], reserva)
