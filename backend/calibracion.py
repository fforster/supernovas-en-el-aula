"""Carga de la calibración / calibration loading.

Todas las constantes físicas del proyecto viven en ``data/calibracion.json``,
que produce ``scripts/calibrar_dm15.py``.  Ningún número mágico debería estar
escrito a mano en el resto del código.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "data" / "calibracion.json"

#: Valores de emergencia, por si la calibración todavía no se ha generado.
#: Son la relación de Phillips clásica y una conversión de banda neutra
#: (identidad), que la app señala como "sin calibrar".
POR_DEFECTO: dict[str, Any] = {
    "generado": None,
    "sin_calibrar": True,
    "H0": 70.0,
    "H0_unidades": "km/s/Mpc",
    "c_km_s": 299792.458,
    "phillips": {
        "M_B_0": -19.3,
        "pendiente": 0.6,
        "dm15_ref": 1.1,
        "dispersion": 0.20,
        "fuente": "Phillips et al. (1999), forma simplificada para el aula",
    },
    "surveys": {
        "ZTF": {
            "banda": "g",
            "banda_color": "r",
            "dm15": {"a": 0.0, "b": 1.0, "dispersion": 0.15},
            "color": {"c0": 0.0, "c1": 0.0, "dispersion": 0.15},
            "R_B": 4.1,
        }
    },
}


@dataclass(frozen=True)
class CalibracionSurvey:
    """Coeficientes de un survey concreto."""

    survey: str
    banda: str
    banda_color: str
    #: Δm15(B) = a + b · Δm15(banda, en reposo)
    a: float
    b: float
    dispersion_dm15: float
    #: m_B(máx) = m_banda(máx) + c0 + c1 · color(máx)
    c0: float
    c1: float
    dispersion_color: float
    #: A_B / E(B−V), para pasar el enrojecimiento galáctico a extinción en B
    R_B: float

    def dm15_B(self, dm15_banda: float) -> float:
        return self.a + self.b * dm15_banda

    def m_B(self, m_banda: float, color: float | None) -> float:
        if color is None:
            return m_banda + self.c0
        return m_banda + self.c0 + self.c1 * color


@dataclass(frozen=True)
class Calibracion:
    H0: float
    c_km_s: float
    M_B_0: float
    pendiente: float
    dm15_ref: float
    dispersion_phillips: float
    sin_calibrar: bool
    generado: str | None
    crudo: dict[str, Any]

    def survey(self, nombre: str) -> CalibracionSurvey:
        bloque = self.crudo["surveys"].get(nombre)
        if bloque is None:
            disponibles = ", ".join(sorted(self.crudo["surveys"]))
            raise KeyError(
                f"No hay calibración para el survey {nombre!r}. "
                f"Disponibles: {disponibles}. "
                "Genera una con scripts/calibrar_dm15.py."
            )
        return CalibracionSurvey(
            survey=nombre,
            banda=bloque["banda"],
            banda_color=bloque["banda_color"],
            a=float(bloque["dm15"]["a"]),
            b=float(bloque["dm15"]["b"]),
            dispersion_dm15=float(bloque["dm15"]["dispersion"]),
            c0=float(bloque["color"]["c0"]),
            c1=float(bloque["color"]["c1"]),
            dispersion_color=float(bloque["color"]["dispersion"]),
            R_B=float(bloque.get("R_B", 4.1)),
        )

    def M_B(self, dm15_B: float) -> float:
        """Relación ancho–luminosidad de Phillips."""
        return self.M_B_0 + self.pendiente * (dm15_B - self.dm15_ref)


@lru_cache(maxsize=1)
def cargar(ruta: str | Path | None = None) -> Calibracion:
    archivo = Path(ruta) if ruta else ARCHIVO
    if archivo.exists():
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    else:
        datos = POR_DEFECTO
    ph = datos["phillips"]
    return Calibracion(
        H0=float(datos["H0"]),
        c_km_s=float(datos["c_km_s"]),
        M_B_0=float(ph["M_B_0"]),
        pendiente=float(ph["pendiente"]),
        dm15_ref=float(ph["dm15_ref"]),
        dispersion_phillips=float(ph["dispersion"]),
        sin_calibrar=bool(datos.get("sin_calibrar", False)),
        generado=datos.get("generado"),
        crudo=datos,
    )
