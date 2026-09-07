"""
Rutas del proyecto.

Django ya no sirve HTML de la aplicación: eso lo hace la SPA de React. Aquí
quedan la API REST y el Django Admin, que sigue siendo el panel de gestión del
recinto (M-04, M-05).
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

admin.site.site_header = "Administración · Arriendo de canchas"
admin.site.site_title = "Arriendo de canchas"
admin.site.index_title = "Gestión del recinto"


def raiz(_request):
    """Punto de entrada: dice dónde está cada cosa."""
    return JsonResponse(
        {
            "nombre": "API · Arriendo de canchas de fútbol",
            "version": "3.0 (eva3 · DRF + React)",
            "api": "/api/",
            "admin": "/admin/",
            "front": "http://localhost:5173 (deno task dev en frontend/)",
        }
    )


urlpatterns = [
    path("", raiz),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("api-auth/", include("rest_framework.urls")),
]
