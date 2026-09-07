"""
Traducción de las reglas de negocio a respuestas HTTP.

`reglas.ReglaViolada` no es un error de programación ni de validación de
formato: es el sistema diciendo que la operación está prohibida por el negocio.
Se responde **409 Conflict** con el identificador de la regla, para que la SPA
pueda mostrar el mensaje y, si quiere, reaccionar distinto según cuál falló.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from reservas.reglas import ReglaViolada


def manejador_de_errores(exc, context):
    if isinstance(exc, ReglaViolada):
        return Response(
            {
                "detail": str(exc).split("] ", 1)[-1],
                "regla": exc.regla,
                "codigo": "regla_violada",
            },
            status=status.HTTP_409_CONFLICT,
        )

    respuesta = exception_handler(exc, context)
    if respuesta is not None and isinstance(respuesta.data, dict):
        respuesta.data.setdefault("codigo", respuesta.status_code)
    return respuesta
