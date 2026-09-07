"""
Grupo de permisos del **administrador normal** (M-05).

Un encargado de recinto no debe ser superusuario: se le marca `is_staff`, se le
pone rol ADMIN y se le agrega a este grupo, que le da acceso al Django Admin
solo sobre lo que necesita para gestionar el arriendo.

El grupo se crea (o se actualiza) automáticamente después de cada `migrate`.
"""

from django.apps import apps as django_apps

NOMBRE_GRUPO = "Administradores de recinto"

#: (modelo, acciones permitidas)
PERMISOS = {
    "cancha": ("add", "change", "delete", "view"),
    "reserva": ("add", "change", "view"),  # borrar reservas destruiría el historial
    "falta": ("change", "view"),  # las crea el sistema al vencer (RN-04)
    "usuario": ("add", "change", "view"),  # para desbloquear clientes
}


def crear_grupo_administradores(sender=None, **kwargs):
    Group = django_apps.get_model("auth", "Group")
    Permission = django_apps.get_model("auth", "Permission")

    grupo, _ = Group.objects.get_or_create(name=NOMBRE_GRUPO)
    codigos = [
        f"{accion}_{modelo}" for modelo, acciones in PERMISOS.items() for accion in acciones
    ]
    grupo.permissions.set(
        Permission.objects.filter(
            content_type__app_label="reservas", codename__in=codigos
        )
    )
    return grupo
