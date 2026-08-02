#!/usr/bin/env python3
"""Genera el sitio estático / build the static site.

Deja en ``sitio/`` una copia de la aplicación que funciona **sin servidor**, con
todo lo que normalmente calcula FastAPI ya resuelto y guardado como archivos.
Se puede publicar tal cual en GitHub Pages, en un pendrive o en el disco de una
sala de computación sin internet.

La idea
-------
El catálogo son 30 objetos fijos, así que todo lo que la API responde se puede
calcular una vez, aquí, **con el mismo código Python** que usa el servidor.  Así
no hay dos implementaciones de la física que puedan divergir: lo único que el
navegador calcula por su cuenta es la aritmética final del estudiante
(``frontend/js/rutas.js``), y hay una prueba que fija esos valores.

Lo que hay que saber antes de publicar
--------------------------------------
En un sitio estático **no se puede esconder la respuesta**.  El navegador
necesita el corrimiento al rojo y la extinción para hacer la cuenta, así que
quedan dentro de los archivos JSON: un estudiante que abra las herramientas de
desarrollo los va a encontrar.  La interfaz sigue sin mostrarlos, pero no es un
secreto de verdad.  Si eso importa, hay que desplegar el backend
(``uvicorn``), que sí los quita antes de enviar nada.

Uso
---
    python3 scripts/construir_estatico.py
    python3 -m http.server -d sitio 8000     # para probarlo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend import calibracion, catalogo, cosmologia, esquema, fotometria, imagenes, informe  # noqa: E402
from backend.app import jinja  # noqa: E402
from backend.brokers import AlerceZTF  # noqa: E402

IDIOMAS = ("es", "en")


def escribir(destino: Path, contenido: str | bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenido, bytes):
        destino.write_bytes(contenido)
    else:
        destino.write_text(contenido, encoding="utf-8")


def json_a(destino: Path, datos) -> None:
    escribir(destino, json.dumps(datos, ensure_ascii=False))


def relativizar(datos):
    """Cambia las rutas absolutas ``/api/...`` por relativas.

    En GitHub Pages el sitio cuelga de ``/usuario.github.io/repositorio/``, así
    que nada puede empezar con ``/``.
    """
    if isinstance(datos, dict):
        return {k: relativizar(v) for k, v in datos.items()}
    if isinstance(datos, list):
        return [relativizar(v) for v in datos]
    if isinstance(datos, str) and datos.startswith("/api/"):
        return datos[1:]
    return datos


async def construir(salida: Path, con_imagenes: bool = True) -> int:
    broker = AlerceZTF(cache_dir=str(RAIZ / "cache"))
    objetos = catalogo.objetos()
    cal = calibracion.cargar()

    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)

    # ------------------------------------------------------- el frontend tal cual
    for sub in ("css", "js", "i18n", "img"):
        origen = RAIZ / "frontend" / sub
        if origen.exists():
            shutil.copytree(origen, salida / sub)

    html = (RAIZ / "frontend" / "index.html").read_text(encoding="utf-8")
    # marca el modo estático y deja todas las rutas relativas
    html = html.replace('<html lang="es">', '<html lang="es" data-estatico="true">')
    html = html.replace('href="/static/', 'href="').replace('src="/static/', 'src="')
    escribir(salida / "index.html", html)

    sw = (RAIZ / "frontend" / "sw.js").read_text(encoding="utf-8")
    sw = sw.replace("'/static/", "'./").replace("  '/',", "  './',")
    escribir(salida / "sw.js", sw)

    # GitHub Pages ignora las carpetas que empiezan con guion bajo si no está esto
    escribir(salida / ".nojekyll", "")

    json_a(salida / "api" / "calibracion.json", cal.crudo)

    for idioma in IDIOMAS:
        escribir(salida / "api" / f"esquema-{idioma}.svg", esquema.curva_esquematica(idioma))

    # ------------------------------------------------------------------ catálogo
    for idioma in IDIOMAS:
        datos = {
            "generado": catalogo.cargar()["generado"],
            "survey": catalogo.cargar()["survey"],
            "clasificador": catalogo.cargar()["clasificador"],
            "version_clasificador": catalogo.cargar()["version_clasificador"],
            "criterios": catalogo.cargar()["criterios"],
            "objetos": catalogo.resumen(idioma, broker),
        }
        json_a(salida / "api" / f"catalogo-{idioma}.json", relativizar(datos))

    # ------------------------------------------------------------------- objetos
    print(f"Preparando {len(objetos)} supernovas...")
    fallos = 0
    for i, ficha in enumerate(objetos, 1):
        oid = ficha["oid"]
        try:
            curva = await broker.curva_de_luz(oid)
        except Exception as exc:
            print(f"  ! {oid}: sin curva de luz ({exc})")
            fallos += 1
            continue

        for idioma in IDIOMAS:
            for modo in ("estudiante", "docente"):
                salida_obj = (
                    catalogo.para_docente(ficha, idioma)
                    if modo == "docente"
                    else catalogo.para_estudiante(ficha, idioma)
                )
                if modo == "estudiante":
                    # Sin servidor, el navegador tiene que hacer la cuenta, y
                    # para eso necesita z y la extinción.  Van con una nota:
                    # en el sitio estático la respuesta no es un secreto.
                    salida_obj["z"] = ficha["z"]
                    salida_obj["ebv"] = ficha["ebv"]
                    salida_obj["_nota"] = (
                        "z y ebv van aquí porque sin servidor el cálculo lo hace "
                        "el navegador. En un sitio estático la respuesta no se "
                        "puede esconder."
                    )
                salida_obj["curva"] = curva.dict()
                salida_obj["ejes"] = informe.rangos_ejes(curva)
                if ficha["candid_estampilla"]:
                    salida_obj["estampillas"] = broker.urls_estampillas(
                        oid, ficha["candid_estampilla"]
                    )
                json_a(
                    salida / "api" / "objeto" / f"{oid}-{modo}-{idioma}.json",
                    relativizar(salida_obj),
                )

            escribir(
                salida / "api" / "datos" / f"{oid}-{idioma}.csv",
                informe.csv_curva(curva, idioma=idioma, locale_es=(idioma == "es")),
            )

        # ------------------------------------------------------------- análisis
        try:
            foto = fotometria.medir(curva, z=ficha["z"], banda="g", banda_color="r")
            for nivel in ("estudiante", "docente"):
                dist = cosmologia.calcular(
                    foto, nivel=nivel, ebv=ficha["ebv"], z=ficha["z"]
                )
                json_a(
                    salida / "api" / "analisis" / f"{oid}-{nivel}.json",
                    {
                        "oid": oid,
                        "nivel": nivel,
                        "fotometria": foto.dict(),
                        "distancia": dist.dict(),
                        "calibracion": {
                            "generado": cal.generado,
                            "H0": cal.H0,
                            "sin_calibrar": cal.sin_calibrar,
                        },
                    },
                )
        except fotometria.MedicionImposible as exc:
            print(f"  ! {oid}: no se pudo analizar ({exc})")
            fallos += 1

        # -------------------------------------------------- hojas imprimibles
        for idioma in IDIOMAS:
            for sufijo, kwargs in (
                ("guia", {"pauta": False, "papel": False}),
                ("pauta", {"pauta": True, "papel": False}),
                ("papel", {"pauta": False, "papel": True}),
            ):
                escribir(
                    salida / "api" / "hoja" / f"{oid}-{idioma}-{sufijo}.html",
                    _hoja(ficha, curva, idioma, **kwargs),
                )

        # ------------------------------------------------------- estampillas
        if con_imagenes and ficha["candid_estampilla"]:
            candid = ficha["candid_estampilla"]
            for tipo in broker.TIPOS_ESTAMPILLA:
                destino = salida / "api" / "estampilla" / oid / candid / f"{tipo}.png"
                cache = RAIZ / "cache" / "estampillas" / f"{oid}_{candid}_{tipo}.png"
                try:
                    if cache.exists():
                        escribir(destino, cache.read_bytes())
                    else:
                        crudo = await broker.fits_estampilla(oid, candid, tipo)
                        escribir(destino, imagenes.procesar(crudo, cache=cache))
                except Exception as exc:
                    print(f"  ! {oid} {tipo}: {exc}")

        if i % 5 == 0:
            print(f"  {i}/{len(objetos)}")

    await broker.aclose()

    archivos = sum(1 for _ in salida.rglob("*") if _.is_file())
    peso = sum(f.stat().st_size for f in salida.rglob("*") if f.is_file())
    print(f"\n{archivos} archivos, {peso / 1e6:.1f} MB en {salida}")
    if fallos:
        print(f"ADVERTENCIA: {fallos} problemas durante la construcción")
    print("\nPara probarlo:  python3 -m http.server -d sitio 8000")
    return 0


def _hoja(ficha, curva, idioma: str, pauta: bool, papel: bool) -> str:
    """La misma hoja imprimible que sirve la API, pero escrita a disco."""
    txt = informe.TEXTOS[idioma]
    filas_pauta = []
    if pauta:
        try:
            foto = fotometria.medir(curva, z=ficha["z"], banda="g", banda_color="r")
            dist = cosmologia.calcular(
                foto, nivel="docente", ebv=ficha["ebv"], z=ficha["z"]
            )
            coma = idioma == "es"

            def n(x, d=2):
                s = f"{x:.{d}f}"
                return s.replace(".", ",") if coma else s

            filas_pauta = [
                (txt["mag"] + (" (máx, g)" if coma else " (peak, g)"), n(foto.maximo.mag_max, 2)),
                ("Δm15 (g)", n(foto.dm15.dm15, 2)),
                ("Δm15 (B)", n(dist.dm15_B, 2) if dist.dm15_B else "—"),
                ("M_B", n(dist.M_B, 2)),
                ("μ", n(dist.mu, 2)),
                ("Distancia" if coma else "Distance", f"{n(dist.distancia_mpc, 0)} Mpc"),
                ("Ley de Hubble" if coma else "Hubble's law", f"{n(dist.distancia_hubble_mpc, 0)} Mpc"),
                ("z", n(ficha["z"], 4)),
            ]
        except fotometria.MedicionImposible as exc:
            filas_pauta = [("—", str(exc))]

    return jinja.get_template("hoja.html").render(
        idioma=idioma,
        titulo=txt["papel"] if papel else txt["pasos"],
        nombre=ficha["nombre_sn"] or ficha["oid"],
        historia=ficha["textos"].get(idioma, ficha["textos"]["es"])["historia"],
        txt=txt,
        pauta=pauta,
        papel=papel,
        pauta_filas=filas_pauta,
        filas=informe.filas_tabla(curva, idioma),
        svg=informe.papel_milimetrado(informe.rangos_ejes(curva), idioma),
        esquema=esquema.curva_esquematica(idioma),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default=str(RAIZ / "sitio"))
    ap.add_argument("--sin-imagenes", action="store_true", help="salta las estampillas")
    args = ap.parse_args()
    return asyncio.run(construir(Path(args.salida), not args.sin_imagenes))


if __name__ == "__main__":
    raise SystemExit(main())
