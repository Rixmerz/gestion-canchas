"""
Capa de persistencia de la PoC: archivos JSON en `data/`.

Aquí no hay ORM ni base de datos. Cada archivo se lee completo, se modifica en
memoria y se reescribe de forma atómica. Es suficiente para una PoC de un solo
proceso y deja en evidencia por qué el MVP necesita SQLite3.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from django.conf import settings

ARCHIVO_CANCHAS = "canchas.json"
ARCHIVO_CLIENTES = "clientes.json"
ARCHIVO_RESERVAS = "reservas.json"


def _ruta(nombre: str) -> Path:
    return Path(settings.DIRECTORIO_DATOS) / nombre


def _leer(nombre: str) -> dict:
    with _ruta(nombre).open(encoding="utf-8") as archivo:
        return json.load(archivo)


def _escribir(nombre: str, contenido: dict) -> None:
    """Escritura atómica: archivo temporal + rename, para no dejar JSON a medias."""
    destino = _ruta(nombre)
    destino.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=destino.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(contenido, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
        os.replace(temporal, destino)
    except Exception:
        Path(temporal).unlink(missing_ok=True)
        raise


# --- Canchas ----------------------------------------------------------------


def listar_canchas(solo_activas: bool = True) -> list[dict]:
    canchas = _leer(ARCHIVO_CANCHAS)["canchas"]
    return [c for c in canchas if c["activa"]] if solo_activas else canchas


def obtener_cancha(cancha_id: int) -> dict | None:
    return next((c for c in listar_canchas(solo_activas=False) if c["id"] == cancha_id), None)


def horario_recinto() -> dict:
    """Apertura, cierre y duración del bloque, definidos en `canchas.json`."""
    return _leer(ARCHIVO_CANCHAS)["horario"]


# --- Clientes ---------------------------------------------------------------


def listar_clientes() -> list[dict]:
    return _leer(ARCHIVO_CLIENTES)["clientes"]


def obtener_cliente(cliente_id: int) -> dict | None:
    return next((c for c in listar_clientes() if c["id"] == cliente_id), None)


def guardar_clientes(clientes: list[dict]) -> None:
    _escribir(ARCHIVO_CLIENTES, {"clientes": clientes})


def marcar_cliente_bloqueado(cliente_id: int, bloqueado: bool) -> None:
    clientes = listar_clientes()
    for cliente in clientes:
        if cliente["id"] == cliente_id:
            cliente["bloqueado"] = bloqueado
    guardar_clientes(clientes)


# --- Reservas y faltas ------------------------------------------------------


def _libro() -> dict:
    """El archivo `reservas.json` completo: reservas, faltas y el correlativo."""
    return _leer(ARCHIVO_RESERVAS)


def _guardar_libro(libro: dict) -> None:
    _escribir(ARCHIVO_RESERVAS, libro)


def listar_reservas() -> list[dict]:
    return _libro()["reservas"]


def listar_faltas() -> list[dict]:
    return _libro()["faltas"]


def obtener_reserva(reserva_id: int) -> dict | None:
    return next((r for r in listar_reservas() if r["id"] == reserva_id), None)


def crear_reserva(datos: dict) -> dict:
    libro = _libro()
    libro["secuencia"] += 1
    datos = {"id": libro["secuencia"], **datos}
    libro["reservas"].append(datos)
    _guardar_libro(libro)
    return datos


def actualizar_reserva(reserva_id: int, cambios: dict) -> dict | None:
    libro = _libro()
    actualizada = None
    for reserva in libro["reservas"]:
        if reserva["id"] == reserva_id:
            reserva.update(cambios)
            actualizada = reserva
    if actualizada is not None:
        _guardar_libro(libro)
    return actualizada


def registrar_falta(falta: dict) -> dict:
    libro = _libro()
    libro["secuencia_faltas"] = libro.get("secuencia_faltas", 0) + 1
    falta = {"id": libro["secuencia_faltas"], **falta}
    libro["faltas"].append(falta)
    _guardar_libro(libro)
    return falta


def aplicar_vencimientos(reservas_vencidas: list[dict], faltas: list[dict]) -> None:
    """
    Escribe en una sola pasada el resultado del barrido de vencimientos:
    marca las reservas como VENCIDA y agrega sus faltas.
    """
    if not reservas_vencidas:
        return
    libro = _libro()
    vencidas_por_id = {r["id"]: r for r in reservas_vencidas}
    for reserva in libro["reservas"]:
        if reserva["id"] in vencidas_por_id:
            reserva.update(vencidas_por_id[reserva["id"]])
    for falta in faltas:
        libro["secuencia_faltas"] = libro.get("secuencia_faltas", 0) + 1
        libro["faltas"].append({"id": libro["secuencia_faltas"], **falta})
    _guardar_libro(libro)
