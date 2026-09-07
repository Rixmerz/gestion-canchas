"""
Vistas de la API REST.

Cada endpoint es una cáscara delgada sobre `reservas.servicios`: valida el
formato de entrada, delega el caso de uso y serializa el resultado. Las reglas
de negocio no se reimplementan aquí — es la única forma de que la migración a
REST no introduzca una segunda verdad.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reservas import reglas, servicios
from reservas.models import Cancha, Falta, Reserva, Usuario

from .permisos import EsAdministradorDelRecinto, EsClienteDueno
from .serializers import (
    BloqueSerializer,
    CanchaSerializer,
    FaltaSerializer,
    PerfilSerializer,
    RegistroSerializer,
    ReservaSerializer,
    ResumenFaltasSerializer,
    SolicitudSerializer,
)


# --- Autenticación (M-02) ---------------------------------------------------


def _respuesta_de_sesion(usuario: Usuario, codigo=status.HTTP_200_OK) -> Response:
    token, _ = Token.objects.get_or_create(user=usuario)
    return Response(
        {"token": token.key, "perfil": PerfilSerializer(usuario).data}, status=codigo
    )


class RegistroView(APIView):
    """POST /api/auth/registro/ — crea un cliente y devuelve su token."""

    permission_classes = [AllowAny]
    serializer_class = RegistroSerializer

    def post(self, request):
        serializador = RegistroSerializer(data=request.data)
        serializador.is_valid(raise_exception=True)
        return _respuesta_de_sesion(serializador.save(), status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ — devuelve el token y el perfil de quien ingresa."""

    permission_classes = [AllowAny]

    def post(self, request):
        usuario = authenticate(
            request,
            username=request.data.get("username", ""),
            password=request.data.get("password", ""),
        )
        if usuario is None:
            return Response(
                {"detail": "Usuario o contraseña incorrectos.", "codigo": "credenciales"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return _respuesta_de_sesion(usuario)


class LogoutView(APIView):
    """POST /api/auth/logout/ — invalida el token actual."""

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class YoView(APIView):
    """GET /api/auth/yo/ — perfil, rol, faltas y estado de bloqueo."""

    def get(self, request):
        servicios.vencer_reservas_pendientes()
        request.user.refresh_from_db()
        return Response(PerfilSerializer(request.user).data)


# --- Canchas (M-06) ---------------------------------------------------------


class CanchaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /api/canchas/ — catálogo público de canchas activas."""

    serializer_class = CanchaSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        canchas = Cancha.objects.all()
        if self.request.query_params.get("todas") != "1":
            canchas = canchas.filter(activa=True)
        return canchas


# --- Agenda (M-07) ----------------------------------------------------------


class AgendaView(APIView):
    """
    GET /api/agenda/?cancha=<id>&fecha=<YYYY-MM-DD>

    Devuelve la grilla del día en hora de Santiago. Es pública: mirar la
    disponibilidad no exige cuenta; solicitar, sí.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        servicios.vencer_reservas_pendientes()

        canchas = Cancha.objects.filter(activa=True)
        if not canchas.exists():
            return Response({"detail": "No hay canchas activas."}, status=status.HTTP_404_NOT_FOUND)

        try:
            cancha = canchas.get(pk=int(request.query_params.get("cancha", 0)))
        except (Cancha.DoesNotExist, ValueError):
            cancha = canchas.first()

        try:
            dia = date.fromisoformat(request.query_params["fecha"])
        except (KeyError, ValueError):
            dia = timezone.localdate()

        bloques = servicios.bloques_del_dia(cancha, dia)
        return Response(
            {
                "cancha": CanchaSerializer(cancha).data,
                "fecha": dia.isoformat(),
                "ahora": timezone.localtime().isoformat(),
                "zona_horaria": str(reglas.ZONA),
                "anticipacion_minima_min": int(
                    reglas.ANTICIPACION_MINIMA.total_seconds() // 60
                ),
                "bloques": BloqueSerializer(bloques, many=True).data,
            }
        )


# --- Reservas (M-08, M-12, M-17) --------------------------------------------


class ReservaViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """
    GET  /api/reservas/                      mis reservas (todas, si soy administrador)
    POST /api/reservas/                      solicitar un bloque (M-08)
    POST /api/reservas/{id}/confirmar-pago/  confirmar el pago (M-12, solo administrador)
    POST /api/reservas/{id}/cancelar/        cancelar (solo administrador)
    """

    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated, EsClienteDueno]

    def get_queryset(self):
        servicios.vencer_reservas_pendientes()
        reservas = Reserva.objects.select_related("cancha", "cliente", "confirmada_por")
        if not self.request.user.es_administrador:
            return reservas.filter(cliente=self.request.user)
        if self.request.query_params.get("estado"):
            reservas = reservas.filter(estado=self.request.query_params["estado"])
        return reservas

    def create(self, request, *args, **kwargs):
        entrada = SolicitudSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        reserva = servicios.solicitar_reserva(
            request.user, entrada.validated_data["cancha"], entrada.validated_data["inicio"]
        )
        return Response(ReservaSerializer(reserva).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="confirmar-pago",
        permission_classes=[IsAuthenticated, EsAdministradorDelRecinto],
    )
    def confirmar_pago(self, request, pk=None):
        reserva = servicios.confirmar_pago(self.get_object(), request.user)
        return Response(ReservaSerializer(reserva).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, EsAdministradorDelRecinto],
    )
    def cancelar(self, request, pk=None):
        reserva = servicios.cancelar_reserva(self.get_object())
        return Response(ReservaSerializer(reserva).data)

    def get_object(self):
        """Un administrador puede actuar sobre cualquier reserva, no solo las suyas."""
        if self.request.user.es_administrador:
            objeto = Reserva.objects.select_related("cancha", "cliente").get(pk=self.kwargs["pk"])
            self.check_object_permissions(self.request, objeto)
            return objeto
        return super().get_object()


# --- Faltas (M-14, M-15) ----------------------------------------------------


class FaltaViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/faltas/ — detalle de faltas registradas (solo administradores)."""

    serializer_class = FaltaSerializer
    permission_classes = [IsAuthenticated, EsAdministradorDelRecinto]

    def get_queryset(self):
        servicios.vencer_reservas_pendientes()
        faltas = Falta.objects.select_related("cliente", "reserva", "reserva__cancha")
        if self.request.query_params.get("vigentes") == "1":
            faltas = faltas.filter(vigente=True)
        return faltas


class ResumenFaltasView(APIView):
    """GET /api/faltas/resumen/ — clientes con faltas, de más a menos (M-14)."""

    permission_classes = [IsAuthenticated, EsAdministradorDelRecinto]

    def get(self, request):
        servicios.vencer_reservas_pendientes()
        return Response(
            {
                "limite_faltas": reglas.FALTAS_PARA_BLOQUEO,
                "clientes": ResumenFaltasSerializer(servicios.resumen_de_faltas(), many=True).data,
            }
        )


class DesbloquearClienteView(APIView):
    """
    POST /api/clientes/{id}/desbloquear/ — habilita al cliente y anula sus
    faltas vigentes, para que el próximo barrido no lo vuelva a bloquear.
    """

    permission_classes = [IsAuthenticated, EsAdministradorDelRecinto]

    def post(self, request, pk):
        try:
            cliente = Usuario.objects.get(pk=pk, rol=Usuario.Rol.CLIENTE)
        except Usuario.DoesNotExist:
            return Response(
                {"detail": "Cliente no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )
        servicios.desbloquear(cliente, anular_faltas=True)
        cliente.refresh_from_db()
        return Response(PerfilSerializer(cliente).data)
