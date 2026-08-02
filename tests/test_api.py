"""Pruebas de la aplicación web."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import catalogo
from backend.app import app


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def oid():
    return catalogo.objetos()[0]["oid"]


def test_salud(cliente):
    d = cliente.get("/api/salud").json()
    assert d["ok"] is True
    assert d["supernovas"] > 0
    assert d["clasificador"] == "lc_classifier_BHRF_forced_phot"


def test_catalogo_no_revela_respuestas(cliente):
    d = cliente.get("/api/catalogo").json()
    assert d["objetos"]
    for o in d["objetos"]:
        for secreto in ("z", "distancia_mpc", "dm15_g", "mag_max"):
            assert secreto not in o, f"{secreto} no debe salir en el catálogo"


def test_el_estudiante_no_recibe_la_respuesta(cliente, oid):
    est = cliente.get(f"/api/objeto/{oid}?modo=estudiante").json()
    doc = cliente.get(f"/api/objeto/{oid}?modo=docente").json()
    for secreto in ("z", "distancia_mpc", "distancia_hubble_mpc", "dm15_g", "mag_max"):
        assert secreto not in est, f"{secreto} se filtró a la vista de estudiante"
        assert secreto in doc, f"{secreto} falta en la vista de docente"
    # pero los datos para graficar sí los recibe: son el ejercicio
    assert len(est["curva"]["detecciones"]) > 5


def test_objeto_desconocido_da_404(cliente):
    assert cliente.get("/api/objeto/ZTF00noexiste").status_code == 404


def test_analisis(cliente, oid):
    d = cliente.get(f"/api/analisis/{oid}?nivel=docente").json()
    assert d["distancia"]["distancia_mpc"] > 0
    assert d["distancia"]["dm15_B"] is not None
    assert d["fotometria"]["dm15"]["dm15"] > 0
    assert d["calibracion"]["sin_calibrar"] is False


def test_analisis_nivel_estudiante_es_vela_estandar(cliente, oid):
    d = cliente.get(f"/api/analisis/{oid}?nivel=estudiante").json()
    assert d["distancia"]["dm15_B"] is None
    assert d["distancia"]["M_B"] == pytest.approx(-19.3, abs=1e-6)


def test_comprobar_usa_los_numeros_del_estudiante(cliente, oid):
    """Dos Δm15 distintos tienen que dar dos distancias distintas.

    Es lo que hace que la actividad se sienta real: el resultado sale de lo que
    midió el estudiante, no de lo que ya sabíamos.
    """
    a = cliente.get(f"/api/comprobar/{oid}?dm15=0.9&mag_max=16.0").json()
    b = cliente.get(f"/api/comprobar/{oid}?dm15=1.5&mag_max=16.0").json()
    assert a["tu_resultado"]["distancia_mpc"] != b["tu_resultado"]["distancia_mpc"]
    # apagarse más rápido = menos luminosa = más cerca para el mismo brillo aparente
    assert b["tu_resultado"]["distancia_mpc"] < a["tu_resultado"]["distancia_mpc"]


def test_comprobar_rechaza_valores_absurdos(cliente, oid):
    assert cliente.get(f"/api/comprobar/{oid}?dm15=-5&mag_max=16").status_code == 422
    assert cliente.get(f"/api/comprobar/{oid}?dm15=1&mag_max=99").status_code == 422


def test_csv_para_planillas_en_espanol(cliente, oid):
    texto = cliente.get(f"/api/datos/{oid}.csv").text
    cabecera, primera = texto.splitlines()[:2]
    assert cabecera.count(";") == 5, "Excel en español espera punto y coma"
    assert "," in primera and primera.count(";") == 5
    assert "." not in primera.split(";")[0], "la coma decimal no debe convivir con el punto"


def test_csv_en_ingles_usa_punto_decimal(cliente, oid):
    texto = cliente.get(f"/api/datos/{oid}.csv?idioma=en&excel_es=false").text
    cabecera, primera = texto.splitlines()[:2]
    assert cabecera.startswith("mjd,")
    assert "." in primera.split(",")[0]


def test_los_dos_idiomas_tienen_las_mismas_claves():
    """Una clave que falte en un idioma aparece en pantalla como 'clave.cruda'."""
    import json
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "frontend" / "i18n"
    es = json.loads((raiz / "es.json").read_text(encoding="utf-8"))
    en = json.loads((raiz / "en.json").read_text(encoding="utf-8"))
    assert set(es) == set(en), (
        f"sólo en es: {sorted(set(es) - set(en))}; sólo en en: {sorted(set(en) - set(es))}"
    )


def test_toda_clave_usada_en_el_html_existe():
    import json
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "frontend"
    es = json.loads((raiz / "i18n" / "es.json").read_text(encoding="utf-8"))
    html = (raiz / "index.html").read_text(encoding="utf-8")
    usadas = set(re.findall(r'data-i18n(?:-aria-label)?="([^"]+)"', html))
    faltan = usadas - set(es)
    assert not faltan, f"claves usadas en el HTML pero sin traducir: {sorted(faltan)}"
