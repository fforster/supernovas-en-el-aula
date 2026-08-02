"""Catálogo de supernovas del aula / classroom supernova catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "data" / "catalogo_snia.json"

#: Campos que **no** se le mandan al estudiante: son la respuesta del ejercicio.
SECRETOS = {
    "z",
    "z_fuente",
    "dm15_g",
    "error_dm15",
    "color_max",
    "mag_max",
    "t_max",
    "distancia_mpc",
    "distancia_hubble_mpc",
    "diferencia_porcentual",
}


class CatalogoVacio(RuntimeError):
    pass


@lru_cache(maxsize=1)
def cargar(ruta: str | Path | None = None) -> dict[str, Any]:
    archivo = Path(ruta) if ruta else ARCHIVO
    if not archivo.exists():
        raise CatalogoVacio(
            f"No existe {archivo}. Genéralo con: python3 scripts/curar_catalogo.py"
        )
    return json.loads(archivo.read_text(encoding="utf-8"))


def objetos() -> list[dict[str, Any]]:
    return cargar()["objetos"]


def buscar(oid: str) -> dict[str, Any] | None:
    return next((o for o in objetos() if o["oid"] == oid), None)


def resumen(idioma: str = "es", broker=None) -> list[dict[str, Any]]:
    """Lista para las tarjetas del navegador de objetos.

    No incluye nada que revele la respuesta: ni z ni la distancia.  Así el mismo
    endpoint sirve para las dos vistas.
    """
    salida = []
    for o in objetos():
        salida.append(
            {
                "oid": o["oid"],
                "nombre_sn": o["nombre_sn"],
                "host": o["host"],
                "dificultad": o["dificultad"],
                "n_g": o["n_g"],
                "n_r": o["n_r"],
                "candid_estampilla": o["candid_estampilla"],
                "estampillas": (
                    broker.urls_estampillas(o["oid"], o["candid_estampilla"])
                    if broker and o["candid_estampilla"]
                    else None
                ),
                "clasificacion": o["clasificacion"],
                "historia": o["textos"].get(idioma, o["textos"]["es"])["historia"],
            }
        )
    return salida


def para_estudiante(o: dict[str, Any], idioma: str = "es") -> dict[str, Any]:
    """La ficha sin las respuestas."""
    limpio = {k: v for k, v in o.items() if k not in SECRETOS}
    limpio["historia"] = o["textos"].get(idioma, o["textos"]["es"])["historia"]
    limpio.pop("textos", None)
    return limpio


def para_docente(o: dict[str, Any], idioma: str = "es") -> dict[str, Any]:
    completo = dict(o)
    completo["historia"] = o["textos"].get(idioma, o["textos"]["es"])["historia"]
    completo.pop("textos", None)
    return completo
