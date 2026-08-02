"""Medición del máximo y de Δm15 / peak and Δm15 measurement.

Todo lo que mide la curva de luz vive aquí.  Es importante que este módulo sea
**el mismo** que usa ``scripts/calibrar_dm15.py``: así la calibración absorbe los
sesgos de nuestro propio estimador en vez de los de un estimador ideal.

Convenios / conventions
-----------------------
* Las magnitudes son de imagen diferencia (``magpsf``): más chico = más brillante.
* Los tiempos son MJD **observados**.  Δm15 se define en el sistema en reposo de
  la supernova, así que se evalúa en ``t_max + 15·(1+z)`` días observados.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Sequence

import numpy as np

from .brokers.base import CurvaDeLuz, Deteccion


class MedicionImposible(ValueError):
    """La curva de luz no alcanza para medir lo que se pide.

    El mensaje está en español y pensado para mostrarse tal cual al docente.
    """


# Ventanas de ajuste, en días **en reposo** alrededor del máximo.
ANTES = 12.0
DESPUES = 30.0
GRADO_MAX = 4
#: Cuán lejos puede estar la última detección del instante t_max+15 para que
#: todavía consideremos que Δm15 está medido y no extrapolado.
TOLERANCIA_COBERTURA = 3.0


@dataclass
class Maximo:
    banda: str
    t_max: float
    mag_max: float
    error_t_max: float
    error_mag_max: float
    n_puntos: int
    grado: int


@dataclass
class MedicionDm15:
    banda: str
    dm15: float
    error_dm15: float
    mag_15: float
    #: instante observado en que se evaluó (t_max + 15(1+z))
    t_15: float
    #: True si hay detecciones reales a ambos lados de t_15
    interpolado: bool


@dataclass
class Fotometria:
    """Todo lo medible directamente de la curva de luz, sin cosmología."""

    oid: str
    banda: str
    z: float
    maximo: Maximo
    dm15: MedicionDm15
    color_max: float | None
    error_color_max: float | None
    banda_color: str | None
    n_detecciones: dict[str, int]
    avisos: list[str]

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["maximo"] = asdict(self.maximo)
        d["dm15"] = asdict(self.dm15)
        return d


# --------------------------------------------------------------------- utilidades


def _arreglos(dets: Sequence[Deteccion]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.array([d.mjd for d in dets], float)
    m = np.array([d.mag for d in dets], float)
    e = np.array([d.error for d in dets], float)
    orden = np.argsort(t)
    # un piso en el error evita que un punto con sigma minúsculo domine el ajuste
    return t[orden], m[orden], np.clip(e[orden], 0.01, None)


def _primera_estimacion(t: np.ndarray, m: np.ndarray, e: np.ndarray, z: float) -> float:
    """Instante aproximado del máximo, robusto ante puntos aislados.

    Tomar sin más la detección más brillante es frágil: un único punto espurio
    lejos del pico deja la ventana de ajuste vacía.  En vez de eso suavizamos la
    curva con un núcleo gaussiano de 5 días (en reposo) y buscamos el mínimo del
    resultado, así que un punto solitario no puede ganar.
    """
    if len(t) < 3:
        return float(t[np.argmin(m)])
    ancho = 5.0 * (1 + z)
    pesos = np.exp(-0.5 * ((t[:, None] - t[None, :]) / ancho) ** 2) / e[None, :] ** 2
    suave = (pesos * m[None, :]).sum(axis=1) / pesos.sum(axis=1)

    # Descartamos épocas sin vecinos: un punto espurio y solitario no debe ganar.
    # La ventana de apoyo es el doble del núcleo, porque con una ventana de sólo
    # 5 días se descartaba el máximo real de SN 2019np, cuyos dos puntos más
    # brillantes están a 5,03 días de su vecino más cercano.
    apoyo = (np.abs(t[:, None] - t[None, :]) <= 2 * ancho).sum(axis=1)
    valido = apoyo >= 3
    if not valido.any():
        return float(t[np.argmin(m)])
    idx = np.flatnonzero(valido)
    return float(t[idx[np.argmin(suave[idx])]])


def _ajustar(
    t: np.ndarray,
    m: np.ndarray,
    e: np.ndarray,
    t0: float,
    z: float,
    recortar: bool = True,
) -> tuple[np.polynomial.Polynomial, np.ndarray]:
    """Polinomio de bajo orden en la ventana alrededor del máximo aproximado.

    Con ``recortar`` se hacen dos pasadas de recorte sigma (4σ) para que un punto
    malo que haya pasado los filtros del broker no tuerza el ajuste.
    """
    ventana = (t >= t0 - ANTES * (1 + z)) & (t <= t0 + DESPUES * (1 + z))
    n = int(ventana.sum())
    if n < 4:
        raise MedicionImposible(
            f"Sólo hay {n} mediciones cerca del máximo; se necesitan al menos 4."
        )

    usar = ventana.copy()
    p = None
    for pasada in range(3 if recortar else 1):
        k = int(usar.sum())
        if k < 4:
            usar = ventana.copy()
            k = n
        grado = min(GRADO_MAX, k - 2)
        x = t[usar] - t0
        # np.polynomial.Polynomial.fit usa pesos w tales que se minimiza residuo*w
        p = np.polynomial.Polynomial.fit(x, m[usar], grado, w=1.0 / e[usar])
        if not recortar or pasada == 2:
            break
        residuo = (m[usar] - p(x)) / e[usar]
        disp = 1.4826 * np.median(np.abs(residuo - np.median(residuo)))
        if not np.isfinite(disp) or disp <= 0:
            break
        buenos = np.abs(residuo - np.median(residuo)) <= 4.0 * disp
        if buenos.all():
            break
        nuevo = usar.copy()
        nuevo[np.flatnonzero(usar)[~buenos]] = False
        if int(nuevo.sum()) < 4:
            break
        usar = nuevo

    assert p is not None
    return p, usar


def buscar_maximo(
    curva: CurvaDeLuz, banda: str, z: float, n_bootstrap: int = 200
) -> tuple[Maximo, np.polynomial.Polynomial, float]:
    """Ajusta el máximo de la curva de luz en una banda.

    Devuelve el máximo, el polinomio ajustado y el origen de tiempos ``t0`` que
    usa ese polinomio (el polinomio está en ``t - t0``).
    """
    dets = curva.por_banda(banda)
    if len(dets) < 5:
        raise MedicionImposible(
            f"La banda {banda} tiene sólo {len(dets)} detecciones; se necesitan 5."
        )
    t, m, e = _arreglos(dets)
    t0 = _primera_estimacion(t, m, e, z)
    p, ventana = _ajustar(t, m, e, t0, z)

    t_max, mag_max = _vertice(p, z)
    grado = p.degree()

    # Incertidumbres por bootstrap paramétrico: repetimos el ajuste perturbando
    # cada medición dentro de su barra de error.
    rng = np.random.default_rng(20260801)
    t_boot, m_boot = [], []
    for _ in range(n_bootstrap):
        ruido = rng.normal(0.0, e)
        try:
            pb, _ = _ajustar(t, m + ruido, e, t0, z)
            tb, mb = _vertice(pb, z)
        except (MedicionImposible, ValueError):
            continue
        t_boot.append(tb)
        m_boot.append(mb)

    err_t = float(np.std(t_boot)) if len(t_boot) > 10 else float("nan")
    err_m = float(np.std(m_boot)) if len(m_boot) > 10 else float("nan")

    maximo = Maximo(
        banda=banda,
        t_max=float(t0 + t_max),
        mag_max=float(mag_max),
        error_t_max=err_t,
        error_mag_max=err_m,
        n_puntos=int(ventana.sum()),
        grado=int(grado),
    )
    return maximo, p, t0


def _vertice(p: np.polynomial.Polynomial, z: float) -> tuple[float, float]:
    """Mínimo en magnitud (= máximo de brillo) del polinomio, cerca de x=0.

    Se busca sobre una grilla fina restringida a ±8 días en reposo del punto más
    brillante, para que un polinomio de grado 4 no se vaya a un mínimo espurio en
    el borde de la ventana.
    """
    lim = 8.0 * (1 + z)
    x = np.linspace(-lim, lim, 1601)
    y = p(x)
    i = int(np.argmin(y))
    if i in (0, len(x) - 1):
        # el mínimo cae en el borde: la cobertura antes/después del máximo es mala
        raise MedicionImposible(
            "No se distingue el máximo: falta cobertura antes o después del pico."
        )
    return float(x[i]), float(y[i])


def medir_dm15(
    curva: CurvaDeLuz,
    banda: str,
    z: float,
    maximo: Maximo,
    p: np.polynomial.Polynomial,
    t0: float,
    n_bootstrap: int = 200,
) -> MedicionDm15:
    """Δm15: cuánto se apaga la supernova 15 días (en reposo) tras el máximo."""
    dets = curva.por_banda(banda)
    t, m, e = _arreglos(dets)

    dt = 15.0 * (1 + z)  # dilatación temporal: 15 días para la SN, más para nosotros
    t_15 = maximo.t_max + dt

    if t.max() < t_15 - TOLERANCIA_COBERTURA:
        raise MedicionImposible(
            "La curva de luz termina antes de 15 días después del máximo, "
            f"así que Δm15 no se puede medir (falta{t_15 - t.max():.0f} d)."
        )
    interpolado = bool((t > maximo.t_max).any() and t.max() >= t_15)

    mag_15 = float(p(t_15 - t0))
    dm15 = mag_15 - maximo.mag_max

    rng = np.random.default_rng(20260802)
    muestras = []
    for _ in range(n_bootstrap):
        ruido = rng.normal(0.0, e)
        try:
            pb, _ = _ajustar(t, m + ruido, e, t0, z)
            xb, yb = _vertice(pb, z)
            muestras.append(float(pb(xb + dt)) - yb)
        except (MedicionImposible, ValueError):
            continue
    err = float(np.std(muestras)) if len(muestras) > 10 else float("nan")

    if dm15 <= 0:
        raise MedicionImposible(
            "El ajuste da un Δm15 negativo (la supernova no se apaga). "
            "Probablemente la cobertura después del máximo es insuficiente."
        )

    return MedicionDm15(
        banda=banda,
        dm15=float(dm15),
        error_dm15=err,
        mag_15=mag_15,
        t_15=float(t_15),
        interpolado=interpolado,
    )


def color_en_maximo(
    curva: CurvaDeLuz, banda_a: str, banda_b: str, t_max: float, z: float
) -> tuple[float | None, float | None]:
    """Color (a − b) en el instante del máximo de la banda ``a``.

    Se interpola linealmente la banda ``b`` entre las detecciones que rodean
    ``t_max``.  Devuelve ``(None, None)`` si no hay con qué interpolar.
    """
    dets_a = curva.por_banda(banda_a)
    dets_b = curva.por_banda(banda_b)
    if len(dets_b) < 2 or not dets_a:
        return None, None

    tb, mb, eb = _arreglos(dets_b)
    cerca = np.abs(tb - t_max) <= 5.0 * (1 + z)
    if cerca.sum() < 2 or not (tb.min() <= t_max <= tb.max()):
        return None, None

    mag_b = float(np.interp(t_max, tb, mb))
    err_b = float(np.mean(eb[cerca]))

    ta, ma, ea = _arreglos(dets_a)
    mag_a = float(np.interp(t_max, ta, ma))
    cerca_a = np.abs(ta - t_max) <= 5.0 * (1 + z)
    err_a = float(np.mean(ea[cerca_a])) if cerca_a.any() else float(np.mean(ea))

    return mag_a - mag_b, math.hypot(err_a, err_b)


def medir(
    curva: CurvaDeLuz,
    z: float,
    banda: str = "g",
    banda_color: str | None = "r",
    n_bootstrap: int = 200,
) -> Fotometria:
    """Mide máximo, Δm15 y color en el máximo de una curva de luz."""
    if z is None or z <= 0:
        raise MedicionImposible(
            "Hace falta el corrimiento al rojo para corregir la dilatación temporal."
        )

    avisos: list[str] = []
    maximo, p, t0 = buscar_maximo(curva, banda, z, n_bootstrap)
    dm15 = medir_dm15(curva, banda, z, maximo, p, t0, n_bootstrap)

    color = err_color = None
    if banda_color:
        color, err_color = color_en_maximo(curva, banda, banda_color, maximo.t_max, z)
        if color is None:
            avisos.append(
                f"No se pudo medir el color {banda}−{banda_color} en el máximo; "
                "la distancia se calcula sin corrección de color."
            )

    if not dm15.interpolado:
        avisos.append(
            "Δm15 está apenas al borde de los datos: tómalo como aproximado."
        )
    if maximo.n_puntos < 8:
        avisos.append(
            f"Sólo {maximo.n_puntos} mediciones definen el máximo; "
            "el resultado puede variar bastante."
        )

    return Fotometria(
        oid=curva.oid,
        banda=banda,
        z=z,
        maximo=maximo,
        dm15=dm15,
        color_max=color,
        error_color_max=err_color,
        banda_color=banda_color if color is not None else None,
        n_detecciones={b: len(curva.por_banda(b)) for b in curva.bandas},
        avisos=avisos,
    )
