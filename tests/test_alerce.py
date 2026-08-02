"""Pruebas contra la API real de ALeRCE.

Se ejecutan sólo con ``pytest --red``. Están para detectar cambios en la API
antes de que los detecte un docente en medio de una clase.
"""

from __future__ import annotations

import pytest

from backend import fotometria as F
from backend.brokers import AlerceZTF, BrokerError
from backend.brokers.alerce_ztf import comprobar_filtro_clase

pytestmark = pytest.mark.red

#: Dos SN Ia muy conocidas, con máximos publicados en la literatura.
CONOCIDAS = {
    # SN 2021hpr en NGC 3147: máximo en B el MJD 59323,2 y Δm15(B) = 1,03
    "ZTF21aarqkes": {"z": 0.0093, "t_max": 59323.2, "dm15_B": 1.03},
    # SN 2019np en NGC 3254: máximo en B alrededor del MJD 58510,6
    "ZTF19aacgslb": {"z": 0.00452, "t_max": 58510.6, "dm15_B": 1.04},
}


@pytest.fixture
async def broker():
    """Un broker por prueba.

    Compartirlo entre pruebas no funciona: cada prueba corre en su propio bucle
    de eventos, y el cliente httpx queda amarrado al bucle en que se creó, así
    que al cerrarse el primero las demás revientan con "Event loop is closed".
    """
    b = AlerceZTF(cache_dir="cache")
    try:
        yield b
    finally:
        await b.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("oid", sorted(CONOCIDAS))
async def test_maximo_coincide_con_la_literatura(broker, oid):
    esperado = CONOCIDAS[oid]
    curva = await broker.curva_de_luz(oid)
    foto = F.medir(curva, z=esperado["z"], n_bootstrap=0)
    # el máximo en g precede al de B en ~1 día; toleramos 3
    assert foto.maximo.t_max == pytest.approx(esperado["t_max"], abs=3.0)


@pytest.mark.anyio
@pytest.mark.parametrize("oid", sorted(CONOCIDAS))
async def test_dm15_convertido_coincide_con_la_literatura(broker, oid):
    from backend.calibracion import cargar

    esperado = CONOCIDAS[oid]
    curva = await broker.curva_de_luz(oid)
    foto = F.medir(curva, z=esperado["z"], n_bootstrap=0)
    dm15_B = cargar().survey("ZTF").dm15_B(foto.dm15.dm15)
    assert dm15_B == pytest.approx(esperado["dm15_B"], abs=0.15)


@pytest.mark.anyio
async def test_el_filtro_class_funciona(broker):
    """Regresión de la API.

    El parámetro se llama ``class``; con ``class_name`` la API **ignora el
    filtro en silencio** y devuelve objetos de cualquier clase. Si esta prueba
    se cae, revisa primero si ALeRCE renombró el parámetro.
    """
    pureza = await comprobar_filtro_clase(broker, "SNIa")
    assert pureza > 0.9, f"pureza del filtro class=SNIa: {pureza:.0%}"


@pytest.mark.anyio
async def test_la_fotometria_brillante_no_se_pierde(broker):
    """Regresión: ``drb`` (de ZTF, no de ALeRCE) vale 0,0 en fuentes brillantes.

    Filtrar por ``drb > 0.5`` borraba el máximo de SN 2019np (g ≈ 13,4) y con él
    las supernovas más útiles para el aula. Ahora ``drb`` se ignora del todo.
    """
    curva = await broker.curva_de_luz("ZTF19aacgslb")
    g = curva.por_banda("g")
    assert min(d.mag for d in g) < 14.0, "se perdieron las detecciones brillantes"


@pytest.mark.anyio
async def test_el_catalogo_es_de_la_era_de_fotometria_forzada():
    """BHRF se entrenó con fotometría forzada: sólo vale de 2024 en adelante."""
    from backend import catalogo
    from backend.brokers.alerce_ztf import MJD_FOTOMETRIA_FORZADA

    viejas = [
        o["oid"] for o in catalogo.objetos()
        if o["t_max"] < MJD_FOTOMETRIA_FORZADA
    ]
    assert not viejas, f"anteriores a la fotometria forzada: {viejas}"


@pytest.mark.anyio
async def test_el_catalogo_no_tiene_huecos_grandes(broker):
    """Sin cobertura densa cerca del máximo el estudiante no puede leer Δm15."""
    from backend import catalogo
    from scripts.curar_catalogo import MAX_HUECO

    malos = [
        (o["oid"], round(o["hueco_max"], 1))
        for o in catalogo.objetos()
        if o["hueco_max"] > MAX_HUECO
    ]
    assert not malos, f"huecos mayores a {MAX_HUECO} d: {malos}"


@pytest.mark.anyio
async def test_el_catalogo_sigue_siendo_de_tipo_Ia(broker):
    """Cada objeto del catálogo debe seguir clasificado como SNIa en ALeRCE.

    Detecta que un reentrenamiento cambie la opinión del clasificador.
    """
    from backend import catalogo

    malos = []
    for ficha in catalogo.objetos():
        clasif = await broker.clasificacion(ficha["oid"])
        if clasif is None or clasif.clase != "SNIa" or clasif.ranking != 1:
            malos.append((ficha["oid"], clasif.clase if clasif else None))
    assert not malos, f"ya no son SNIa de ranking 1 segun BHRF: {malos}"


@pytest.mark.anyio
async def test_objeto_inexistente(broker):
    with pytest.raises(BrokerError):
        await broker.curva_de_luz("ZTF00noexisteenabsoluto")


@pytest.mark.anyio
async def test_distancias_del_catalogo_son_razonables():
    """El catálogo completo debe reproducir la ley de Hubble sin escándalos."""
    import numpy as np

    from backend import catalogo

    dif = np.array([
        abs(o["diferencia_porcentual"])
        for o in catalogo.objetos()
        if o["diferencia_porcentual"] is not None
    ])
    assert dif.size >= 10
    assert np.median(dif) < 20.0, f"mediana {np.median(dif):.1f} %"
    assert dif.max() <= 30.0, "el curador debía descartar las diferencias > 30 %"


@pytest.fixture
def anyio_backend():
    return "asyncio"
