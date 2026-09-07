"""
Django Admin: el panel de gestión del recinto (M-04, M-05).

Desde aquí el administrador confirma pagos (M-12), cancela, revisa las faltas
(M-14) y desbloquea clientes. No se construyó un back-office propio: usar el
admin es justamente lo que hace que el MVP sea mínimo.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from . import reglas, servicios
from .models import Cancha, Falta, Reserva, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "nombre", "email", "rol", "faltas", "estado_bloqueo")
    list_filter = ("rol", "bloqueado", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    actions = ("accion_desbloquear", "accion_bloquear")

    fieldsets = UserAdmin.fieldsets + (
        (
            "Arriendo de canchas",
            {
                "fields": ("rol", "telefono", "bloqueado", "bloqueado_en"),
                "description": (
                    "El bloqueo lo activa el sistema al acumular "
                    f"{reglas.FALTAS_PARA_BLOQUEO} faltas vigentes (RN-05). "
                    "Para desbloquear, usar la acción de la lista: además anula las "
                    "faltas, si no el cliente vuelve a bloquearse en el próximo barrido."
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Arriendo de canchas", {"fields": ("rol", "telefono")}),
    )
    readonly_fields = ("bloqueado_en",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(total_faltas=Count("faltas", filter=Q(faltas__vigente=True)))
        )

    @admin.display(description="nombre")
    def nombre(self, usuario):
        return usuario.get_full_name() or "—"

    @admin.display(description="faltas vigentes", ordering="total_faltas")
    def faltas(self, usuario):
        total = usuario.total_faltas
        color = "#b00" if total >= reglas.FALTAS_PARA_BLOQUEO else "#666"
        return format_html(
            '<b style="color:{}">{}</b> / {}', color, total, reglas.FALTAS_PARA_BLOQUEO
        )

    @admin.display(description="estado", boolean=False)
    def estado_bloqueo(self, usuario):
        if usuario.bloqueado:
            return format_html('<b style="color:#b00">BLOQUEADO</b>')
        return "Habilitado"

    @admin.action(description="Desbloquear y anular sus faltas vigentes")
    def accion_desbloquear(self, request, queryset):
        for usuario in queryset:
            servicios.desbloquear(usuario, anular_faltas=True)
        self.message_user(
            request,
            f"{queryset.count()} cliente(s) desbloqueado(s); sus faltas quedaron anuladas "
            "pero se conservan como historial.",
            messages.SUCCESS,
        )

    @admin.action(description="Bloquear manualmente")
    def accion_bloquear(self, request, queryset):
        queryset.update(bloqueado=True, bloqueado_en=timezone.now())
        self.message_user(request, f"{queryset.count()} cliente(s) bloqueado(s).", messages.WARNING)


@admin.register(Cancha)
class CanchaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "superficie", "precio_hora", "activa")
    list_filter = ("tipo", "activa")
    list_editable = ("precio_hora", "activa")
    search_fields = ("nombre",)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cancha",
        "cliente",
        "bloque",
        "estado_coloreado",
        "vence",
        "precio",
        "confirmada_por",
    )
    list_display_links = ("id", "cancha")
    list_filter = ("estado", "cancha", "inicio")
    search_fields = ("cliente__username", "cliente__first_name", "cliente__last_name")
    date_hierarchy = "inicio"
    autocomplete_fields = ("cliente",)
    readonly_fields = ("creada_en", "vence_en", "pagada_en", "vencida_en", "confirmada_por")
    actions = ("accion_confirmar_pago", "accion_cancelar")

    @admin.display(description="bloque", ordering="inicio")
    def bloque(self, reserva):
        inicio = timezone.localtime(reserva.inicio)
        fin = timezone.localtime(reserva.fin)
        return f"{inicio:%d/%m/%Y %H:%M} – {fin:%H:%M}"

    @admin.display(description="estado", ordering="estado")
    def estado_coloreado(self, reserva):
        colores = {
            Reserva.Estado.PENDIENTE_PAGO: "#b8860b",
            Reserva.Estado.PAGADA: "#1a7f37",
            Reserva.Estado.VENCIDA: "#b00",
            Reserva.Estado.CANCELADA: "#666",
        }
        return format_html(
            '<b style="color:{}">{}</b>',
            colores.get(reserva.estado, "#000"),
            reserva.get_estado_display(),
        )

    @admin.display(description="vence")
    def vence(self, reserva):
        if not reserva.esta_pendiente:
            return "—"
        return f"{timezone.localtime(reserva.vence_en):%d/%m %H:%M}"

    @admin.action(description="Confirmar pago → la reserva pasa a ser real (RN-03)")
    def accion_confirmar_pago(self, request, queryset):
        confirmadas, rechazadas = 0, []
        for reserva in queryset:
            try:
                servicios.confirmar_pago(reserva, request.user)
            except reglas.ReglaViolada as error:
                rechazadas.append(f"#{reserva.pk}: {error}")
            else:
                confirmadas += 1
        if confirmadas:
            self.message_user(
                request, f"{confirmadas} reserva(s) marcada(s) como PAGADA.", messages.SUCCESS
            )
        for detalle in rechazadas:
            self.message_user(request, detalle, messages.ERROR)

    @admin.action(description="Cancelar (libera el bloque, no genera falta)")
    def accion_cancelar(self, request, queryset):
        canceladas = 0
        for reserva in queryset:
            try:
                servicios.cancelar_reserva(reserva)
            except reglas.ReglaViolada as error:
                self.message_user(request, str(error), messages.ERROR)
            else:
                canceladas += 1
        if canceladas:
            self.message_user(request, f"{canceladas} reserva(s) cancelada(s).", messages.SUCCESS)


@admin.register(Falta)
class FaltaAdmin(admin.ModelAdmin):
    """M-14: el registro de quién aparta bloques y no paga."""

    list_display = ("id", "cliente", "reserva", "motivo", "registrada", "vigente")
    list_filter = ("vigente", "registrada_en")
    search_fields = ("cliente__username", "cliente__first_name", "cliente__last_name")
    autocomplete_fields = ("cliente",)
    date_hierarchy = "registrada_en"

    @admin.display(description="registrada", ordering="registrada_en")
    def registrada(self, falta):
        return f"{timezone.localtime(falta.registrada_en):%d/%m/%Y %H:%M}"

    def has_add_permission(self, request):
        """Las faltas las registra el sistema al vencer una reserva (RN-04)."""
        return False
