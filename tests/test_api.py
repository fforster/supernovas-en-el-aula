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


def test_rango_del_catalogo_se_calcula_no_se_escribe():
    """La sección del docente cita el rango de distancias del catálogo.

    Regresión: ese rango estaba escrito a mano en el texto y quedó desfasado en
    cuanto se volvió a curar el catálogo (decía 215 Mpc cuando ya llegaba a
    310). Ahora se calcula, y esta prueba comprueba que sigue cuadrando con los
    objetos que hay de verdad.
    """
    import math

    from backend import catalogo

    r = catalogo.rango_modulo()
    ds = [o["distancia_hubble_mpc"] for o in catalogo.objetos()]
    assert r["d_min"] == pytest.approx(min(ds))
    assert r["d_max"] == pytest.approx(max(ds))
    assert r["mu_min"] == pytest.approx(5 * math.log10(min(ds) * 1e6) - 5)
    assert r["mu_max"] == pytest.approx(5 * math.log10(max(ds) * 1e6) - 5)
    # y el módulo tiene que ser coherente con la conversión que usa la app
    from backend import cosmologia as C

    assert C.modulo_a_mpc(r["mu_min"]) == pytest.approx(r["d_min"], rel=1e-9)


def test_el_endpoint_del_catalogo_entrega_el_rango(cliente):
    r = cliente.get("/api/catalogo").json()["rango_modulo"]
    assert r["mu_min"] < r["mu_max"]
    assert 25 < r["mu_min"] < 45, "módulo de distancia fuera de lo plausible"


def test_los_marcadores_del_texto_del_docente_son_los_que_rellena_el_js():
    """Si alguien añade un {marcador} al texto y no lo rellena, sale en pantalla."""
    import json
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    app_js = (raiz / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

    for lang in ("es", "en"):
        textos = json.loads(
            (raiz / "frontend" / "i18n" / f"{lang}.json").read_text(encoding="utf-8")
        )
        con_marcador = {
            k: set(re.findall(r"\{([a-z_]+)\}", v))
            for k, v in textos.items()
            if k.startswith("metodo.") and re.search(r"\{[a-z_]+\}", str(v))
        }
        assert set(con_marcador) == {"metodo.s4_p5"}, (
            f"[{lang}] claves de método con marcadores sin rellenar: "
            f"{sorted(set(con_marcador) - {'metodo.s4_p5'})}"
        )
        for marcador in con_marcador["metodo.s4_p5"]:
            assert f"{marcador}:" in app_js, (
                f"[{lang}] el texto usa {{{marcador}}} pero app.js no lo rellena"
            )


def test_los_diagramas_se_generan_en_los_dos_idiomas():
    from backend import esquema

    for idioma in ("es", "en"):
        for svg in (esquema.curva_esquematica(idioma), esquema.ley_inversa(idioma)):
            assert svg.startswith("<svg") and svg.endswith("</svg>")
            assert 'role="img"' in svg and "aria-label=" in svg, "falta texto alternativo"


def test_las_pantallas_del_diagrama_crecen_como_el_cuadrado():
    """El dibujo enseña que el área crece como d²: si no, enseña algo falso."""
    import re

    from backend import esquema

    poligonos = re.findall(
        r'class="ley__pantalla" points="([^"]+)"', esquema.ley_inversa("es")
    )
    assert len(poligonos) == 3

    def area(pts):
        p = [tuple(map(float, q.split(","))) for q in pts.split()]
        ux, uy = p[1][0] - p[0][0], p[1][1] - p[0][1]
        vx, vy = p[3][0] - p[0][0], p[3][1] - p[0][1]
        return abs(ux * vy - uy * vx)

    a = sorted(area(p) for p in poligonos)
    assert a[1] / a[0] == pytest.approx(4.0, rel=1e-6)
    assert a[2] / a[0] == pytest.approx(9.0, rel=1e-6)


def test_todo_aviso_del_backend_esta_traducido():
    """Regresión: la interfaz en inglés mostraba las advertencias en español.

    Las advertencias nacen en Python y se leen en la página, que puede estar en
    cualquiera de los dos idiomas. Se emiten como código + parámetros y se
    traducen en el navegador; esta prueba comprueba que todo código que el
    backend sabe emitir tiene su clave en LOS DOS idiomas, y que los parámetros
    de la plantilla española y la inglesa coinciden.
    """
    import json
    import re
    from pathlib import Path

    from backend.avisos import PLANTILLAS

    raiz = Path(__file__).resolve().parent.parent / "frontend" / "i18n"
    textos = {
        lang: json.loads((raiz / f"{lang}.json").read_text(encoding="utf-8"))
        for lang in ("es", "en")
    }

    for codigo, plantilla in PLANTILLAS.items():
        clave = f"aviso.{codigo}"
        esperados = set(re.findall(r"\{(\w+)\}", plantilla))
        for lang, d in textos.items():
            assert clave in d, f"falta '{clave}' en {lang}.json"
            hallados = set(re.findall(r"\{(\w+)\}", d[clave]))
            assert hallados == esperados, (
                f"[{lang}] '{clave}' usa {sorted(hallados)} pero el backend "
                f"entrega {sorted(esperados)}"
            )


def test_los_avisos_viajan_como_codigo_no_como_frase(cliente, oid):
    """Si el backend volviera a mandar frases, la traducción sería imposible."""
    d = cliente.get(f"/api/analisis/{oid}?nivel=docente").json()
    for av in d["distancia"]["avisos"]:
        assert isinstance(av, dict), f"aviso sin estructura: {av!r}"
        assert av["codigo"] and isinstance(av["params"], dict)


def test_un_aviso_desconocido_falla_temprano():
    from backend.avisos import aviso

    with pytest.raises(KeyError, match="Aviso desconocido"):
        aviso("no_existe")


def test_z_fuente_viaja_como_codigo_no_como_frase():
    """Regresión: "NED, galaxia anfitriona X" salía en español en modo inglés.

    Lo ve el docente en el panel («Corrimiento al rojo: …»), así que tiene que
    poder traducirse: viaja como código + nombre, igual que los avisos.
    """
    from backend import catalogo

    for o in catalogo.objetos():
        z = o["z_fuente"]
        assert isinstance(z, dict), f"{o['oid']}: z_fuente es una frase, no un código"
        assert z["codigo"] and "nombre" in z["params"]


def test_todo_codigo_de_zfuente_esta_traducido():
    import json
    import re
    from pathlib import Path

    from backend import catalogo

    raiz = Path(__file__).resolve().parent.parent / "frontend" / "i18n"
    codigos = {o["z_fuente"]["codigo"] for o in catalogo.objetos()}
    for lang in ("es", "en"):
        d = json.loads((raiz / f"{lang}.json").read_text(encoding="utf-8"))
        for c in codigos:
            clave = f"zfuente.{c}"
            assert clave in d, f"falta '{clave}' en {lang}.json"
            assert set(re.findall(r"\{(\w+)\}", d[clave])) == {"nombre"}


def test_el_catalogo_no_lleva_prosa_en_espanol_fuera_de_los_textos():
    """Canario: cualquier campo nuevo con una frase en español la delata.

    Los campos que SÍ pueden llevar español son los códigos (que la interfaz
    traduce) y ``textos``, que ya es bilingüe. El resto son números, nombres
    propios o identificadores.
    """
    import re

    from backend import catalogo

    # campos que son códigos traducidos en la interfaz, no prosa
    CODIGOS = {"dificultad", "codigo"}
    PALABRAS = re.compile(
        r"\b(galaxia|anfitriona|misma|otra|supernova|del|los|las|una|para|desde)\b",
        re.IGNORECASE,
    )

    def revisar(valor, ruta=""):
        if isinstance(valor, dict):
            for k, v in valor.items():
                if k in ("textos", "texto") or k in CODIGOS:
                    continue
                revisar(v, f"{ruta}.{k}")
        elif isinstance(valor, list):
            for v in valor:
                revisar(v, ruta)
        elif isinstance(valor, str) and PALABRAS.search(valor):
            raise AssertionError(
                f"prosa en español en {ruta}: {valor!r} — "
                "si se muestra en pantalla debe viajar como código traducible"
            )

    for o in catalogo.objetos():
        revisar(o, o["oid"])


def test_la_formula_de_la_hoja_usa_el_decimal_de_cada_idioma():
    from backend.informe import TEXTOS

    assert "−19,3" in TEXTOS["es"]["formula_distancia"]
    assert "−19.3" in TEXTOS["en"]["formula_distancia"]
