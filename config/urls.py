from django.contrib import admin
from django.urls import include, path

# El Django Admin (M-04) es el panel de gestión del recinto.
admin.site.site_header = "Administración · Arriendo de canchas"
admin.site.site_title = "Arriendo de canchas"
admin.site.index_title = "Gestión del recinto"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("reservas.urls")),
]
