"""De la curva de luz a la distancia / from light curve to distance.

La cadena completa, en el orden en que se le explica a la clase:

1. Del gráfico salen el **máximo** ``m_max`` y **Δm15**.
2. Δm15 se pasa a la banda B (los astrónomos definieron Phillips en B).
3. Phillips convierte Δm15(B) en la **luminosidad real** ``M_B``.
4. Se descuenta el polvo de nuestra propia galaxia.
5. ``μ = m − M`` es el **módulo de distancia**, y de ahí sale la distancia.
6. Se compara con la ley de Hubble, que usa el corrimiento al rojo.

El paso 2 y el término de color del paso 3 se saltan en el nivel "estudiante":
ahí la supernova es una vela estándar pura, ``M_B = −19,3``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Literal

from .calibracion import Calibracion, CalibracionSurvey, cargar
from .fotometria import Fotometria

Nivel = Literal["estudiante", "docente"]

#: 1 pársec en años luz
ANIOS_LUZ_POR_PARSEC = 3.261563777


@dataclass
class Distancia:
    nivel: Nivel
    #: Δm15 medido en la banda del survey (sistema en reposo)
    dm15_banda: float
    error_dm15_banda: float
    #: Δm15 convertido a la banda B, o ``None`` en nivel estudiante
    dm15_B: float | None
    #: magnitud aparente en el máximo, en la banda del survey
    m_banda: float
    #: magnitud aparente en el máximo convertida a B y corregida por polvo
    m_B_corregida: float
    #: extinción galáctica aplicada, en magnitudes
    A_B: float
    #: magnitud absoluta según Phillips (o la vela estándar)
    M_B: float
    #: módulo de distancia
    mu: float
    error_mu: float
    distancia_mpc: float
    error_distancia_mpc: float
    distancia_anios_luz: float
    #: distancia según la ley de Hubble, para comparar (sólo si hay z)
    distancia_hubble_mpc: float | None
    diferencia_porcentual: float | None
    avisos: list[str]

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def modulo_a_mpc(mu: float) -> float:
    """μ = 5·log10(d/10 pc)  ⇒  d en megapársecs."""
    return 10.0 ** ((mu + 5.0) / 5.0) / 1.0e6


def mpc_a_modulo(d_mpc: float) -> float:
    return 5.0 * math.log10(d_mpc * 1.0e6) - 5.0


def distancia_hubble(z: float, cal: Calibracion | None = None) -> float:
    """Ley de Hubble, con la corrección relativista de primer orden.

    ``d ≈ (c/H₀)·z·(1 + z/2)``.  A los corrimientos al rojo de este proyecto
    (z < 0,1) el término extra cambia el resultado en menos de un 5 %, pero lo
    dejamos porque es gratis y evita un sesgo sistemático visible.
    """
    cal = cal or cargar()
    return (cal.c_km_s / cal.H0) * z * (1.0 + z / 2.0)


def calcular(
    foto: Fotometria,
    *,
    survey: str = "ZTF",
    nivel: Nivel = "docente",
    ebv: float = 0.0,
    z: float | None = None,
    cal: Calibracion | None = None,
) -> Distancia:
    """Calcula la distancia a la supernova a partir de la fotometría medida.

    Parameters
    ----------
    foto:
        Salida de :func:`backend.fotometria.medir`.
    nivel:
        ``"estudiante"`` usa una vela estándar pura (``M_B = −19,3``), sin
        conversión de banda ni término de color: es el camino de una sola
        ecuación que se hace en clase.  ``"docente"`` aplica toda la cadena.
    ebv:
        Enrojecimiento galáctico E(B−V) en la línea de visión (de IRSA).
    """
    cal = cal or cargar()
    scal: CalibracionSurvey = cal.survey(survey)
    avisos = list(foto.avisos)
    z = z if z is not None else foto.z

    dm15 = foto.dm15.dm15
    err_dm15 = foto.dm15.error_dm15
    m_banda = foto.maximo.mag_max
    err_m = foto.maximo.error_mag_max

    A_B = scal.R_B * ebv

    if nivel == "estudiante":
        # Vela estándar: todas las SN Ia brillan igual en el máximo.
        dm15_B = None
        M_B = cal.M_B_0
        m_B = m_banda - A_B
        # el error de M_B es la dispersión intrínseca de suponerlas todas iguales
        err_M = 0.35
    else:
        dm15_B = scal.dm15_B(dm15)
        M_B = cal.M_B(dm15_B)
        m_B = scal.m_B(m_banda, foto.color_max) - A_B
        if foto.color_max is None:
            avisos.append(
                "Sin color en el máximo: la conversión g→B se hizo sólo con el "
                "término constante, así que la distancia es menos precisa."
            )
        err_M = math.hypot(
            cal.dispersion_phillips,
            cal.pendiente * scal.b * (err_dm15 if err_dm15 == err_dm15 else 0.1),
        )

    mu = m_B - M_B
    err_mu = math.hypot(err_m if err_m == err_m else 0.05, err_M)

    d_mpc = modulo_a_mpc(mu)
    # dd/d = ln(10)/5 · dμ
    err_d = d_mpc * math.log(10.0) / 5.0 * err_mu

    d_hubble = distancia_hubble(z, cal) if z and z > 0 else None
    dif = (
        100.0 * (d_mpc - d_hubble) / d_hubble
        if d_hubble not in (None, 0)
        else None
    )

    if cal.sin_calibrar:
        avisos.append(
            "La calibración todavía no se ha generado; se están usando valores "
            "por defecto. Corre scripts/calibrar_dm15.py."
        )

    return Distancia(
        nivel=nivel,
        dm15_banda=dm15,
        error_dm15_banda=err_dm15,
        dm15_B=dm15_B,
        m_banda=m_banda,
        m_B_corregida=m_B,
        A_B=A_B,
        M_B=M_B,
        mu=mu,
        error_mu=err_mu,
        distancia_mpc=d_mpc,
        error_distancia_mpc=err_d,
        distancia_anios_luz=d_mpc * 1.0e6 * ANIOS_LUZ_POR_PARSEC,
        distancia_hubble_mpc=d_hubble,
        diferencia_porcentual=dif,
        avisos=avisos,
    )
