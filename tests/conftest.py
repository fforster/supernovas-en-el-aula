"""Configuración común de las pruebas."""

from __future__ import annotations

import pytest

from backend.brokers.base import CurvaDeLuz, Deteccion


def pytest_addoption(parser):
    parser.addoption(
        "--red",
        action="store_true",
        default=False,
        help="ejecuta también las pruebas que consultan ALeRCE por internet",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "red: necesita internet (ALeRCE)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--red"):
        return
    saltar = pytest.mark.skip(reason="necesita internet; usa --red para incluirla")
    for item in items:
        if "red" in item.keywords:
            item.add_marker(saltar)


def curva_sintetica(
    z: float = 0.02,
    mag_max: float = 16.0,
    dm15: float = 1.0,
    cadencia: float = 2.0,
    ruido: float = 0.0,
    semilla: int = 7,
) -> CurvaDeLuz:
    """Curva de luz de juguete con un máximo conocido en el día 20.

    Es una parábola suave en la fase en reposo, con mínimo exacto en el máximo y
    que pasa exactamente por ``mag_max + dm15`` a los 15 días. Se eligió suave a
    propósito: una versión anterior pegaba una parábola de subida con una recta
    de bajada, y el quiebre en el máximo —que ninguna SN Ia real tiene— hacía
    que el ajuste polinómico subestimara Δm15. El realismo lo cubre la
    validación con SALT2 de ``scripts/calibrar_dm15.py``; esta curva sólo
    comprueba la mecánica del estimador.
    """
    import numpy as np

    rng = np.random.default_rng(semilla)
    t_max = 20.0
    dets = []
    for banda, desplazamiento in (("g", 0.0), ("r", 0.15)):
        t = np.arange(0.0, 60.0, cadencia)
        fase = (t - t_max) / (1 + z)
        mag = mag_max + (dm15 / 225.0) * fase**2 + desplazamiento
        for ti, mi in zip(t, mag):
            dets.append(
                Deteccion(
                    mjd=float(ti),
                    banda=banda,
                    mag=float(mi + (rng.normal(0, ruido) if ruido else 0.0)),
                    error=float(max(ruido, 0.02)),
                )
            )
    return CurvaDeLuz(oid="sintetica", survey="test", detecciones=dets)
