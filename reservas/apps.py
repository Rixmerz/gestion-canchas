from django.apps import AppConfig


class ReservasConfig(AppConfig):
    name = "reservas"
    verbose_name = "Arriendo de canchas"

    def ready(self):
        from django.db.models.signals import post_migrate

        from .permisos import crear_grupo_administradores

        post_migrate.connect(crear_grupo_administradores, sender=self)
