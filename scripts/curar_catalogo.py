#!/usr/bin/env python3
"""Arma el catálogo de supernovas para el aula / build the classroom SN catalog.

Produce ``data/catalogo_snia.json``.  Sólo entran supernovas que sirven de
verdad para la actividad, y cada filtro está aquí por una razón concreta:

* **La clase la decide ALeRCE**, con el filtro ``class`` (¡no ``class_name``!) de
  la rama de transitorios de BHRF, y además se confirma objeto por objeto contra
  ``/objects/{oid}/probabilities``.  La confirmación es barata y sirve de red:
  si la API cambia, lo notamos aquí y no en la sala de clases.
* **Sólo supernovas de 2024 en adelante.**  BHRF se entrenó con fotometría
  forzada, que ZTF sólo produce desde entonces; aplicarlo a alertas anteriores
  es sacarlo de su dominio.  Se exige además que BHRF haya opinado de verdad
  sobre el objeto: no hay clasificador de respaldo.
* **La identidad y el corrimiento al rojo los da NED**, buscando por posición: si
  hay una supernova catalogada a menos de 15″ obtenemos su nombre IAU y su z.
  Sin z no se puede corregir la dilatación temporal ni comparar con Hubble, así
  que sin z el objeto no entra.
* **z entre 0,015 y 0,07.**  Más cerca, las velocidades peculiares de las
  galaxias arruinan la comparación con la ley de Hubble: a z = 0,0045 una
  velocidad peculiar típica de 300 km/s cambia la distancia en ±22 %, y la
  actividad parecería fallar cuando en realidad falla la ley de Hubble.
* **Máximo entre g = 14 y g = 18,3.**  Más brillante satura el detector de ZTF
  (SN 2019np, con g ≈ 13,4, tiene fotometría poco fiable); más débil no tiene
  suficientes puntos para ver la forma de la curva.
* **Cobertura densa alrededor del máximo.**  No basta con que haya puntos antes
  y después: si entre el máximo y el día +15 hay un hueco de dos semanas, el
  ajuste rellena ese hueco inventando, y el estudiante que grafique a mano ve
  un vacío donde debería leer Δm15.  Se exige que en la ventana crítica
  (−8 a +20 días del máximo) no haya huecos mayores a 5 días, y que exista una
  medición real a menos de 3 días del instante t_max + 15(1+z).

Uso
---
    python3 scripts/curar_catalogo.py --objetivo 25
    python3 scripts/curar_catalogo.py --objetivo 25 --candidatas 400
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import httpx  # noqa: E402
import numpy as np  # noqa: E402

from backend import fotometria as F  # noqa: E402
from backend import cosmologia as C  # noqa: E402
from backend import eras  # noqa: E402
from backend.brokers import AlerceZTF  # noqa: E402
from backend.brokers.alerce_ztf import MJD_FOTOMETRIA_FORZADA  # noqa: E402

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ criterios

Z_MIN, Z_MAX = 0.015, 0.070
MAG_MIN, MAG_MAX = 14.0, 18.3
N_MIN_BANDA = 8
N_MIN_ANTES = 2
#: Cobertura mínima alrededor del máximo (ver la nota del encabezado).
MAX_HUECO = 5.0
VENTANA_CRITICA = (-8.0, 20.0)
#: Distancia máxima entre t_max+15(1+z) y la medición real más cercana.
MAX_DISTANCIA_A_15 = 3.0

#: Rango físico de Δm15(B) para SN Ia normales (Phillips 1999 y sucesores).
DM15_B_MIN, DM15_B_MAX = 0.75, 1.80
#: Descarte de metadatos malos: ver la nota en :func:`evaluar`.
MAX_DIF_HUBBLE = 30.0
RADIO_NED_SN = 15.0  # arcsec: la supernova misma
RADIO_NED_HOST = 40.0  # arcsec: la galaxia anfitriona

CACHE = RAIZ / "cache" / "curacion"


# --------------------------------------------------------------------- NED


def _cache_leer(clave: str) -> Any | None:
    f = CACHE / f"{clave}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            f.unlink(missing_ok=True)
    return None


def _cache_escribir(clave: str, valor: Any) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{clave}.json").write_text(json.dumps(valor))


#: De dónde salió el corrimiento al rojo.  Se guarda como código + nombre y la
#: traducción vive en frontend/i18n; guardado como frase, la interfaz en inglés
#: mostraba "NED, galaxia anfitriona UGC 00525".
FUENTES_Z = {
    "ned_sn": "NED, {nombre}",
    "ned_host": "NED, galaxia anfitriona {nombre}",
    "ned_otra_sn": "NED, otra supernova de la misma galaxia ({nombre})",
}


def _fuente(codigo: str, **params: Any) -> dict[str, Any]:
    return {
        "codigo": codigo,
        "params": params,
        "texto": FUENTES_Z[codigo].format(**params),
    }


def _anio_del_nombre(nombre: str) -> int | None:
    m = re.match(r"\s*SN\s*(\d{4})", nombre)
    return int(m.group(1)) if m else None


def consultar_ned(ra: float, dec: float, anio_maximo: int | None = None) -> dict[str, Any]:
    """Identidad y corrimiento al rojo desde NED, buscando por posición.

    ``anio_maximo`` es el año en que la supernova alcanzó su máximo.  Sirve para
    no confundirla con **otra** supernova de la misma galaxia: NED devolvió
    "SN 2000fo" a 3″ de un objeto de ZTF cuyo máximo fue en 2020.  En ese caso el
    corrimiento al rojo sigue sirviendo (es el de la galaxia anfitriona), pero el
    nombre no es de esta supernova y no debe aparecer en la ficha.
    """
    clave = f"ned_{ra:.5f}_{dec:+.5f}"
    guardado = _cache_leer(clave)
    if guardado is not None:
        return guardado

    from astropy import units as u
    from astropy.coordinates import SkyCoord
    from astroquery.ipac.ned import Ned

    # z_fuente va como {codigo, params, texto}, igual que los avisos: es texto
    # que se muestra en pantalla y la interfaz puede estar en inglés.
    resultado: dict[str, Any] = {
        "nombre_sn": None,
        "z": None,
        "z_fuente": None,
        "host": None,
        "z_host": None,
    }
    try:
        tabla = Ned.query_region(
            SkyCoord(ra, dec, unit="deg"), radius=RADIO_NED_HOST * u.arcsec
        )
    except Exception as exc:  # NED se cae seguido; seguimos sin este objeto
        resultado["error"] = f"{type(exc).__name__}: {exc}"
        _cache_escribir(clave, resultado)
        return resultado

    def _z(fila) -> float | None:
        try:
            v = float(tabla["Redshift"][fila])
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            return None

    # 'Separation' viene en minutos de arco
    for i in range(len(tabla)):
        sep = float(tabla["Separation"][i]) * 60.0
        tipo = str(tabla["Type"][i]).strip()
        nombre = str(tabla["Object Name"][i]).strip()
        if tipo != "SN" or sep > RADIO_NED_SN:
            continue
        anio = _anio_del_nombre(nombre)
        coincide = (
            anio_maximo is None or anio is None or abs(anio - anio_maximo) <= 1
        )
        z = _z(i)
        if coincide:
            resultado["nombre_sn"] = nombre
            if z is not None:
                resultado["z"] = z
                resultado["z_fuente"] = _fuente("ned_sn", nombre=nombre)
            break
        # Otra supernova de la misma galaxia: su z sirve, su nombre no.
        if z is not None and resultado["z"] is None:
            resultado["z"] = z
            resultado["z_fuente"] = _fuente("ned_otra_sn", nombre=nombre)

    if resultado["z"] is None:
        # sin z de la supernova, usamos la galaxia anfitriona más cercana con z
        mejor = None
        for i in range(len(tabla)):
            sep = float(tabla["Separation"][i]) * 60.0
            if not str(tabla["Type"][i]).strip().startswith("G"):
                continue
            z = _z(i)
            if z is None:
                continue
            if mejor is None or sep < mejor[0]:
                mejor = (sep, str(tabla["Object Name"][i]).strip(), z)
        if mejor:
            resultado["host"] = mejor[1]
            resultado["z_host"] = mejor[2]
            resultado["z"] = mejor[2]
            resultado["z_fuente"] = _fuente("ned_host", nombre=mejor[1])

    _cache_escribir(clave, resultado)
    return resultado


def consultar_extincion(ra: float, dec: float) -> float | None:
    """E(B−V) galáctico de Schlafly & Finkbeiner, vía el servicio DUST de IRSA."""
    clave = f"dust_{ra:.5f}_{dec:+.5f}"
    guardado = _cache_leer(clave)
    if guardado is not None:
        return guardado.get("ebv")

    url = (
        "https://irsa.ipac.caltech.edu/cgi-bin/DUST/nph-dust"
        f"?locstr={ra:.6f}+{dec:+.6f}+equ+j2000"
    )
    for intento in range(3):
        try:
            r = httpx.get(url, timeout=60.0, follow_redirects=True)
            r.raise_for_status()
            m = re.search(r"<meanValueSandF>\s*([\d.eE+-]+)", r.text)
            if m:
                ebv = float(m.group(1))
                _cache_escribir(clave, {"ebv": ebv})
                return ebv
        except Exception:
            pass
    return None


# ------------------------------------------------------------------ historias


def historias(datos: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Texto para la ficha, construido **sólo** con datos reales del objeto.

    Nada inventado: si no sabemos la galaxia anfitriona, no la mencionamos.
    """
    nombre = datos.get("nombre_sn") or datos["oid"]
    d = datos["distancia_hubble_mpc"]
    anios = d * 1e6 * C.ANIOS_LUZ_POR_PARSEC / 1e6  # en millones de años luz
    fecha = dt.datetime(1858, 11, 17) + dt.timedelta(days=datos["t_max"])
    mes_es = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ][fecha.month - 1]
    host = datos.get("host")

    donde_es = f" en la galaxia {host}" if host else ""
    donde_en = f" in the galaxy {host}" if host else ""

    def es_num(x: float, decimales: int = 0) -> str:
        """Número al estilo castellano: punto para miles, coma para decimales."""
        # "1,234,567.9" (formato ingles) -> "1.234.567,9"
        crudo = f"{x:,.{decimales}f}"
        return crudo.replace(",", "\x00").replace(".", ",").replace("\x00", ".")

    # Cuantas veces MAS DEBIL que el limite a simple vista (magnitud 6).
    # Como la magnitud crece al bajar el brillo, el exponente va (mag - 6).
    veces = 10 ** (0.4 * (datos["mag_max"] - 6.0))

    # Qué había vivo en la Tierra cuando la luz salió: el número de años solo
    # no se imagina, un bosque de helechos gigantes sí.
    periodo_es, vida_es = eras.epoca(anios, "es")
    periodo_en, vida_en = eras.epoca(anios, "en")

    es = (
        f"{nombre} es una supernova de tipo Ia que alcanzó su punto más brillante "
        f"en {mes_es} de {fecha.year}{donde_es}. Su luz viajó unos "
        f"{es_num(anios)} millones de años antes de llegar a los telescopios de "
        f"ZTF. Cuando esta estrella explotó, en la Tierra corría {periodo_es}: "
        f"{vida_es}. Faltaba muchísimo para que apareciera el primer ser humano. "
        f"En el máximo llegó a magnitud {es_num(datos['mag_max'], 1)}, "
        f"unas {es_num(veces)} veces más débil que la estrella más tenue que puedes "
        f"ver a simple vista."
    )

    en = (
        f"{nombre} is a Type Ia supernova that reached its brightest point in "
        f"{fecha.strftime('%B %Y')}{donde_en}. Its light travelled about "
        f"{anios:,.0f} million years before reaching the ZTF telescopes. When this "
        f"star exploded, Earth was in {periodo_en}: {vida_en}. The first human "
        f"being was still a very long way off. At maximum it reached magnitude "
        f"{datos['mag_max']:.1f}, about {veces:,.0f} times fainter than the "
        f"faintest star you can see with the naked eye."
    )
    return {"es": {"historia": es}, "en": {"historia": en}}


def dificultad(datos: dict[str, Any]) -> str:
    """Qué tan fácil es hacer la actividad con este objeto."""
    puntos = 0
    if datos["n_g"] >= 15:
        puntos += 1
    if datos["n_antes"] >= 4:
        puntos += 1
    if datos["hueco_max"] <= 3.0:
        puntos += 1
    if datos["mag_max"] <= 17.0:
        puntos += 1
    if datos["error_dm15"] <= 0.06:
        puntos += 1
    return "facil" if puntos >= 4 else ("intermedia" if puntos >= 2 else "desafio")


# ------------------------------------------------------------------ principal


async def evaluar(broker: AlerceZTF, oid: str, ra: float, dec: float) -> dict | None:
    """Aplica todos los filtros a un candidato.  Devuelve la ficha o ``None``."""
    # El año del máximo se necesita antes de preguntarle a NED, para no
    # confundir esta supernova con otra de la misma galaxia.  Se saca de la
    # detección más brillante, que basta para acertar el año.
    try:
        curva_previa = await broker.curva_de_luz(oid)
        g_previa = curva_previa.por_banda("g")
        if not g_previa:
            return {"oid": oid, "rechazo": "sin puntos en g"}
        mjd_brillante = min(g_previa, key=lambda d: d.mag).mjd
        anio = (dt.datetime(1858, 11, 17) + dt.timedelta(days=mjd_brillante)).year
        primera = min(d.mjd for d in curva_previa.detecciones)
        if primera < MJD_FOTOMETRIA_FORZADA:
            return {"oid": oid, "rechazo": "anterior a la fotometria forzada (2024)"}
    except Exception as exc:
        return {"oid": oid, "rechazo": f"sin curva de luz: {exc}"}

    ned = consultar_ned(ra, dec, anio_maximo=anio)
    z = ned.get("z")
    if z is None:
        return {"oid": oid, "rechazo": "sin corrimiento al rojo en NED"}
    if not (Z_MIN <= z <= Z_MAX):
        return {"oid": oid, "rechazo": f"z = {z:.4f} fuera del rango util"}

    curva = curva_previa  # ya la trajimos arriba para saber el año del máximo
    g = curva.por_banda("g")
    if len(g) < N_MIN_BANDA:
        return {"oid": oid, "rechazo": f"solo {len(g)} puntos en g"}

    try:
        foto = F.medir(curva, z=z, banda="g", banda_color="r", n_bootstrap=100)
    except F.MedicionImposible as exc:
        return {"oid": oid, "rechazo": str(exc)}
    except Exception as exc:
        return {"oid": oid, "rechazo": f"error midiendo: {type(exc).__name__}"}

    if not (MAG_MIN <= foto.maximo.mag_max <= MAG_MAX):
        return {
            "oid": oid,
            "rechazo": f"maximo g = {foto.maximo.mag_max:.2f} fuera de rango",
        }

    t = np.array([d.mjd for d in g])
    n_antes = int((t < foto.maximo.t_max).sum())
    if n_antes < N_MIN_ANTES:
        return {"oid": oid, "rechazo": f"solo {n_antes} puntos antes del maximo"}

    # Cobertura en la ventana crítica: sin ella, el ajuste rellena huecos y el
    # estudiante no tiene qué leer en el gráfico que dibuja a mano.
    a, b = VENTANA_CRITICA
    cerca = np.sort(t[(t >= foto.maximo.t_max + a) & (t <= foto.maximo.t_max + b)])
    if cerca.size < 5:
        return {"oid": oid, "rechazo": f"solo {cerca.size} puntos alrededor del maximo"}
    hueco = float(np.diff(cerca).max())
    if hueco > MAX_HUECO:
        return {"oid": oid, "rechazo": f"hueco de {hueco:.0f} d alrededor del maximo"}

    # Y el instante en que se lee Δm15 tiene que estar de verdad medido.
    t_15 = foto.maximo.t_max + 15.0 * (1 + z)
    if float(np.min(np.abs(t - t_15))) > MAX_DISTANCIA_A_15:
        return {"oid": oid, "rechazo": "sin mediciones cerca de t_max + 15 dias"}

    if not np.isfinite(foto.dm15.error_dm15):
        return {"oid": oid, "rechazo": "no se pudo estimar el error de dm15"}

    # Δm15 tiene que caer en el rango físico de las SN Ia normales.  Fuera de
    # él, o no es una Ia o el ajuste salió mal; en cualquier caso no sirve para
    # enseñar la relación de Phillips.
    from backend.calibracion import cargar as cargar_cal

    dm15_B = cargar_cal().survey("ZTF").dm15_B(foto.dm15.dm15)
    if not (DM15_B_MIN <= dm15_B <= DM15_B_MAX):
        return {"oid": oid, "rechazo": f"dm15(B) = {dm15_B:.2f} fuera del rango fisico"}

    ebv = consultar_extincion(ra, dec)
    if ebv is None:
        return {"oid": oid, "rechazo": "IRSA no entrego la extincion"}

    dist = C.calcular(foto, nivel="docente", ebv=ebv, z=z)

    # Último filtro: si la distancia se aleja muchísimo de la ley de Hubble, casi
    # siempre es porque NED asoció una galaxia anfitriona equivocada y el z está
    # mal.  Se descarta, y se deja constancia de cuántas se cayeron por aquí para
    # que el sesgo de esta selección quede a la vista.
    if dist.diferencia_porcentual is not None and abs(dist.diferencia_porcentual) > MAX_DIF_HUBBLE:
        return {
            "oid": oid,
            "rechazo": (
                f"difiere {dist.diferencia_porcentual:+.0f} % de Hubble "
                "(probable z equivocado)"
            ),
        }
    # La estampilla del MÁXIMO, no la del descubrimiento. En la alerta de
    # descubrimiento la supernova está en el límite de detección y no se ve:
    # en ZTF25ackdapv la primera estampilla es de magnitud 19,7 y la del máximo
    # de 15,3, sesenta veces más brillante.
    con_estampilla = [
        d for d in curva.detecciones if d.tiene_estampilla and d.banda == "g"
    ] or [d for d in curva.detecciones if d.tiene_estampilla]
    estampilla = (
        min(con_estampilla, key=lambda d: d.mag).candid if con_estampilla else None
    )
    clasif = await broker.clasificacion(oid)

    ficha: dict[str, Any] = {
        "oid": oid,
        "survey": "ZTF",
        "nombre_sn": ned.get("nombre_sn"),
        "host": ned.get("host"),
        "ra": ra,
        "dec": dec,
        "z": z,
        "z_fuente": ned.get("z_fuente"),
        "ebv": ebv,
        "t_max": foto.maximo.t_max,
        "mag_max": foto.maximo.mag_max,
        "dm15_g": foto.dm15.dm15,
        "error_dm15": foto.dm15.error_dm15,
        "color_max": foto.color_max,
        "n_g": len(g),
        "n_r": len(curva.por_banda("r")),
        "n_antes": n_antes,
        "hueco_max": hueco,
        "candid_estampilla": estampilla,
        "distancia_mpc": dist.distancia_mpc,
        "distancia_hubble_mpc": dist.distancia_hubble_mpc,
        "diferencia_porcentual": dist.diferencia_porcentual,
        "clasificacion": {
            "clasificador": clasif.clasificador,
            "version": clasif.version,
            "clase": clasif.clase,
            "probabilidad": clasif.probabilidad,
            "ranking": clasif.ranking,
        },
    }
    ficha["dificultad"] = dificultad(ficha)
    ficha["textos"] = historias(ficha)
    return ficha


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--objetivo", type=int, default=25, help="cuántas queremos")
    ap.add_argument("--candidatas", type=int, default=400)
    ap.add_argument("--prob-min", type=float, default=0.5)
    ap.add_argument("--salida", default=str(RAIZ / "data" / "catalogo_snia.json"))
    args = ap.parse_args()

    broker = AlerceZTF(cache_dir=str(RAIZ / "cache"))
    print(
        f"Buscando candidatas a SN Ia con {broker.clasificador} "
        f"v{broker.version_clasificador} (verificadas una por una)..."
    )

    # Se piden candidatas por las dos vías: el modelo plano de 21 clases y la
    # rama de transitorios.  Se solapan bastante, pero juntas dan más objetos.
    vistos: dict[str, tuple[float, float]] = {}
    for clasificador in (
        f"{broker.clasificador}_transient",
        broker.clasificador,
    ):
        for umbral in (args.prob_min, 0.85, 0.95):
            lote = await broker.buscar_por_clase(
                "SNIa",
                prob_min=umbral,
                ndet=(12, 2000),
                paginas=max(1, args.candidatas // 200 + 1),
                clasificador=clasificador,
                firstmjd=(MJD_FOTOMETRIA_FORZADA, 99999.0),
            )
            vistos.update(lote)
            print(f"  {clasificador} p≥{umbral}: {len(vistos)} candidatas acumuladas")
            if len(vistos) >= args.candidatas:
                break
        if len(vistos) >= args.candidatas:
            break

    print(f"\nVerificando la clase de {len(vistos)} candidatas...")
    sem = asyncio.Semaphore(8)
    confirmadas: list[tuple[str, float, float]] = []

    async def verificar(oid: str) -> None:
        # BHRF obligatorio: sin fila BHRF el objeto no entra, aunque otro
        # clasificador opine que es SNIa.
        async with sem:
            clasif = await broker.clasificacion(oid)
        if clasif and clasif.clase == "SNIa" and clasif.ranking == 1:
            confirmadas.append((oid, *vistos[oid]))

    await asyncio.gather(*(verificar(o) for o in vistos))
    print(f"  {len(confirmadas)} confirmadas como SNIa en ranking 1 "
          f"(de {len(vistos)} candidatas devueltas por la API)")

    print("\nEvaluando calidad, NED y extinción (esto tarda: NED es lento)...")
    fichas: list[dict] = []
    rechazos: dict[str, int] = {}
    # ALeRCE puede tener DOS oid para la misma supernova (p.ej. SN 2025oxy salio
    # como ZTF25aaxjntk y ZTF25aaxnchn). Sin esto, el curso veria la misma
    # supernova dos veces con distinto nombre.
    nombres_vistos: set[str] = set()
    posiciones: list[tuple[float, float]] = []

    def es_duplicada(ficha: dict) -> bool:
        if ficha["nombre_sn"] and ficha["nombre_sn"] in nombres_vistos:
            return True
        for ra0, dec0 in posiciones:
            dra = (ficha["ra"] - ra0) * np.cos(np.radians(ficha["dec"]))
            if np.hypot(dra, ficha["dec"] - dec0) * 3600 < 5.0:
                return True
        return False

    for i, (oid, ra, dec) in enumerate(sorted(confirmadas), 1):
        r = await evaluar(broker, oid, ra, dec)
        if r is None:
            continue
        if "rechazo" not in r and es_duplicada(r):
            clave = "duplicada de otra ya aceptada"
            rechazos[clave] = rechazos.get(clave, 0) + 1
            continue
        if "rechazo" in r:
            motivo = re.sub(r"[\d.,+-]+", "N", r["rechazo"])[:60]
            rechazos[motivo] = rechazos.get(motivo, 0) + 1
        else:
            fichas.append(r)
            if r["nombre_sn"]:
                nombres_vistos.add(r["nombre_sn"])
            posiciones.append((r["ra"], r["dec"]))
            print(f"  [{len(fichas):2d}] {oid}  {r['nombre_sn'] or '—':<12s} "
                  f"z={r['z']:.4f}  g_max={r['mag_max']:.2f}  "
                  f"Δm15(g)={r['dm15_g']:.2f}  {r['dificultad']}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(confirmadas)} revisadas, {len(fichas)} aceptadas")
        if len(fichas) >= args.objetivo:
            break

    await broker.aclose()

    if not fichas:
        print("ERROR: ninguna supernova pasó los filtros.", file=sys.stderr)
        print("Rechazos:", json.dumps(rechazos, indent=2, ensure_ascii=False))
        return 1

    fichas.sort(key=lambda f: ({"facil": 0, "intermedia": 1, "desafio": 2}[f["dificultad"]], f["mag_max"]))
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(
        json.dumps(
            {
                "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "survey": "ZTF",
                "clasificador": broker.clasificador,
                "version_clasificador": broker.version_clasificador,
                "criterios": {
                    "z": [Z_MIN, Z_MAX],
                    "mag_max_g": [MAG_MIN, MAG_MAX],
                    "n_min_g": N_MIN_BANDA,
                    "n_min_antes_del_maximo": N_MIN_ANTES,
                    "hueco_maximo_dias": MAX_HUECO,
                    "ventana_critica_dias": list(VENTANA_CRITICA),
                    "primera_deteccion_desde_mjd": MJD_FOTOMETRIA_FORZADA,
                },
                "objetos": fichas,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n{len(fichas)} supernovas escritas en {salida}")
    print(f"  fáciles: {sum(f['dificultad']=='facil' for f in fichas)}  "
          f"intermedias: {sum(f['dificultad']=='intermedia' for f in fichas)}  "
          f"desafío: {sum(f['dificultad']=='desafio' for f in fichas)}")
    dif = [abs(f["diferencia_porcentual"]) for f in fichas if f["diferencia_porcentual"]]
    if dif:
        print(f"  |distancia − Hubble| mediana: {np.median(dif):.1f} %")
    print("\nMotivos de rechazo más comunes:")
    for motivo, n in sorted(rechazos.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {n:4d}  {motivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
