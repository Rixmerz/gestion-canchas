"""Vistas de la PoC. Sin login: el "cliente actual" se elige en un selector."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from . import reglas, repositorio, servicios

CLAVE_CLIENTE = "cliente_id"


def _cliente_actual(request: HttpRequest) -> dict | None:
    clientes = repositorio.listar_clientes()
    if not clientes:
        return None
    elegido = request.session.get(CLAVE_CLIENTE, clientes[0]["id"])
    return repositorio.obtener_cliente(elegido) or clientes[0]


def _dia_pedido(request: HttpRequest) -> date:
    crudo = request.GET.get("fecha")
    if crudo:
        try:
            return date.fromisoformat(crudo)
        except ValueError:
            pass
    return reglas.ahora().date()


def agenda(request: HttpRequest) -> HttpResponse:
    """Disponibilidad de una cancha para un día, en hora de Santiago."""
    servicios.vencer_reservas_pendientes()

    canchas = repositorio.listar_canchas()
    if not canchas:
        return render(request, "canchas/agenda.html", {"canchas": []})

    try:
        cancha_id = int(request.GET.get("cancha", canchas[0]["id"]))
    except ValueError:
        cancha_id = canchas[0]["id"]
    cancha = repositorio.obtener_cancha(cancha_id) or canchas[0]

    dia = _dia_pedido(request)
    cliente = _cliente_actual(request)
    faltas = servicios.contar_faltas_por_cliente().get(cliente["id"], 0) if cliente else 0

    return render(
        request,
        "canchas/agenda.html",
        {
            "canchas": canchas,
            "cancha": cancha,
            "dia": dia,
            "dia_anterior": dia - timedelta(days=1),
            "dia_siguiente": dia + timedelta(days=1),
            "hoy": reglas.ahora(),
            "bloques": servicios.bloques_del_dia(cancha["id"], dia),
            "clientes": repositorio.listar_clientes(),
            "cliente": cliente,
            "faltas_cliente": faltas,
            "limite_faltas": reglas.FALTAS_PARA_BLOQUEO,
        },
    )


def elegir_cliente(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        try:
            request.session[CLAVE_CLIENTE] = int(request.POST["cliente_id"])
        except (KeyError, ValueError):
            messages.error(request, "Cliente inválido.")
    return redirect(request.POST.get("volver_a") or "canchas:agenda")


def solicitar(request: HttpRequest) -> HttpResponse:
    """RN-01, RN-02, RN-05 y RN-06 se validan aquí, en el servidor."""
    if request.method != "POST":
        return redirect("canchas:agenda")

    cliente = _cliente_actual(request)
    if cliente is None:
        messages.error(request, "No hay clientes cargados en data/clientes.json.")
        return redirect("canchas:agenda")

    try:
        cancha_id = int(request.POST["cancha_id"])
        inicio = reglas.desde_iso(request.POST["inicio"])
    except (KeyError, ValueError):
        messages.error(request, "Datos de la solicitud incompletos o mal formados.")
        return redirect("canchas:agenda")

    try:
        reserva = servicios.solicitar_reserva(cliente["id"], cancha_id, inicio)
    except reglas.ReglaViolada as error:
        messages.error(request, str(error))
    else:
        vence = reglas.desde_iso(reserva["vence_en"]).strftime("%H:%M")
        messages.success(
            request,
            f"Solicitud #{reserva['id']} creada para las "
            f"{reglas.desde_iso(reserva['inicio']).strftime('%d-%m %H:%M')}. "
            f"Queda PENDIENTE DE PAGO hasta las {vence}; si no se paga, se libera "
            f"el bloque y se registra una falta.",
        )

    destino = f"{request.POST.get('volver_a', '/')}"
    return redirect(destino or "canchas:agenda")


def gestion(request: HttpRequest) -> HttpResponse:
    """Pantalla del administrador: confirmar pagos y cancelar."""
    vencidas = servicios.vencer_reservas_pendientes()
    if vencidas:
        messages.warning(
            request,
            f"{vencidas} reserva(s) vencieron por falta de pago y generaron su falta (RN-04).",
        )
    return render(
        request,
        "canchas/gestion.html",
        {
            "reservas": servicios.reservas_ordenadas(),
            "ahora": reglas.ahora(),
        },
    )


def confirmar_pago(request: HttpRequest, reserva_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("canchas:gestion")
    try:
        servicios.confirmar_pago(reserva_id)
    except reglas.ReglaViolada as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request, f"Reserva #{reserva_id} PAGADA. El bloque queda tomado en firme."
        )
    return redirect("canchas:gestion")


def cancelar(request: HttpRequest, reserva_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("canchas:gestion")
    try:
        servicios.cancelar_reserva(reserva_id)
    except reglas.ReglaViolada as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Reserva #{reserva_id} cancelada; el bloque quedó libre.")
    return redirect("canchas:gestion")


def faltas(request: HttpRequest) -> HttpResponse:
    """Vista de faltas: quién no paga y quién ya está bloqueado (RN-05)."""
    servicios.vencer_reservas_pendientes()
    return render(
        request,
        "canchas/faltas.html",
        {
            "filas": servicios.resumen_de_faltas(),
            "detalle": _detalle_de_faltas(),
            "limite": reglas.FALTAS_PARA_BLOQUEO,
        },
    )


def _detalle_de_faltas() -> list[dict]:
    clientes = {c["id"]: c for c in repositorio.listar_clientes()}
    return [
        {
            **falta,
            "cliente": clientes.get(falta["cliente_id"], {}),
            "registrada_dt": reglas.desde_iso(falta["registrada_en"]),
        }
        for falta in sorted(repositorio.listar_faltas(), key=lambda f: f["id"], reverse=True)
    ]


def desbloquear(request: HttpRequest, cliente_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("canchas:faltas")
    servicios.desbloquear_cliente(cliente_id)
    messages.info(
        request,
        "Cliente desbloqueado. Ojo: en la PoC las faltas no se anulan, así que "
        "el próximo barrido lo vuelve a bloquear (el MVP lo resuelve con faltas vigentes).",
    )
    return redirect("canchas:faltas")
