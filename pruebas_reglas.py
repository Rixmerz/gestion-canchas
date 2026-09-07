"""
Verificación de las reglas de negocio de la PoC.

    python -m unittest pruebas_reglas -v

No necesita Django ni servidor: `canchas.reglas` es Python puro. Es el
entregable que responde la pregunta de la Prueba de Concepto — ¿las reglas
críticas del arriendo son implementables y correctas?
"""

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from canchas import reglas

SANTIAGO = ZoneInfo("America/Santiago")


def stgo(texto: str) -> datetime:
    """Un instante local de Santiago escrito como 'YYYY-MM-DD HH:MM'."""
    return datetime.fromisoformat(texto).replace(tzinfo=SANTIAGO)


class AnticipacionMinima(unittest.TestCase):
    """RN-01: al menos 30 minutos entre la solicitud y el inicio del bloque."""

    def test_acepta_exactamente_30_minutos(self):
        reglas.validar_anticipacion(stgo("2026-09-10 20:00"), stgo("2026-09-10 19:30"))

    def test_rechaza_29_minutos(self):
        with self.assertRaises(reglas.ReglaViolada) as caso:
            reglas.validar_anticipacion(stgo("2026-09-10 20:00"), stgo("2026-09-10 19:31"))
        self.assertEqual(caso.exception.regla, "RN-01")

    def test_rechaza_un_bloque_ya_comenzado(self):
        with self.assertRaises(reglas.ReglaViolada):
            reglas.validar_anticipacion(stgo("2026-09-10 20:00"), stgo("2026-09-10 20:15"))

    def test_version_booleana_coincide(self):
        self.assertTrue(
            reglas.puede_solicitarse(stgo("2026-09-10 20:00"), stgo("2026-09-10 18:00"))
        )
        self.assertFalse(
            reglas.puede_solicitarse(stgo("2026-09-10 20:00"), stgo("2026-09-10 19:45"))
        )


class VentanaDePago(unittest.TestCase):
    """RN-02: vence_en = min(creada_en + 30 min, inicio del bloque)."""

    def test_reserva_lejana_tiene_ventana_de_30_minutos(self):
        creada = stgo("2026-09-10 12:00")
        vence = reglas.calcular_vence_en(creada, stgo("2026-09-12 21:00"))
        self.assertEqual(vence, stgo("2026-09-10 12:30"))

    def test_la_ventana_nunca_pasa_del_inicio_del_bloque(self):
        creada = stgo("2026-09-10 19:25")
        vence = reglas.calcular_vence_en(creada, stgo("2026-09-10 19:55"))
        self.assertEqual(vence, stgo("2026-09-10 19:55"))

    def test_reserva_al_limite_de_rn01_vence_justo_al_empezar(self):
        creada = stgo("2026-09-10 19:30")
        self.assertEqual(
            reglas.calcular_vence_en(creada, stgo("2026-09-10 20:00")), stgo("2026-09-10 20:00")
        )


class Vencimiento(unittest.TestCase):
    """RN-04: la pendiente no pagada vence; la pagada no vence nunca."""

    def test_pendiente_pasado_el_plazo_esta_vencida(self):
        self.assertTrue(
            reglas.esta_vencida(
                reglas.PENDIENTE_PAGO, stgo("2026-09-10 12:30"), stgo("2026-09-10 12:31")
            )
        )

    def test_pendiente_dentro_del_plazo_no_esta_vencida(self):
        self.assertFalse(
            reglas.esta_vencida(
                reglas.PENDIENTE_PAGO, stgo("2026-09-10 12:30"), stgo("2026-09-10 12:29")
            )
        )

    def test_la_reserva_pagada_no_vence(self):
        self.assertFalse(
            reglas.esta_vencida(reglas.PAGADA, stgo("2026-09-10 12:30"), stgo("2026-09-11 00:00"))
        )


class BloqueoPorFaltas(unittest.TestCase):
    """RN-05: a las 10 faltas el cliente queda bloqueado."""

    def test_nueve_faltas_todavia_habilitan(self):
        self.assertFalse(reglas.debe_bloquearse(9))
        reglas.validar_cliente_habilitado(bloqueado=False, cantidad_faltas=9)

    def test_diez_faltas_bloquean(self):
        self.assertTrue(reglas.debe_bloquearse(10))
        with self.assertRaises(reglas.ReglaViolada) as caso:
            reglas.validar_cliente_habilitado(bloqueado=False, cantidad_faltas=10)
        self.assertEqual(caso.exception.regla, "RN-05")

    def test_un_cliente_ya_marcado_no_puede_solicitar(self):
        with self.assertRaises(reglas.ReglaViolada):
            reglas.validar_cliente_habilitado(bloqueado=True, cantidad_faltas=0)


class Solapamiento(unittest.TestCase):
    """RN-06: una cancha no admite dos reservas vigentes superpuestas."""

    def test_bloques_contiguos_no_se_solapan(self):
        self.assertFalse(
            reglas.se_solapan(
                stgo("2026-09-10 20:00"),
                stgo("2026-09-10 21:00"),
                stgo("2026-09-10 21:00"),
                stgo("2026-09-10 22:00"),
            )
        )

    def test_solapamiento_parcial(self):
        self.assertTrue(
            reglas.se_solapan(
                stgo("2026-09-10 20:00"),
                stgo("2026-09-10 21:00"),
                stgo("2026-09-10 20:30"),
                stgo("2026-09-10 21:30"),
            )
        )

    def test_validar_rechaza_el_bloque_tomado(self):
        ocupados = [(stgo("2026-09-10 20:00"), stgo("2026-09-10 21:00"))]
        with self.assertRaises(reglas.ReglaViolada) as caso:
            reglas.validar_sin_solapamiento(
                stgo("2026-09-10 20:00"), stgo("2026-09-10 21:00"), ocupados
            )
        self.assertEqual(caso.exception.regla, "RN-06")

    def test_validar_acepta_el_bloque_siguiente(self):
        ocupados = [(stgo("2026-09-10 20:00"), stgo("2026-09-10 21:00"))]
        reglas.validar_sin_solapamiento(
            stgo("2026-09-10 21:00"), stgo("2026-09-10 22:00"), ocupados
        )


class ZonaHoraria(unittest.TestCase):
    """RN-07: Santiago de Chile, incluido el cambio de horario de verano."""

    def test_rechaza_datetimes_sin_zona(self):
        with self.assertRaises(ValueError):
            reglas.a_local(datetime(2026, 9, 10, 20, 0))

    def test_convierte_desde_utc(self):
        utc = datetime(2026, 9, 10, 23, 0, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(reglas.a_local(utc), stgo("2026-09-10 20:00"))

    def test_ida_y_vuelta_por_iso(self):
        momento = stgo("2026-09-10 20:00")
        self.assertEqual(reglas.desde_iso(reglas.a_iso(momento)), momento)

    def test_horario_de_invierno_y_de_verano_tienen_distinto_offset(self):
        invierno = stgo("2026-06-15 20:00").utcoffset()
        verano = stgo("2026-12-15 20:00").utcoffset()
        self.assertEqual(invierno, timedelta(hours=-4))
        self.assertEqual(verano, timedelta(hours=-3))

    def test_la_ventana_de_pago_cruza_el_cambio_de_hora_sin_saltos(self):
        # Chile adelanta el reloj el primer domingo de septiembre a medianoche:
        # las 00:00 pasan a ser las 01:00, y esa hora local no existe.
        creada = stgo("2026-09-05 23:50")

        # Sumar el timedelta a secas da 00:20, un instante inexistente.
        ingenuo = creada + timedelta(minutes=30)
        self.assertEqual(ingenuo.hour, 0)

        # `sumar` trabaja en UTC: 30 minutos reales después son las 01:20.
        correcto = reglas.sumar(creada, timedelta(minutes=30))
        self.assertEqual((correcto.hour, correcto.minute), (1, 20))
        self.assertEqual(reglas.diferencia(correcto, creada), timedelta(minutes=30))

    def test_el_vencimiento_respeta_el_cambio_de_hora(self):
        creada = stgo("2026-09-05 23:50")
        vence = reglas.calcular_vence_en(creada, stgo("2026-09-07 21:00"))
        self.assertEqual((vence.hour, vence.minute), (1, 20))
        self.assertEqual(reglas.diferencia(vence, creada), reglas.VENTANA_DE_PAGO)


class AritmeticaDeTiempo(unittest.TestCase):
    """
    Las dos trampas de `datetime` que RN-07 obliga a evitar, ambas activas en
    el cambio de horario chileno del 6 de septiembre de 2026.
    """

    def test_restar_relojes_de_pared_miente_sobre_la_anticipacion(self):
        antes = stgo("2026-09-05 23:45")
        despues = stgo("2026-09-06 01:00")
        # Reloj de pared: 1 h 15 min. Tiempo real: 15 minutos.
        self.assertEqual(despues - antes, timedelta(hours=1, minutes=15))
        self.assertEqual(reglas.diferencia(despues, antes), timedelta(minutes=15))

    def test_rn01_usa_el_tiempo_real_en_el_cambio_de_hora(self):
        # Faltan 15 minutos reales para el bloque: hay que rechazar la solicitud,
        # aunque el reloj de pared muestre una diferencia de 1 h 15 min.
        with self.assertRaises(reglas.ReglaViolada) as caso:
            reglas.validar_anticipacion(stgo("2026-09-06 01:00"), stgo("2026-09-05 23:45"))
        self.assertEqual(caso.exception.regla, "RN-01")


if __name__ == "__main__":
    unittest.main(verbosity=2)
