from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("solicitar/", views.solicitar, name="solicitar"),
    path("mis-reservas/", views.mis_reservas, name="mis_reservas"),
    path("faltas/", views.panel_faltas, name="faltas"),
    path("registro/", views.registro, name="registro"),
    path("ingresar/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
