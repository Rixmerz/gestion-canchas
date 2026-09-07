"""
Casos de uso del MVP: las reglas puras de `reglas.py` aplicadas sobre el ORM.

Toda escritura que involucre más de una tabla ocurre dentro de una transacción,
para que una reserva vencida y su falta entren o no entren juntas.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import reglas
from .models import Cancha, Falta, Reserva, Usuario

#: Duración fija del bloque en el MVP. La duración variable es un Should (S-06).
DURACION_BLOQUE = timedelta(minutes=60)
APERTURA = time(9, 0)
CIERRE = time(23, 0)


# --- RN-04: vencimiento -----------------------------------------------------


@transaction.atomic
def vencer_reservas_pendientes(referencia: datetime | None = None) -> int:
    """
    Marca como `VENCIDA` toda reserva pendiente cuyo plazo de pago ya pasó,
    registra su falta y bloquea al cliente que llegue al límite (RN-04, RN-05).

    Se invoca de forma perezosa al abrir la agenda o al solicitar, y también
    desde `manage.py vencer_reservas` (M-18). Devuelve cuántas vencieron.
    """
    referencia = referencia or timezone.now()
    vencidas = list(
        Reserva.objects.select_for_update().por_vencer(referencia).select_related("cliente")
    )
    if not vencidas:
        return 0

    for reserva in vencidas:
        reserva.estado = Reserva.Estado.VENCIDA
        reserva.vencida_en = referencia
    Reserva.objects.bulk_update(vencidas, ["estado", "vencida_en"])

    Falta.objects.bulk_create(
        [
            Falta(
                cliente=reserva.cliente,
                reserva=reserva,
                motivo="No pagó dentro de la ventana de 30 minutos (RN-02).",
                registrada_en=referencia,
            )
            for reserva in vencidas
        ],
        ignore_conflicts=True,
    )

    for cliente in {reserva.cliente for reserva in vencidas}:
        evaluar_bloqueo(cliente, referencia)

    return len(vencidas)


def evaluar_bloqueo(cliente: Usuario, referencia: datetime | None = None) -> bool:
    """RN-05: bloquea al cliente que alcanzó el límite de faltas vigentes."""
    if reglas.debe_bloquearse(cliente.faltas_vigentes()) and not cliente.bloqueado:
        cliente.bloqueado = True
        cliente.bloqueado_en = referencia or timezone.now()
        cliente.save(update_fields=["bloqueado", "bloqueado_en"])
        return True
    return False


def desbloquear(cliente: Usuario, anular_faltas: bool = True) -> None:
    """
    Desbloqueo manual del administrador.

    Anula las faltas vigentes por defecto: si no se anularan, el cliente
    volvería a quedar bloqueado en el siguiente barrido. Las faltas anuladas se
    conservan como historial (`vigente=False`), no se borran.
    """
    with transaction.atomic():
        if anular_faltas:
            cliente.faltas.filter(vigente=True).update(vigente=False)
        cliente.bloqueado = False
        cliente.bloqueado_en = None
        cliente.save(update_fields=["bloqueado", "bloqueado_en"])


# --- Agenda (M-07) ----------------------------------------------------------


def bloques_del_dia(cancha: Cancha, dia: date) -> list[dict]:
    """Grilla horaria de una cancha para un día, en hora de Santiago."""
    referencia = timezone.now()
    inicio_dia = timezone.make_aware(datetime.combine(dia, time.min))
    fin_dia = inicio_dia + timedelta(days=1)

    ocupadas = list(
        Reserva.objects.vigentes()
        .filter(cancha=cancha, inicio__gte=inicio_dia, inicio__lt=fin_dia)
        .select_related("cliente")
    )

    bloques = []
    momento = timezone.make_aware(datetime.combine(dia, APERTURA))
    limite = timezone.make_aware(datetime.combine(dia, CIERRE))

    while momento + DURACION_BLOQUE <= limite:
        fin = momento + DURACION_BLOQUE
        ocupante = next(
            (r for r in ocupadas if reglas.se_solapan(momento, fin, r.inicio, r.fin)), None
        )
        a_tiempo = reglas.puede_solicitarse(momento, referencia)
        bloques.append(
            {
                "inicio": momento,
                "fin": fin,
                "ocupante": ocupante,
                "a_tiempo": a_tiempo,
                "disponible": ocupante is None and a_tiempo,
            }
        )
        momento = fin
    return bloques


# --- M-08: solicitar (el caso de uso central) -------------------------------


def solicitar_reserva(cliente: Usuario, cancha: Cancha, inicio: datetime) -> Reserva:
    """
    Crea el "hold" del bloque tras validar todas las reglas Must.

    Lanza `reglas.ReglaViolada` si alguna no se cumple; en ese caso la
    transacción no deja rastro en la base de datos.
    """
    vencer_reservas_pendientes()

    if not cancha.activa:
        raise reglas.ReglaViolada("RN-06", "La cancha no está disponible para arriendo.")
    if cliente.es_administrador:
        raise reglas.ReglaViolada(
            "RN-08", "Las reservas las solicitan los clientes, no los administradores."
        )

    reglas.validar_cliente_habilitado(cliente.bloqueado, cliente.faltas_vigentes())

    referencia = timezone.now()
    reglas.validar_anticipacion(inicio, referencia)

    fin = reglas.sumar(inicio, DURACION_BLOQUE)

    try:
        with transaction.atomic():
            ocupadas = (
                Reserva.objects.select_for_update()
                .vigentes()
                .filter(cancha=cancha, inicio__lt=fin, fin__gt=inicio)
                .values_list("inicio", "fin")
            )
            reglas.validar_sin_solapamiento(inicio, fin, list(ocupadas))

            return Reserva.objects.create(
                cancha=cancha,
                cliente=cliente,
                inicio=inicio,
                fin=fin,
                estado=Reserva.Estado.PENDIENTE_PAGO,
                precio=cancha.precio_hora,
                creada_en=referencia,
                vence_en=reglas.calcular_vence_en(referencia, inicio),
            )
    except IntegrityError as error:
        # La restricción única de la base de datos ganó la carrera.
        raise reglas.ReglaViolada(
            "RN-06", "Otro cliente tomó este bloque hace un instante."
        ) from error


# --- RN-03: confirmación del pago -------------------------------------------


def confirmar_pago(reserva: Reserva, administrador: Usuario) -> Reserva:
    """La solicitud se convierte en reserva real. Es un acto manual (M-12)."""
    if not administrador.es_administrador:
        raise reglas.ReglaViolada("RN-03", "Solo un administrador puede confirmar un pago.")
    if not reserva.esta_pendiente:
        raise reglas.ReglaViolada(
            "RN-03",
            f"Solo se confirma el pago de una reserva pendiente "
            f"(esta está {reserva.get_estado_display().lower()}).",
        )
    ahora = timezone.now()
    if reglas.esta_vencida(reserva.estado, reserva.vence_en, ahora):
        raise reglas.ReglaViolada(
            "RN-02", "La ventana de pago ya venció; el bloque se liberó."
        )

    reserva.estado = Reserva.Estado.PAGADA
    reserva.pagada_en = ahora
    reserva.confirmada_por = administrador
    reserva.save(update_fields=["estado", "pagada_en", "confirmada_por"])
    return reserva


def cancelar_reserva(reserva: Reserva) -> Reserva:
    """Cancelación administrativa: libera el bloque y **no** genera falta."""
    if not reserva.es_vigente:
        raise reglas.ReglaViolada(
            "RN-03", f"No se puede cancelar una reserva {reserva.get_estado_display().lower()}."
        )
    reserva.estado = Reserva.Estado.CANCELADA
    reserva.save(update_fields=["estado"])
    return reserva


# --- M-14: vista de faltas --------------------------------------------------


def resumen_de_faltas():
    """Una fila por cliente con faltas, de más a menos, para el administrador."""
    from django.db.models import Count, Q

    return (
        Usuario.objects.filter(rol=Usuario.Rol.CLIENTE)
        .annotate(total_faltas=Count("faltas", filter=Q(faltas__vigente=True)))
        .filter(total_faltas__gt=0)
        .order_by("-total_faltas", "username")
    )
