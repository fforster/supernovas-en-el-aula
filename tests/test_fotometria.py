"""Pruebas del medidor de curvas de luz."""

from __future__ import annotations

import math

import pytest

from backend import fotometria as F
from backend.brokers.base import CurvaDeLuz, Deteccion
from tests.conftest import curva_sintetica


def test_encuentra_el_maximo_conocido():
    curva = curva_sintetica(mag_max=16.0)
    foto = F.medir(curva, z=0.02, n_bootstrap=0)
    assert foto.maximo.t_max == pytest.approx(20.0, abs=1.0)
    assert foto.maximo.mag_max == pytest.approx(16.0, abs=0.1)


@pytest.mark.parametrize("dm15", [0.85, 1.0, 1.35])
def test_recupera_dm15(dm15):
    curva = curva_sintetica(dm15=dm15)
    foto = F.medir(curva, z=0.02, n_bootstrap=0)
    assert foto.dm15.dm15 == pytest.approx(dm15, abs=0.12)


def test_dm15_se_mide_en_el_sistema_en_reposo():
    """A mayor z, los 15 días en reposo son más días observados.

    Si el código ignorara la dilatación temporal, un mismo Δm15 intrínseco
    saldría medido más grande a alto z. Con la corrección, el valor no cambia.
    """
    valores = [
        F.medir(curva_sintetica(z=z, dm15=1.0), z=z, n_bootstrap=0).dm15.dm15
        for z in (0.01, 0.08)
    ]
    assert valores[0] == pytest.approx(valores[1], abs=0.05)


def test_color_en_el_maximo():
    curva = curva_sintetica()
    foto = F.medir(curva, z=0.02, n_bootstrap=0)
    # la banda r se construyó 0,15 mag más débil
    assert foto.color_max == pytest.approx(-0.15, abs=0.05)


def test_el_bootstrap_entrega_incertidumbres_finitas():
    curva = curva_sintetica(ruido=0.05)
    foto = F.medir(curva, z=0.02, n_bootstrap=60)
    assert math.isfinite(foto.maximo.error_mag_max)
    assert math.isfinite(foto.dm15.error_dm15)
    assert foto.dm15.error_dm15 > 0


def test_un_punto_aislado_no_se_confunde_con_el_maximo():
    """Regresión: la estimación inicial tomaba el punto más brillante a secas.

    Un único punto espurio y solitario dejaba la ventana de ajuste casi vacía y
    la medición fallaba (o peor, medía en el lugar equivocado).
    """
    curva = curva_sintetica()
    curva.detecciones.append(
        Deteccion(mjd=200.0, banda="g", mag=10.0, error=0.02)  # imposible, aislado
    )
    foto = F.medir(curva, z=0.02, n_bootstrap=0)
    assert foto.maximo.t_max == pytest.approx(20.0, abs=1.5)


def test_recorte_sigma_ignora_un_punto_malo():
    curva = curva_sintetica()
    curva.detecciones.append(Deteccion(mjd=22.0, banda="g", mag=19.5, error=0.02))
    foto = F.medir(curva, z=0.02, n_bootstrap=0)
    assert foto.maximo.mag_max == pytest.approx(16.0, abs=0.2)


def test_se_niega_a_medir_sin_cobertura_despues_del_maximo():
    """Sin datos a los 15 días del máximo, Δm15 sería una extrapolación.

    Preferimos negarnos y decirlo, antes que entregarle al docente un número
    inventado que parece medido.
    """
    curva = curva_sintetica()
    # el máximo (día 20) queda bien definido, pero t_max + 15(1+z) = 35,3 no
    curva.detecciones = [d for d in curva.detecciones if d.mjd <= 31.0]
    with pytest.raises(F.MedicionImposible, match="15 días"):
        F.medir(curva, z=0.02, n_bootstrap=0)


def test_se_niega_cuando_la_supernova_se_descubrio_despues_del_maximo():
    """Caso real y frecuente: sólo se observó la bajada.

    Sin ningún punto antes del máximo no hay pico que ajustar, y el mínimo del
    polinomio se va al borde de la ventana. Hay que decirlo, no inventarlo.
    """
    curva = curva_sintetica()
    curva.detecciones = [d for d in curva.detecciones if d.mjd >= 30.0]
    with pytest.raises(F.MedicionImposible, match="cobertura"):
        F.medir(curva, z=0.02, n_bootstrap=0)


def test_se_niega_a_medir_sin_corrimiento_al_rojo():
    with pytest.raises(F.MedicionImposible, match="corrimiento al rojo"):
        F.medir(curva_sintetica(), z=0.0, n_bootstrap=0)


def test_se_niega_con_muy_pocos_puntos():
    curva = CurvaDeLuz(
        oid="x",
        survey="test",
        detecciones=[
            Deteccion(mjd=float(i), banda="g", mag=16.0, error=0.02) for i in range(3)
        ],
    )
    with pytest.raises(F.MedicionImposible):
        F.medir(curva, z=0.02, n_bootstrap=0)
