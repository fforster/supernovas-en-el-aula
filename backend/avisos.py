"""Advertencias traducibles / translatable warnings.

Las advertencias que el pipeline le manda al docente («no se pudo medir el
color», «Δm15 está al borde de los datos») nacen en Python, pero se leen en la
página, que puede estar en español o en inglés.  Si se generan como texto ya
escrito, salen siempre en el idioma en que las escribió quien programó — que fue
exactamente el error que había: la interfaz en inglés mostraba las advertencias
en español.

Por eso un aviso no es una frase sino un **código** más sus parámetros.  La
traducción vive junto al resto de los textos, en ``frontend/i18n/*.json``, bajo
la clave ``aviso.<codigo>``.

Se incluye además ``texto`` en español para quien consuma la API sin traducir
(los scripts de curación, un cuaderno de Python, el propio ``/docs``): así el
JSON se sigue entendiendo solo, pero la interfaz nunca lo usa.

Al añadir un aviso hay que añadir su clave en los DOS idiomas.  Hay una prueba
que lo comprueba (``test_todo_aviso_del_backend_esta_traducido``).
"""

from __future__ import annotations

from typing import Any

#: código -> plantilla en español, con los mismos {parámetros} que el i18n.
PLANTILLAS: dict[str, str] = {
    "sin_color": (
        "No se pudo medir el color {banda}−{banda_color} en el máximo; "
        "la distancia se calcula sin corrección de color."
    ),
    "dm15_al_borde": "Δm15 está apenas al borde de los datos: tómalo como aproximado.",
    "pocos_puntos_maximo": (
        "Sólo {n} mediciones definen el máximo; el resultado puede variar bastante."
    ),
    "conversion_sin_color": (
        "Sin color en el máximo: la conversión g→B se hizo sólo con el término "
        "constante, así que la distancia es menos precisa."
    ),
    "sin_calibrar": (
        "La calibración todavía no se ha generado; se están usando valores por "
        "defecto. Corre scripts/calibrar_dm15.py."
    ),
}


def aviso(codigo: str, **params: Any) -> dict[str, Any]:
    """Un aviso listo para viajar en el JSON.

    >>> aviso("pocos_puntos_maximo", n=5)["texto"]
    'Sólo 5 mediciones definen el máximo; el resultado puede variar bastante.'
    """
    if codigo not in PLANTILLAS:
        raise KeyError(f"Aviso desconocido: {codigo!r}. Añádelo a PLANTILLAS.")
    return {
        "codigo": codigo,
        "params": params,
        "texto": PLANTILLAS[codigo].format(**params),
    }
