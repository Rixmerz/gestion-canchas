"""
M-18 · RN-04: vence las reservas no pagadas y registra sus faltas.

Pensado para cron cada 5 minutos:

    */5 * * * * cd /ruta/al/proyecto && .venv/bin/python manage.py vencer_reservas

El MVP además ejecuta este mismo barrido de forma perezosa al abrir la agenda o
al solicitar, de modo que el estado sea correcto aunque nadie configure el cron.
"""

from django.core.management.base import BaseCommand

from reservas import servicios


class Command(BaseCommand):
    help = "Vence las reservas pendientes fuera de plazo, registra faltas y bloquea (RN-04, RN-05)."

    def handle(self, *args, **opciones):
        vencidas = servicios.vencer_reservas_pendientes()
        if vencidas:
            self.stdout.write(
                self.style.WARNING(
                    f"{vencidas} reserva(s) vencida(s) por falta de pago. "
                    "Los bloques quedaron libres y se registraron las faltas."
                )
            )
        else:
            self.stdout.write("Sin reservas vencidas.")
