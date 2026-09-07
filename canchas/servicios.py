"""
Casos de uso de la PoC: orquestan las reglas (`reglas.py`) sobre la
persistencia en JSON (`repositorio.py`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import reglas, repositorio


# --- Vencimiento perezoso (RN-04) -------------------------------------------


def vencer_reservas_pendientes() -> int:
    """
    Barre las reservas `PENDIENTE_PAGO` cuyo plazo ya pasó: las marca
    `VENCIDA`, libera el bloque y registra una falta por cada una.

    Se llama antes de mostrar la agenda y antes de aceptar una solicitud, de
    modo que el estado siempre esté al día sin necesidad de un proceso aparte.
    Devuelve cuántas reservas vencieron.
    """
    referencia = reglas.ahora()
    vencidas, faltas = [], []

    for reserva in repositorio.listar_reservas():
        if not reglas.esta_vencida(
            reserva["estado"], reglas.desde_iso(reserva["vence_en"]), referencia
        ):
            continue
        vencidas.append(
            {
                "id": reserva["id"],
                "estado": reglas.VENCIDA,
                "vencida_en": reglas.a_iso(referencia),
            }
        )
        faltas.append(
            {
                "cliente_id": reserva["cliente_id"],
                "reserva_id": reserva["id"],
                "motivo": "No pagó dentro de la ventana de 30 minutos (RN-02).",
                "registrada_en": reglas.a_iso(referencia),
            }
        )

    repositorio.aplicar_vencimientos(vencidas, faltas)
    _sincronizar_bloqueos()
    return len(vencidas)


def _sincronizar_bloqueos() -> None:
    """RN-05: marca como bloqueado a todo cliente que llegó al límite de faltas."""
    conteo = contar_faltas_por_cliente()
    clientes = repositorio.listar_clientes()
    cambio = False
    for cliente in clientes:
        debe = reglas.debe_bloquearse(conteo.get(cliente["id"], 0))
        if debe and not cliente["bloqueado"]:
            cliente["bloqueado"] = True
            cambio = True
    if cambio:
        repositorio.guardar_clientes(clientes)


# --- Faltas -----------------------------------------------------------------


def contar_faltas_por_cliente() -> dict[int, int]:
    conteo: dict[int, int] = {}
    for falta in repositorio.listar_faltas():
        conteo[falta["cliente_id"]] = conteo.get(falta["cliente_id"], 0) + 1
    return conteo


def resumen_de_faltas() -> list[dict]:
    """Una fila por cliente, ordenada de más a menos faltas."""
    conteo = contar_faltas_por_cliente()
    filas = [
        {
            "cliente": cliente,
            "faltas": conteo.get(cliente["id"], 0),
            "restantes": max(reglas.FALTAS_PARA_BLOQUEO - conteo.get(cliente["id"], 0), 0),
            "bloqueado": cliente["bloqueado"],
        }
        for cliente in repositorio.listar_clientes()
    ]
    return sorted(filas, key=lambda fila: fila["faltas"], reverse=True)


# --- Agenda (RN-01, RN-06, RN-07) -------------------------------------------


def bloques_del_dia(cancha_id: int, dia: date) -> list[dict]:
    """
    Construye la grilla horaria de una cancha para un día, marcando cada bloque
    como libre, tomado o fuera de plazo.
    """
    horario = repositorio.horario_recinto()
    apertura = time.fromisoformat(horario["apertura"])
    cierre = time.fromisoformat(horario["cierre"])
    duracion = timedelta(minutes=horario["duracion_bloque_min"])

    referencia = reglas.ahora()
    ocupadas = _reservas_vigentes_de(cancha_id)

    bloques = []
    momento = datetime.combine(dia, apertura, tzinfo=reglas.ZONA)
    limite = datetime.combine(dia, cierre, tzinfo=reglas.ZONA)

    while momento + duracion <= limite:
        fin = momento + duracion
        ocupante = next(
            (
                reserva
                for reserva in ocupadas
                if reglas.se_solapan(
                    momento,
                    fin,
                    reglas.desde_iso(reserva["inicio"]),
                    reglas.desde_iso(reserva["fin"]),
                )
            ),
            None,
        )
        bloques.append(
            {
                "inicio": momento,
                "fin": fin,
                "ocupante": ocupante,
                "a_tiempo": reglas.puede_solicitarse(momento, referencia),
                "disponible": ocupante is None and reglas.puede_solicitarse(momento, referencia),
            }
        )
        momento = fin
    return bloques


def _reservas_vigentes_de(cancha_id: int) -> list[dict]:
    return [
        reserva
        for reserva in repositorio.listar_reservas()
        if reserva["cancha_id"] == cancha_id and reserva["estado"] in reglas.ESTADOS_VIGENTES
    ]


# --- Solicitar (el caso de uso central) -------------------------------------


def solicitar_reserva(cliente_id: int, cancha_id: int, inicio: datetime) -> dict:
    """
    Crea el "hold" del bloque tras validar todas las reglas.

    Lanza `reglas.ReglaViolada` si alguna no se cumple; en ese caso no escribe
    nada en los archivos JSON.
    """
    vencer_reservas_pendientes()

    cliente = repositorio.obtener_cliente(cliente_id)
    if cliente is None:
        raise reglas.ReglaViolada("RN-08", "El cliente indicado no existe.")

    cancha = repositorio.obtener_cancha(cancha_id)
    if cancha is None or not cancha["activa"]:
        raise reglas.ReglaViolada("RN-06", "La cancha no existe o está inactiva.")

    faltas = contar_faltas_por_cliente().get(cliente_id, 0)
    reglas.validar_cliente_habilitado(cliente["bloqueado"], faltas)

    referencia = reglas.ahora()
    reglas.validar_anticipacion(inicio, referencia)

    duracion = timedelta(minutes=repositorio.horario_recinto()["duracion_bloque_min"])
    fin = inicio + duracion
    reglas.validar_sin_solapamiento(
        inicio,
        fin,
        [
            (reglas.desde_iso(r["inicio"]), reglas.desde_iso(r["fin"]))
            for r in _reservas_vigentes_de(cancha_id)
        ],
    )

    return repositorio.crear_reserva(
        {
            "cancha_id": cancha_id,
            "cliente_id": cliente_id,
            "inicio": reglas.a_iso(inicio),
            "fin": reglas.a_iso(fin),
            "estado": reglas.PENDIENTE_PAGO,
            "creada_en": reglas.a_iso(referencia),
            "vence_en": reglas.a_iso(reglas.calcular_vence_en(referencia, inicio)),
            "pagada_en": None,
            "vencida_en": None,
            "precio": cancha["precio_hora"],
        }
    )


# --- Gestión del administrador (RN-03) --------------------------------------


def confirmar_pago(reserva_id: int) -> dict:
    """La solicitud se convierte en reserva real. Es un acto manual y deliberado."""
    reserva = repositorio.obtener_reserva(reserva_id)
    if reserva is None:
        raise reglas.ReglaViolada("RN-03", "La reserva no existe.")
    if reserva["estado"] != reglas.PENDIENTE_PAGO:
        raise reglas.ReglaViolada(
            "RN-03",
            f"Solo se puede confirmar el pago de una reserva pendiente "
            f"(esta está {reserva['estado']}).",
        )
    if reglas.esta_vencida(
        reserva["estado"], reglas.desde_iso(reserva["vence_en"]), reglas.ahora()
    ):
        raise reglas.ReglaViolada(
            "RN-02", "La ventana de pago de esta reserva ya venció; el bloque se liberó."
        )
    return repositorio.actualizar_reserva(
        reserva_id, {"estado": reglas.PAGADA, "pagada_en": reglas.a_iso(reglas.ahora())}
    )


def cancelar_reserva(reserva_id: int) -> dict:
    """Cancelación administrativa: libera el bloque y **no** genera falta."""
    reserva = repositorio.obtener_reserva(reserva_id)
    if reserva is None:
        raise reglas.ReglaViolada("RN-03", "La reserva no existe.")
    if reserva["estado"] not in reglas.ESTADOS_VIGENTES:
        raise reglas.ReglaViolada(
            "RN-03", f"No se puede cancelar una reserva {reserva['estado']}."
        )
    return repositorio.actualizar_reserva(reserva_id, {"estado": reglas.CANCELADA})


def desbloquear_cliente(cliente_id: int) -> None:
    """
    Acción manual del administrador. En la PoC el desbloqueo no borra las
    faltas, así que el cliente vuelve a bloquearse en el próximo barrido: es
    justamente el hallazgo que el MVP corrige con faltas `vigentes`.
    """
    repositorio.marcar_cliente_bloqueado(cliente_id, False)


def reservas_ordenadas() -> list[dict]:
    """Todas las reservas, con cancha y cliente resueltos, de la más nueva a la más vieja."""
    canchas = {c["id"]: c for c in repositorio.listar_canchas(solo_activas=False)}
    clientes = {c["id"]: c for c in repositorio.listar_clientes()}
    filas = []
    for reserva in repositorio.listar_reservas():
        filas.append(
            {
                **reserva,
                "inicio_dt": reglas.desde_iso(reserva["inicio"]),
                "fin_dt": reglas.desde_iso(reserva["fin"]),
                "vence_dt": reglas.desde_iso(reserva["vence_en"]),
                "cancha": canchas.get(reserva["cancha_id"], {}),
                "cliente": clientes.get(reserva["cliente_id"], {}),
                "es_pendiente": reserva["estado"] == reglas.PENDIENTE_PAGO,
                "es_vigente": reserva["estado"] in reglas.ESTADOS_VIGENTES,
            }
        )
    return sorted(filas, key=lambda fila: fila["id"], reverse=True)
