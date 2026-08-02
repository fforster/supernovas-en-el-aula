"""Aplicación web / web application.

Rutas JSON + los archivos estáticos del frontend.  El navegador nunca habla
directo con ALeRCE: así el cálculo científico es uno solo, en Python, y el mismo
número sale en la pantalla, en el CSV y en la hoja impresa.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import calibracion, catalogo, cosmologia, fotometria, imagenes, informe
from .brokers import AlerceZTF, BrokerError

log = logging.getLogger(__name__)
RAIZ = Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend"

broker = AlerceZTF(cache_dir=str(RAIZ / "cache"))

jinja = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent / "plantillas")),
    autoescape=select_autoescape(["html"]),
)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    yield
    await broker.aclose()


app = FastAPI(
    title="Supernovas en el aula — ALeRCE",
    description="Actividad escolar de distancias con supernovas tipo Ia",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)


async def _curva(oid: str):
    ficha = catalogo.buscar(oid)
    if ficha is None:
        raise HTTPException(404, f"La supernova {oid} no está en el catálogo.")
    try:
        return ficha, await broker.curva_de_luz(oid)
    except BrokerError as exc:
        raise HTTPException(
            503, f"No se pudo obtener la curva de luz desde ALeRCE: {exc}"
        ) from exc


# ------------------------------------------------------------------- catálogo


@app.get("/api/catalogo")
async def api_catalogo(idioma: str = Query("es", pattern="^(es|en)$")):
    """Tarjetas del navegador de objetos.  No revela las respuestas."""
    datos = catalogo.cargar()
    return {
        "generado": datos["generado"],
        "survey": datos["survey"],
        "clasificador": datos["clasificador"],
        "version_clasificador": datos["version_clasificador"],
        "criterios": datos["criterios"],
        "objetos": catalogo.resumen(idioma, broker),
    }


@app.get("/api/objeto/{oid}")
async def api_objeto(
    oid: str,
    modo: str = Query("estudiante", pattern="^(estudiante|docente)$"),
    idioma: str = Query("es", pattern="^(es|en)$"),
):
    """Ficha del objeto.  En modo estudiante se omiten z y las distancias."""
    ficha, curva = await _curva(oid)
    salida = (
        catalogo.para_docente(ficha, idioma)
        if modo == "docente"
        else catalogo.para_estudiante(ficha, idioma)
    )
    salida["curva"] = curva.dict()
    salida["ejes"] = informe.rangos_ejes(curva)
    if ficha["candid_estampilla"]:
        salida["estampillas"] = broker.urls_estampillas(oid, ficha["candid_estampilla"])
    return salida


# -------------------------------------------------------------------- análisis


@app.get("/api/analisis/{oid}")
async def api_analisis(
    oid: str,
    nivel: str = Query("docente", pattern="^(estudiante|docente)$"),
):
    """La cadena completa: máximo, Δm15, luminosidad y distancia.

    Es la "pauta de corrección": lo que el docente compara con lo que midieron
    sus estudiantes.
    """
    ficha, curva = await _curva(oid)
    try:
        foto = fotometria.medir(curva, z=ficha["z"], banda="g", banda_color="r")
    except fotometria.MedicionImposible as exc:
        raise HTTPException(422, str(exc)) from exc

    dist = cosmologia.calcular(
        foto, nivel=nivel, ebv=ficha["ebv"], z=ficha["z"]
    )
    return {
        "oid": oid,
        "nivel": nivel,
        "fotometria": foto.dict(),
        "distancia": dist.dict(),
        "calibracion": {
            "generado": calibracion.cargar().generado,
            "H0": calibracion.cargar().H0,
            "sin_calibrar": calibracion.cargar().sin_calibrar,
        },
    }


@app.get("/api/comprobar/{oid}")
async def api_comprobar(
    oid: str,
    dm15: float = Query(..., ge=0.0, le=5.0, description="Δm15 medido por el estudiante"),
    mag_max: float = Query(..., ge=5.0, le=25.0),
):
    """Compara la medición del estudiante con la del pipeline.

    Devuelve también la distancia que sale **de sus propios números**, que es lo
    que hace que la actividad se sienta real: el resultado es suyo, no nuestro.
    """
    ficha, curva = await _curva(oid)
    cal = calibracion.cargar()
    scal = cal.survey("ZTF")

    dm15_B = scal.dm15_B(dm15)
    M_B = cal.M_B(dm15_B)
    m_B = scal.m_B(mag_max, None) - scal.R_B * ficha["ebv"]
    mu = m_B - M_B
    d = cosmologia.modulo_a_mpc(mu)
    d_hubble = cosmologia.distancia_hubble(ficha["z"], cal)

    try:
        foto = fotometria.medir(curva, z=ficha["z"], banda="g", banda_color="r")
        referencia = {"dm15": foto.dm15.dm15, "mag_max": foto.maximo.mag_max}
    except fotometria.MedicionImposible:
        referencia = None

    return {
        "oid": oid,
        "tu_medicion": {"dm15": dm15, "mag_max": mag_max},
        "referencia": referencia,
        "tu_resultado": {
            "dm15_B": dm15_B,
            "M_B": M_B,
            "mu": mu,
            "distancia_mpc": d,
            "distancia_anios_luz": d * 1e6 * cosmologia.ANIOS_LUZ_POR_PARSEC,
        },
        "respuesta": {
            "distancia_hubble_mpc": d_hubble,
            "z": ficha["z"],
            "diferencia_porcentual": 100.0 * (d - d_hubble) / d_hubble,
        },
    }


# ------------------------------------------------------------------- descargas


@app.get("/api/datos/{oid}.csv")
async def api_csv(
    oid: str,
    idioma: str = Query("es", pattern="^(es|en)$"),
    excel_es: bool = Query(True, description="separador ; y coma decimal"),
    limites: bool = Query(False, description="incluir no detecciones"),
):
    _, curva = await _curva(oid)
    texto = informe.csv_curva(
        curva, idioma=idioma, locale_es=excel_es, incluir_no_detecciones=limites
    )
    return PlainTextResponse(
        texto,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{oid}.csv"'},
    )


@app.get("/api/hoja/{oid}")
async def api_hoja(
    oid: str,
    idioma: str = Query("es", pattern="^(es|en)$"),
    pauta: bool = Query(False, description="incluir la pauta de corrección"),
    papel: bool = Query(False, description="sólo el papel para graficar"),
):
    """Guía imprimible para la clase (y, opcionalmente, la pauta del docente).

    Se sirve como HTML: el navegador la convierte en PDF con Ctrl+P, así no hace
    falta arrastrar una dependencia de PDF ni una fuente para el castellano.
    """
    ficha, curva = await _curva(oid)
    txt = informe.TEXTOS[idioma]
    nombre = ficha["nombre_sn"] or ficha["oid"]

    filas_pauta = []
    if pauta:
        try:
            foto = fotometria.medir(curva, z=ficha["z"], banda="g", banda_color="r")
            dist = cosmologia.calcular(foto, nivel="docente", ebv=ficha["ebv"], z=ficha["z"])
            coma = idioma == "es"

            def n(x, d=2):
                s = f"{x:.{d}f}"
                return s.replace(".", ",") if coma else s

            filas_pauta = [
                (txt["mag"] + " (máx, g)" if coma else txt["mag"] + " (peak, g)",
                 n(foto.maximo.mag_max, 2)),
                ("Δm15 (g)", n(foto.dm15.dm15, 2)),
                ("Δm15 (B)", n(dist.dm15_B, 2) if dist.dm15_B else "—"),
                ("M_B", n(dist.M_B, 2)),
                ("μ", n(dist.mu, 2)),
                ("Distancia" if coma else "Distance", f"{n(dist.distancia_mpc, 0)} Mpc"),
                ("Ley de Hubble" if coma else "Hubble's law",
                 f"{n(dist.distancia_hubble_mpc, 0)} Mpc"),
                ("z", n(ficha["z"], 4)),
            ]
        except fotometria.MedicionImposible as exc:
            filas_pauta = [("—", str(exc))]

    plantilla = jinja.get_template("hoja.html")
    return HTMLResponse(plantilla.render(
        idioma=idioma,
        titulo=txt["papel"] if papel else txt["pasos"],
        nombre=nombre,
        historia=ficha["textos"].get(idioma, ficha["textos"]["es"])["historia"],
        txt=txt,
        pauta=pauta,
        papel=papel,
        pauta_filas=filas_pauta,
        filas=informe.filas_tabla(curva, idioma),
        svg=informe.papel_milimetrado(informe.rangos_ejes(curva), idioma),
    ))


@app.get("/api/estampilla/{oid}/{candid}/{tipo}.png")
async def api_estampilla(oid: str, candid: str, tipo: str):
    """Recorte del cielo, reescalado para que se vea.

    ALeRCE sirve estas imágenes en PNG con estiramiento lineal, y en una imagen
    astronómica eso deja casi todo negro.  Aquí se baja el FITS y se normaliza
    con ``astropy.visualization``, midiendo el brillo en la **zona central**
    para que la supernova —que está justo ahí— siempre quede visible.
    """
    if tipo not in broker.TIPOS_ESTAMPILLA:
        raise HTTPException(
            404, f"Tipo de imagen desconocido: {tipo}. Usa uno de {broker.TIPOS_ESTAMPILLA}."
        )
    if not candid.isdigit():
        raise HTTPException(400, "candid inválido.")

    destino = RAIZ / "cache" / "estampillas" / f"{oid}_{candid}_{tipo}.png"
    if destino.exists():
        return FileResponse(str(destino), media_type="image/png")

    try:
        crudo = await broker.fits_estampilla(oid, candid, tipo)
        png = imagenes.procesar(crudo, cache=destino)
    except (BrokerError, imagenes.ImagenNoDisponible) as exc:
        raise HTTPException(503, f"No se pudo preparar la imagen: {exc}") from exc

    return Response(
        content=png,
        media_type="image/png",
        # son inmutables: un candid identifica una observación concreta
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/calibracion")
async def api_calibracion():
    """Los números con que se hacen las cuentas, a la vista de quien quiera."""
    return calibracion.cargar().crudo


@app.get("/api/salud")
async def api_salud():
    try:
        n = len(catalogo.objetos())
    except catalogo.CatalogoVacio as exc:
        return {"ok": False, "error": str(exc)}
    cal = calibracion.cargar()
    return {
        "ok": True,
        "supernovas": n,
        "calibracion_generada": cal.generado,
        "sin_calibrar": cal.sin_calibrar,
        "clasificador": broker.clasificador,
    }


# ------------------------------------------------------------------- estáticos

if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

    @app.get("/")
    async def raiz():
        return FileResponse(str(FRONTEND / "index.html"))

    @app.get("/sw.js")
    async def service_worker():
        # el service worker debe servirse desde la raíz para poder cachear todo
        return FileResponse(
            str(FRONTEND / "sw.js"), media_type="application/javascript"
        )
else:  # pragma: no cover

    @app.get("/")
    async def raiz():
        return RedirectResponse("/docs")
