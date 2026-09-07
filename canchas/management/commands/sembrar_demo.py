"""
Deja los archivos JSON en un estado demostrable.

Reescribe `data/reservas.json` con un escenario relativo al momento actual, de
modo que la PoC se pueda mostrar sin esperar media hora a que algo venza:

* una reserva ya PAGADA para hoy en la tarde;
* una solicitud PENDIENTE_PAGO recién creada, con su ventana corriendo;
* un cliente con 9 faltas, a una sola falta del bloqueo automático (RN-05).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand

from canchas import reglas, repositorio


class Command(BaseCommand):
    help = "Carga un escenario de demostración en data/reservas.json (lo sobrescribe)."

    def handle(self, *args, **opciones):
        ahora = reglas.ahora()
        duracion = timedelta(minutes=repositorio.horario_recinto()["duracion_bloque_min"])

        def bloque(horas_desde_ahora: int):
            inicio = (ahora + timedelta(hours=horas_desde_ahora)).replace(
                minute=0, second=0, microsecond=0
            )
            return inicio, inicio + duracion

        reservas, faltas = [], []
        correlativo = 0

        # 1) Reserva real: pagada y confirmada.
        correlativo += 1
        inicio, fin = bloque(4)
        reservas.append(
            {
                "id": correlativo,
                "cancha_id": 1,
                "cliente_id": 2,
                "inicio": reglas.a_iso(inicio),
                "fin": reglas.a_iso(fin),
                "estado": reglas.PAGADA,
                "creada_en": reglas.a_iso(ahora - timedelta(hours=3)),
                "vence_en": reglas.a_iso(ahora - timedelta(hours=3) + reglas.VENTANA_DE_PAGO),
                "pagada_en": reglas.a_iso(ahora - timedelta(hours=2, minutes=50)),
                "vencida_en": None,
                "precio": 45000,
            }
        )

        # 2) Solicitud viva: el reloj de los 30 minutos está corriendo.
        correlativo += 1
        inicio, fin = bloque(6)
        reservas.append(
            {
                "id": correlativo,
                "cancha_id": 2,
                "cliente_id": 1,
                "inicio": reglas.a_iso(inicio),
                "fin": reglas.a_iso(fin),
                "estado": reglas.PENDIENTE_PAGO,
                "creada_en": reglas.a_iso(ahora - timedelta(minutes=5)),
                "vence_en": reglas.a_iso(
                    reglas.calcular_vence_en(ahora - timedelta(minutes=5), inicio)
                ),
                "pagada_en": None,
                "vencida_en": None,
                "precio": 40000,
            }
        )

        # 3) Ignacio Vera: 9 faltas históricas. La décima lo bloquea.
        for numero in range(9):
            correlativo += 1
            momento = ahora - timedelta(days=numero + 1)
            inicio = momento.replace(hour=21, minute=0, second=0, microsecond=0)
            reservas.append(
                {
                    "id": correlativo,
                    "cancha_id": 3,
                    "cliente_id": 3,
                    "inicio": reglas.a_iso(inicio),
                    "fin": reglas.a_iso(inicio + duracion),
                    "estado": reglas.VENCIDA,
                    "creada_en": reglas.a_iso(inicio - timedelta(hours=2)),
                    "vence_en": reglas.a_iso(inicio - timedelta(hours=1, minutes=30)),
                    "pagada_en": None,
                    "vencida_en": reglas.a_iso(inicio - timedelta(hours=1, minutes=30)),
                    "precio": 28000,
                }
            )
            faltas.append(
                {
                    "id": numero + 1,
                    "cliente_id": 3,
                    "reserva_id": correlativo,
                    "motivo": "No pagó dentro de la ventana de 30 minutos (RN-02).",
                    "registrada_en": reglas.a_iso(inicio - timedelta(hours=1, minutes=30)),
                }
            )

        repositorio._escribir(  # noqa: SLF001 — la PoC no expone otra puerta de escritura
            repositorio.ARCHIVO_RESERVAS,
            {
                "secuencia": correlativo,
                "secuencia_faltas": len(faltas),
                "reservas": reservas,
                "faltas": faltas,
            },
        )
        clientes = repositorio.listar_clientes()
        for cliente in clientes:
            cliente["bloqueado"] = False
        repositorio.guardar_clientes(clientes)

        self.stdout.write(
            self.style.SUCCESS(
                f"Escenario cargado: {len(reservas)} reservas y {len(faltas)} faltas.\n"
                "Ignacio Vera tiene 9 faltas: una más y queda bloqueado (RN-05)."
            )
        )
