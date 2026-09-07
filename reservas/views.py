"""
Vistas del MVP.

La agenda es pública (M-07); solicitar exige sesión iniciada (M-02, M-08) y el
panel de faltas exige rol administrador (M-03, M-14). La gestión operativa
—confirmar pagos y cancelar— vive en el Django Admin (M-04, M-12).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import reglas, servicios
from .forms import RegistroClienteForm
from .models import Cancha, Falta, Reserva


def _solo_administradores(request: HttpRequest) -> None:
    if not request.user.is_authenticated or not request.user.es_administrador:
        raise PermissionDenied("Esta sección es solo para administradores del recinto.")


def _dia_pedido(request: HttpRequest) -> date:
    crudo = request.GET.get("fecha")
    if crudo:
        try:
            return date.fromisoformat(crudo)
        except ValueError:
            pass
    return timezone.localdate()


# --- M-07: agenda de disponibilidad -----------------------------------------


def agenda(request: HttpRequest) -> HttpResponse:
    servicios.vencer_reservas_pendientes()

    canchas = Cancha.objects.filter(activa=True)
    if not canchas.exists():
        return render(request, "reservas/agenda.html", {"canchas": canchas})

    try:
        cancha = canchas.get(pk=int(request.GET.get("cancha", 0)))
    except (Cancha.DoesNotExist, ValueError):
        cancha = canchas.first()

    dia = _dia_pedido(request)
    return render(
        request,
        "reservas/agenda.html",
        {
            "seccion": "agenda",
            "canchas": canchas,
            "cancha": cancha,
            "dia": dia,
            "dia_anterior": dia - timedelta(days=1),
            "dia_siguiente": dia + timedelta(days=1),
            "ahora": timezone.localtime(),
            "bloques": servicios.bloques_del_dia(cancha, dia),
            "limite_faltas": reglas.FALTAS_PARA_BLOQUEO,
        },
    )


# --- M-08: solicitar --------------------------------------------------------


@login_required
def solicitar(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("reservas:agenda")

    volver_a = request.POST.get("volver_a") or "/"
    try:
        cancha = Cancha.objects.get(pk=int(request.POST["cancha_id"]))
        inicio = reglas.desde_iso(request.POST["inicio"])
    except (KeyError, ValueError, Cancha.DoesNotExist):
        messages.error(request, "Datos de la solicitud incompletos o mal formados.")
        return redirect(volver_a)

    try:
        reserva = servicios.solicitar_reserva(request.user, cancha, inicio)
    except reglas.ReglaViolada as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"Solicitud #{reserva.pk} creada para el "
            f"{timezone.localtime(reserva.inicio):%d/%m a las %H:%M}. Queda PENDIENTE DE PAGO "
            f"hasta las {timezone.localtime(reserva.vence_en):%H:%M}: paga y pide al "
            "administrador que confirme, o se libera el bloque y se te registra una falta.",
        )
    return redirect(volver_a)


# --- M-17: mis reservas -----------------------------------------------------


@login_required
def mis_reservas(request: HttpRequest) -> HttpResponse:
    servicios.vencer_reservas_pendientes()
    return render(
        request,
        "reservas/mis_reservas.html",
        {
            "seccion": "mis_reservas",
            "reservas": Reserva.objects.filter(cliente=request.user).select_related("cancha"),
            "faltas": request.user.faltas.filter(vigente=True).select_related("reserva"),
            "limite_faltas": reglas.FALTAS_PARA_BLOQUEO,
        },
    )


# --- M-14: vista de faltas (solo administradores) ---------------------------


def panel_faltas(request: HttpRequest) -> HttpResponse:
    _solo_administradores(request)
    servicios.vencer_reservas_pendientes()
    return render(
        request,
        "reservas/faltas.html",
        {
            "seccion": "faltas",
            "clientes": servicios.resumen_de_faltas(),
            "faltas": Falta.objects.select_related("cliente", "reserva", "reserva__cancha")[:50],
            "limite_faltas": reglas.FALTAS_PARA_BLOQUEO,
            "pendientes": Reserva.objects.pendientes()
            .select_related("cancha", "cliente")
            .order_by("vence_en"),
        },
    )


# --- M-02: registro ---------------------------------------------------------


def registro(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("reservas:agenda")

    formulario = RegistroClienteForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        login(request, usuario)
        messages.success(request, f"Bienvenido, {usuario.first_name}. Ya puedes reservar.")
        return redirect("reservas:agenda")

    return render(request, "reservas/registro.html", {"formulario": formulario})
