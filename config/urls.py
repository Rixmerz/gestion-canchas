from django.urls import include, path

urlpatterns = [
    path("", include("canchas.urls")),
]
