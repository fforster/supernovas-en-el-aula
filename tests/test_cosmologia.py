"""Pruebas de la cadena Δm15 → luminosidad → distancia."""

from __future__ import annotations

import math

import pytest

from backend import cosmologia as C
from backend import fotometria as F
from backend.calibracion import cargar
from tests.conftest import curva_sintetica


def test_ida_y_vuelta_del_modulo_de_distancia():
    for d in (10.0, 75.0, 300.0):
        assert C.modulo_a_mpc(C.mpc_a_modulo(d)) == pytest.approx(d, rel=1e-9)


def test_modulo_de_distancia_conocido():
    # 10 pc  ->  mu = 0 por definición
    assert C.mpc_a_modulo(1e-5) == pytest.approx(0.0, abs=1e-9)
    # 10 Mpc ->  mu = 30
    assert C.mpc_a_modulo(10.0) == pytest.approx(30.0, abs=1e-9)


def test_ley_de_hubble():
    cal = cargar()
    # a z pequeño la corrección relativista es despreciable
    assert C.distancia_hubble(0.001, cal) == pytest.approx(
        cal.c_km_s * 0.001 / cal.H0, rel=2e-3
    )
    # y siempre crece con z
    assert C.distancia_hubble(0.05) > C.distancia_hubble(0.02)


def test_phillips_las_lentas_son_mas_luminosas():
    """Menor Δm15 (se apaga más lento) debe dar una magnitud absoluta más negativa."""
    cal = cargar()
    assert cal.M_B(0.9) < cal.M_B(1.4)


def test_la_correccion_de_dm15_cambia_la_distancia():
    curva = curva_sintetica(mag_max=16.0, dm15=1.4)
    foto = F.medir(curva, z=0.03, n_bootstrap=0)
    est = C.calcular(foto, nivel="estudiante", ebv=0.0, z=0.03)
    doc = C.calcular(foto, nivel="docente", ebv=0.0, z=0.03)
    assert est.dm15_B is None and doc.dm15_B is not None
    assert doc.distancia_mpc != pytest.approx(est.distancia_mpc, rel=1e-3)


def test_la_extincion_acerca_la_supernova():
    """Si parte del brillo se lo comió el polvo, la supernova está más cerca."""
    curva = curva_sintetica()
    foto = F.medir(curva, z=0.03, n_bootstrap=0)
    sin_polvo = C.calcular(foto, ebv=0.0, z=0.03).distancia_mpc
    con_polvo = C.calcular(foto, ebv=0.2, z=0.03).distancia_mpc
    assert con_polvo < sin_polvo


def test_mas_brillante_es_mas_cerca():
    d = []
    for mag in (15.0, 17.0):
        foto = F.medir(curva_sintetica(mag_max=mag), z=0.03, n_bootstrap=0)
        d.append(C.calcular(foto, ebv=0.0, z=0.03).distancia_mpc)
    assert d[0] < d[1]
    # 2 magnitudes = factor 10^(2/5) en distancia
    assert d[1] / d[0] == pytest.approx(10 ** (2 / 5), rel=0.02)


def test_las_incertidumbres_se_propagan():
    curva = curva_sintetica(ruido=0.05)
    foto = F.medir(curva, z=0.03, n_bootstrap=60)
    dist = C.calcular(foto, ebv=0.0, z=0.03)
    assert math.isfinite(dist.error_distancia_mpc)
    assert dist.error_distancia_mpc > 0


def test_hay_calibracion_generada():
    """Si esto falla, alguien subió el repo sin correr scripts/calibrar_dm15.py."""
    cal = cargar()
    assert not cal.sin_calibrar, "falta generar data/calibracion.json"
    scal = cal.survey("ZTF")
    # la conversión g -> B debe ser una relación creciente y de pendiente ~1
    assert 0.7 < scal.b < 1.2
    assert scal.dm15_B(1.2) > scal.dm15_B(0.9)


def test_la_formula_del_estudiante_es_la_del_backend(tmp_path):
    """El sitio estático calcula en JavaScript: no puede divergir del backend.

    Sin servidor, la aritmética final del estudiante corre en el navegador
    (``frontend/js/rutas.js``). Es la única física duplicada del proyecto, así
    que aquí se ejecuta ese JavaScript de verdad con node y se compara contra
    ``backend``. Si alguien toca los coeficientes o una fórmula en un solo lado,
    esta prueba se cae.
    """
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado")

    raiz = Path(__file__).resolve().parent.parent
    cal = cargar()
    casos = [
        {"dm15": 0.85, "magMax": 15.5, "z": 0.02, "ebv": 0.03},
        {"dm15": 1.10, "magMax": 17.0, "z": 0.045, "ebv": 0.0},
        {"dm15": 1.55, "magMax": 18.2, "z": 0.068, "ebv": 0.12},
    ]

    guion = tmp_path / "parity.mjs"
    guion.write_text(
        "globalThis.document = { documentElement: { dataset: {} },"
        " baseURI: 'http://localhost/' };\n"
        f"const m = await import({json.dumps((raiz / 'frontend/js/rutas.js').as_uri())});\n"
        f"const cal = {json.dumps(cal.crudo)};\n"
        f"const casos = {json.dumps(casos)};\n"
        "console.log(JSON.stringify(casos.map((c) => m.calcularLocal({\n"
        "  dm15: c.dm15, magMax: c.magMax,\n"
        "  ficha: { survey: 'ZTF', z: c.z, ebv: c.ebv }, calibracion: cal,\n"
        "}))));\n",
        encoding="utf-8",
    )
    salida = subprocess.run(
        [node, str(guion)], capture_output=True, text=True, timeout=60, check=True
    )
    en_js = json.loads(salida.stdout)

    scal = cal.survey("ZTF")
    for caso, js in zip(casos, en_js):
        dm15_B = scal.dm15_B(caso["dm15"])
        M_B = cal.M_B(dm15_B)
        mu = scal.m_B(caso["magMax"], None) - scal.R_B * caso["ebv"] - M_B
        assert js["tu_resultado"]["dm15_B"] == pytest.approx(dm15_B, rel=1e-9)
        assert js["tu_resultado"]["M_B"] == pytest.approx(M_B, rel=1e-9)
        assert js["tu_resultado"]["mu"] == pytest.approx(mu, rel=1e-9)
        assert js["tu_resultado"]["distancia_mpc"] == pytest.approx(
            C.modulo_a_mpc(mu), rel=1e-9
        )
        assert js["respuesta"]["distancia_hubble_mpc"] == pytest.approx(
            C.distancia_hubble(caso["z"], cal), rel=1e-9
        )
