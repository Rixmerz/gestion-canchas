from django.urls import path

from . import views

app_name = "canchas"

urlpatterns = [
    path("", views.agenda, name="agenda"),
    path("cliente/", views.elegir_cliente, name="elegir_cliente"),
    path("solicitar/", views.solicitar, name="solicitar"),
    path("gestion/", views.gestion, name="gestion"),
    path("gestion/<int:reserva_id>/pagar/", views.confirmar_pago, name="confirmar_pago"),
    path("gestion/<int:reserva_id>/cancelar/", views.cancelar, name="cancelar"),
    path("faltas/", views.faltas, name="faltas"),
    path("faltas/<int:cliente_id>/desbloquear/", views.desbloquear, name="desbloquear"),
]
