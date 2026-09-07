"""
Modelo relacional del MVP (M-01).

Cuatro entidades: `Usuario` (con rol y estado de bloqueo), `Cancha`, `Reserva`
y `Falta`. Los estados y umbrales viven en `reglas.py`, no aquí: el modelo los
importa para que exista un solo lugar donde cambiar una regla de negocio.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from . import reglas


class Usuario(AbstractUser):
    """
    Usuario del sistema (M-02, M-03).

    Un solo modelo para los dos perfiles. `rol` decide qué puede hacer;
    `bloqueado` implementa RN-05 y lo administra el sistema, no el usuario.
    """

    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        CLIENTE = "CLIENTE", "Cliente"

    rol = models.CharField(
        "rol", max_length=10, choices=Rol.choices, default=Rol.CLIENTE
    )
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    bloqueado = models.BooleanField(
        "bloqueado",
        default=False,
        help_text=f"Se activa solo al acumular {reglas.FALTAS_PARA_BLOQUEO} faltas vigentes (RN-05).",
    )
    bloqueado_en = models.DateTimeField("bloqueado el", null=True, blank=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def es_administrador(self) -> bool:
        """Superusuario o usuario con rol ADMIN (M-05)."""
        return self.is_superuser or self.rol == self.Rol.ADMIN

    def faltas_vigentes(self) -> int:
        return self.faltas.filter(vigente=True).count()

    def faltas_restantes(self) -> int:
        return max(reglas.FALTAS_PARA_BLOQUEO - self.faltas_vigentes(), 0)


class Cancha(models.Model):
    """Inventario que se arrienda (M-06)."""

    class Tipo(models.TextChoices):
        BABY = "BABY", "Baby fútbol"
        FUTBOL_7 = "F7", "Fútbol 7"
        FUTBOL_11 = "F11", "Fútbol 11"

    nombre = models.CharField("nombre", max_length=80, unique=True)
    tipo = models.CharField("tipo", max_length=4, choices=Tipo.choices, default=Tipo.FUTBOL_7)
    superficie = models.CharField("superficie", max_length=60, blank=True)
    precio_hora = models.PositiveIntegerField(
        "precio por hora (CLP)", validators=[MinValueValidator(1)]
    )
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "cancha"
        verbose_name_plural = "canchas"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class ReservaQuerySet(models.QuerySet):
    def vigentes(self):
        """Las que ocupan el bloque: pendientes de pago y pagadas (RN-06)."""
        return self.filter(estado__in=Reserva.ESTADOS_VIGENTES)

    def pendientes(self):
        return self.filter(estado=Reserva.Estado.PENDIENTE_PAGO)

    def por_vencer(self, referencia=None):
        """Pendientes cuyo plazo de pago ya pasó (RN-04)."""
        return self.pendientes().filter(vence_en__lte=referencia or timezone.now())


class Reserva(models.Model):
    """
    Solicitud de arriendo de un bloque.

    Nace como `PENDIENTE_PAGO` (un "hold") y solo se convierte en reserva real
    cuando el administrador confirma el pago (RN-03).
    """

    class Estado(models.TextChoices):
        PENDIENTE_PAGO = reglas.PENDIENTE_PAGO, "Pendiente de pago"
        PAGADA = reglas.PAGADA, "Pagada"
        VENCIDA = reglas.VENCIDA, "Vencida"
        CANCELADA = reglas.CANCELADA, "Cancelada"

    ESTADOS_VIGENTES = list(reglas.ESTADOS_VIGENTES)

    cancha = models.ForeignKey(
        Cancha, on_delete=models.PROTECT, related_name="reservas", verbose_name="cancha"
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas",
        verbose_name="cliente",
    )
    inicio = models.DateTimeField("inicio del bloque")
    fin = models.DateTimeField("fin del bloque")
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO
    )
    precio = models.PositiveIntegerField("precio cobrado (CLP)")

    creada_en = models.DateTimeField("solicitada el", default=timezone.now)
    vence_en = models.DateTimeField(
        "vence el", help_text="RN-02: min(solicitada + 30 min, inicio del bloque)."
    )
    pagada_en = models.DateTimeField("pagada el", null=True, blank=True)
    vencida_en = models.DateTimeField("vencida el", null=True, blank=True)
    confirmada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagos_confirmados",
        verbose_name="pago confirmado por",
        help_text="RN-03: qué administrador validó el pago.",
    )

    objects = ReservaQuerySet.as_manager()

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-inicio"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fin__gt=models.F("inicio")),
                name="reserva_fin_posterior_al_inicio",
            ),
            # Barrera en la base de datos contra la doble reserva del mismo
            # bloque. La validación completa de solapamiento vive en el
            # servicio; esto cubre la carrera del caso exacto.
            models.UniqueConstraint(
                fields=["cancha", "inicio"],
                condition=models.Q(estado__in=list(reglas.ESTADOS_VIGENTES)),
                name="una_reserva_vigente_por_cancha_y_bloque",
            ),
        ]
        indexes = [
            models.Index(fields=["cancha", "inicio"]),
            models.Index(fields=["estado", "vence_en"]),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} · {self.cancha} · {timezone.localtime(self.inicio):%d/%m %H:%M}"

    @property
    def es_vigente(self) -> bool:
        return self.estado in self.ESTADOS_VIGENTES

    @property
    def esta_pendiente(self) -> bool:
        return self.estado == self.Estado.PENDIENTE_PAGO

    @property
    def minutos_para_vencer(self) -> int | None:
        """Cuánto le queda al cliente para pagar, en minutos."""
        if not self.esta_pendiente:
            return None
        restante = reglas.diferencia(self.vence_en, timezone.now())
        return max(int(restante.total_seconds() // 60), 0)


class Falta(models.Model):
    """
    Registro de incumplimiento (M-14).

    Una falta por reserva no pagada — la relación es uno a uno para que un
    barrido repetido no pueda duplicarla.
    """

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="faltas",
        verbose_name="cliente",
    )
    reserva = models.OneToOneField(
        Reserva, on_delete=models.CASCADE, related_name="falta", verbose_name="reserva"
    )
    motivo = models.CharField("motivo", max_length=200)
    registrada_en = models.DateTimeField("registrada el", default=timezone.now)
    vigente = models.BooleanField(
        "vigente",
        default=True,
        help_text="Solo las faltas vigentes cuentan para el bloqueo (RN-05).",
    )

    class Meta:
        verbose_name = "falta"
        verbose_name_plural = "faltas"
        ordering = ["-registrada_en"]
        indexes = [models.Index(fields=["cliente", "vigente"])]

    def __str__(self) -> str:
        return f"Falta de {self.cliente} · reserva #{self.reserva_id}"
