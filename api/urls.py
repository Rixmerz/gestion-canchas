"""Rutas de la API REST."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("canchas", views.CanchaViewSet, basename="cancha")
router.register("reservas", views.ReservaViewSet, basename="reserva")
router.register("faltas", views.FaltaViewSet, basename="falta")

app_name = "api"

urlpatterns = [
    path("auth/registro/", views.RegistroView.as_view(), name="registro"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/yo/", views.YoView.as_view(), name="yo"),
    path("agenda/", views.AgendaView.as_view(), name="agenda"),
    # Antes del router: /faltas/resumen/ no es el detalle de una falta.
    path("faltas/resumen/", views.ResumenFaltasView.as_view(), name="faltas-resumen"),
    path(
        "clientes/<int:pk>/desbloquear/",
        views.DesbloquearClienteView.as_view(),
        name="desbloquear",
    ),
    path("", include(router.urls)),
]
