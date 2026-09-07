"""
Serializadores de la API.

Ninguno de ellos contiene reglas de negocio: la validación de RN-01, RN-02,
RN-05 y RN-06 sigue viviendo en `reservas.servicios`, que es lo que hace que la
migración a REST no cambie el comportamiento del MVP.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from reservas import reglas
from reservas.models import Cancha, Falta, Reserva, Usuario


class CanchaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Cancha
        fields = ("id", "nombre", "tipo", "tipo_display", "superficie", "precio_hora", "activa")


class UsuarioResumenSerializer(serializers.ModelSerializer):
    """Datos mínimos de un cliente para embeber en otra respuesta."""

    nombre = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ("id", "username", "nombre")

    def get_nombre(self, usuario):
        return usuario.get_full_name() or usuario.username


class PerfilSerializer(serializers.ModelSerializer):
    """Quién soy y qué puedo hacer: lo que la SPA necesita para pintarse."""

    nombre = serializers.SerializerMethodField()
    es_administrador = serializers.BooleanField(read_only=True)
    faltas_vigentes = serializers.IntegerField(read_only=True)
    faltas_restantes = serializers.IntegerField(read_only=True)
    limite_faltas = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            "id",
            "username",
            "nombre",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "rol",
            "es_administrador",
            "bloqueado",
            "bloqueado_en",
            "faltas_vigentes",
            "faltas_restantes",
            "limite_faltas",
        )

    def get_nombre(self, usuario):
        return usuario.get_full_name() or usuario.username

    def get_limite_faltas(self, _usuario):
        return reglas.FALTAS_PARA_BLOQUEO


class RegistroSerializer(serializers.ModelSerializer):
    """M-02: alta de cliente. El rol se fuerza; nadie se registra como administrador."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Repetir contraseña")

    class Meta:
        model = Usuario
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telefono",
            "password",
            "password2",
        )
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "email": {"required": True},
        }

    def validate(self, datos):
        if datos["password"] != datos.pop("password2"):
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        return datos

    def create(self, datos):
        clave = datos.pop("password")
        usuario = Usuario(**datos, rol=Usuario.Rol.CLIENTE, is_staff=False, is_superuser=False)
        usuario.set_password(clave)
        usuario.save()
        return usuario


class ReservaSerializer(serializers.ModelSerializer):
    """Lectura de una reserva, con lo justo para pintarla sin más consultas."""

    cancha = CanchaSerializer(read_only=True)
    cliente = UsuarioResumenSerializer(read_only=True)
    confirmada_por = UsuarioResumenSerializer(read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    minutos_para_vencer = serializers.IntegerField(read_only=True)
    es_vigente = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reserva
        fields = (
            "id",
            "cancha",
            "cliente",
            "inicio",
            "fin",
            "estado",
            "estado_display",
            "es_vigente",
            "precio",
            "creada_en",
            "vence_en",
            "minutos_para_vencer",
            "pagada_en",
            "vencida_en",
            "confirmada_por",
        )


class SolicitudSerializer(serializers.Serializer):
    """M-08: la entrada del caso de uso central. Solo formato, sin reglas."""

    cancha = serializers.PrimaryKeyRelatedField(queryset=Cancha.objects.all())
    inicio = serializers.DateTimeField()


class BloqueSerializer(serializers.Serializer):
    """Un casillero de la agenda (M-07)."""

    inicio = serializers.DateTimeField()
    fin = serializers.DateTimeField()
    disponible = serializers.BooleanField()
    a_tiempo = serializers.BooleanField()
    estado = serializers.SerializerMethodField()
    reserva_id = serializers.SerializerMethodField()

    def get_estado(self, bloque):
        if bloque["ocupante"] is not None:
            return bloque["ocupante"].estado
        return "LIBRE" if bloque["a_tiempo"] else "FUERA_DE_PLAZO"

    def get_reserva_id(self, bloque):
        return bloque["ocupante"].pk if bloque["ocupante"] is not None else None


class FaltaSerializer(serializers.ModelSerializer):
    cliente = UsuarioResumenSerializer(read_only=True)
    cancha = serializers.CharField(source="reserva.cancha.nombre", read_only=True)

    class Meta:
        model = Falta
        fields = ("id", "cliente", "reserva", "cancha", "motivo", "registrada_en", "vigente")


class ResumenFaltasSerializer(serializers.ModelSerializer):
    """M-14: una fila por cliente con faltas vigentes."""

    nombre = serializers.SerializerMethodField()
    total_faltas = serializers.IntegerField(read_only=True)
    faltas_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Usuario
        fields = ("id", "username", "nombre", "email", "total_faltas", "faltas_restantes", "bloqueado")

    def get_nombre(self, usuario):
        return usuario.get_full_name() or usuario.username
