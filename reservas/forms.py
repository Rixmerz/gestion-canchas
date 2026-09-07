"""Formularios del MVP: registro de cliente (M-02)."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


class RegistroClienteForm(UserCreationForm):
    """
    Alta de un cliente. El rol se fuerza a CLIENTE: nadie se registra como
    administrador desde la web (M-03).
    """

    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellido", max_length=150)
    email = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False)

    class Meta:
        model = Usuario
        fields = ("username", "first_name", "last_name", "email", "telefono")

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = Usuario.Rol.CLIENTE
        usuario.is_staff = False
        usuario.is_superuser = False
        if commit:
            usuario.save()
        return usuario
