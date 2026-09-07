"""Permisos de la API. Traducen M-03 al mundo REST."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class EsAdministradorDelRecinto(BasePermission):
    """Solo superusuarios o usuarios con rol ADMIN (M-05)."""

    message = "Esta operación es solo para administradores del recinto."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.es_administrador
        )


class EsClienteDueno(BasePermission):
    """RN-08: el cliente solo ve y toca lo suyo; el administrador ve todo."""

    message = "Solo puedes consultar tus propias reservas."

    def has_object_permission(self, request, view, obj):
        if request.user.es_administrador:
            return True
        return obj.cliente_id == request.user.pk and request.method in SAFE_METHODS
