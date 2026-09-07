"""
Reglas de negocio del MVP.

Módulo de **Python puro**: no importa Django, no toca la base de datos y no
sabe que existe un ORM. Es el mismo núcleo que se validó en la PoC (rama
`eva1`), incluidas las dos correcciones de aritmética de fechas que allí
aparecieron, y aquí se reutiliza tal cual sobre el modelo relacional.

Reglas implementadas (ver `docs/01-problema-y-solucion.md`):

* RN-01  Anticipación mínima de 30 minutos.
* RN-02  Ventana de pago: vence_en = min(creada_en + 30 min, inicio).
* RN-04  Vencimiento sin pago -> VENCIDA + una falta.
* RN-05  Bloqueo automático al llegar a 10 faltas.
* RN-06  Sin solapamiento de reservas vigentes en una misma cancha.
* RN-07  Toda la aritmética ocurre en horario de Santiago de Chile.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Parámetros de negocio --------------------------------------------------

ZONA = ZoneInfo("America/Santiago")
UTC = ZoneInfo("UTC")

#: RN-01 — anticipación mínima para poder solicitar un bloque.
ANTICIPACION_MINIMA = timedelta(minutes=30)

#: RN-02 — cuánto dura el "hold" antes de vencer por falta de pago.
VENTANA_DE_PAGO = timedelta(minutes=30)

#: RN-05 — faltas que gatillan el bloqueo automático del cliente.
FALTAS_PARA_BLOQUEO = 10

# --- Estados de la reserva --------------------------------------------------

PENDIENTE_PAGO = "PENDIENTE_PAGO"
PAGADA = "PAGADA"
VENCIDA = "VENCIDA"
CANCELADA = "CANCELADA"

#: Estados que ocupan el bloque y, por lo tanto, participan del solapamiento.
ESTADOS_VIGENTES = (PENDIENTE_PAGO, PAGADA)


class ReglaViolada(Exception):
    """La operación solicitada infringe una regla de negocio."""

    def __init__(self, regla: str, mensaje: str):
        self.regla = regla
        super().__init__(f"[{regla}] {mensaje}")


# --- Tiempo (RN-07) ---------------------------------------------------------


def ahora() -> datetime:
    """Instante actual, consciente de zona horaria, en hora de Santiago."""
    return datetime.now(ZONA)


def a_utc(momento: datetime) -> datetime:
    """Instante listo para guardar en la base de datos (Django almacena en UTC)."""
    return en_utc(momento)


def a_local(momento: datetime) -> datetime:
    """Lleva cualquier datetime *aware* a la hora de Santiago."""
    if momento.tzinfo is None:
        raise ValueError("RN-07: no se aceptan datetimes sin zona horaria.")
    return momento.astimezone(ZONA)


def desde_iso(texto: str) -> datetime:
    """Lee un instante ISO-8601 con offset y lo devuelve en hora de Santiago."""
    return a_local(datetime.fromisoformat(texto))


def a_iso(momento: datetime) -> str:
    """Serializa un instante a ISO-8601 en hora de Santiago."""
    return a_local(momento).isoformat()


def sumar(momento: datetime, delta: timedelta) -> datetime:
    """
    Suma un intervalo de **tiempo real**, no de reloj de pared.

    Sumar un `timedelta` directamente a un datetime con zona horaria hace
    aritmética de calendario: Python cambia la hora del reloj y recién después
    resuelve el offset. En el cambio de horario chileno eso corre la ventana de
    pago una hora entera, o la deja en un instante que no existe. Se suma en UTC
    y se vuelve a hora local.
    """
    utc = a_local(momento).astimezone(UTC)
    return (utc + delta).astimezone(ZONA)


def en_utc(momento: datetime) -> datetime:
    """
    Instante llevado a UTC, la única forma segura de **comparar** dos fechas.

    Al igual que la resta, la comparación de dos datetimes que comparten
    `tzinfo` ignora la zona y compara relojes de pared: en la hora repetida del
    cambio de horario de abril eso da dos instantes distintos como iguales.
    """
    return a_local(momento).astimezone(UTC)


def diferencia(fin: datetime, inicio: datetime) -> timedelta:
    """
    Tiempo real transcurrido entre dos instantes.

    Restar dos datetimes que comparten el mismo `tzinfo` hace que Python ignore
    la zona y reste los relojes de pared. Convertir ambos a UTC obliga a medir
    tiempo real, que es lo que exige RN-01.
    """
    return a_local(fin).astimezone(UTC) - a_local(inicio).astimezone(UTC)


# --- RN-01: anticipación mínima --------------------------------------------


def validar_anticipacion(inicio: datetime, referencia: datetime) -> None:
    """Exige al menos 30 minutos entre `referencia` y el inicio del bloque."""
    faltante = diferencia(inicio, referencia)
    if faltante < ANTICIPACION_MINIMA:
        minutos = int(faltante.total_seconds() // 60)
        detalle = (
            f"faltan {minutos} minutos" if faltante.total_seconds() > 0 else "el bloque ya comenzó"
        )
        raise ReglaViolada(
            "RN-01",
            "Solo se puede solicitar con al menos 30 minutos de anticipación: " + detalle + ".",
        )


def puede_solicitarse(inicio: datetime, referencia: datetime) -> bool:
    """Versión booleana de RN-01, para pintar la agenda sin excepciones."""
    return diferencia(inicio, referencia) >= ANTICIPACION_MINIMA


# --- RN-02: ventana de pago -------------------------------------------------


def calcular_vence_en(creada_en: datetime, inicio: datetime) -> datetime:
    """
    Momento en que muere el "hold" si nadie confirma el pago.

    Es el menor entre `creada_en + 30 min` y el inicio del bloque: el cliente
    siempre tiene una ventana para pagar, y esa ventana jamás se estira más
    allá del comienzo del partido.
    """
    return min(sumar(creada_en, VENTANA_DE_PAGO), a_local(inicio), key=en_utc)


# --- RN-04: vencimiento -----------------------------------------------------


def esta_vencida(estado: str, vence_en: datetime, referencia: datetime) -> bool:
    """¿Esta reserva pendiente ya pasó su plazo de pago?"""
    return estado == PENDIENTE_PAGO and en_utc(referencia) >= en_utc(vence_en)


# --- RN-05: bloqueo por faltas ---------------------------------------------


def debe_bloquearse(cantidad_faltas: int) -> bool:
    """El cliente queda bloqueado al alcanzar el límite de faltas."""
    return cantidad_faltas >= FALTAS_PARA_BLOQUEO


def validar_cliente_habilitado(bloqueado: bool, cantidad_faltas: int) -> None:
    """Un cliente bloqueado no puede solicitar nada más."""
    if bloqueado or debe_bloquearse(cantidad_faltas):
        raise ReglaViolada(
            "RN-05",
            f"El cliente está bloqueado por acumular {cantidad_faltas} faltas "
            f"(límite: {FALTAS_PARA_BLOQUEO}). Debe regularizar con el administrador.",
        )


# --- RN-06: solapamiento ----------------------------------------------------


def se_solapan(inicio_a: datetime, fin_a: datetime, inicio_b: datetime, fin_b: datetime) -> bool:
    """Dos intervalos se solapan si cada uno empieza antes de que el otro termine."""
    return en_utc(inicio_a) < en_utc(fin_b) and en_utc(inicio_b) < en_utc(fin_a)


def validar_sin_solapamiento(inicio: datetime, fin: datetime, ocupados) -> None:
    """
    `ocupados` es un iterable de pares (inicio, fin) de las reservas vigentes
    de la misma cancha.
    """
    for inicio_ocupado, fin_ocupado in ocupados:
        if se_solapan(inicio, fin, inicio_ocupado, fin_ocupado):
            hora = a_local(inicio_ocupado).strftime("%H:%M")
            raise ReglaViolada(
                "RN-06",
                f"La cancha ya tiene una reserva vigente que parte a las {hora}.",
            )
