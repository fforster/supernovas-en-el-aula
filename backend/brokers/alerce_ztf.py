"""Cliente del broker ALeRCE para datos de ZTF / ALeRCE broker client for ZTF data.

Notas verificadas contra la API en producción (agosto 2026):

* ``GET /ztf/v1/objects/{oid}/lightcurve`` entrega fotometría de imagen diferencia
  (``magpsf``), que es exactamente lo que queremos para supernovas sobre galaxias.
* ``fid`` 1 = g, 2 = r.
* El parámetro para filtrar por clase en ``/objects/`` se llama ``class``, **no**
  ``class_name``.  La API descarta en silencio los parámetros que no conoce, así
  que usar el nombre equivocado no da error: simplemente devuelve objetos de
  cualquier clase, como si el filtro estuviera roto.  Con ``class`` la pureza es
  del 100 %.  ``ndet``, ``firstmjd`` y ``lastmjd`` son **rangos**: se pasan como
  dos valores, p.ej. ``ndet=[12, 2000]``.
* No existe endpoint público de fotometría forzada (404), aunque el clasificador
  BHRF sí fue entrenado con ella.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from .base import (
    Broker,
    BrokerError,
    Clasificacion,
    CurvaDeLuz,
    Deteccion,
    NoDeteccion,
)

log = logging.getLogger(__name__)

API = "https://api.alerce.online/ztf/v1"
AVRO = "https://avro.alerce.online"

#: fid -> nombre de banda
BANDAS = {1: "g", 2: "r", 3: "i"}

#: Clasificador acordado para este proyecto: modelo plano de 21 clases
#: entrenado con fotometría forzada.
CLASIFICADOR = "lc_classifier_BHRF_forced_phot"
VERSION_CLASIFICADOR = "2.1.0"

#: BHRF se entrenó con **fotometría forzada**, que ZTF sólo produce desde 2024.
#: Aplicarlo a objetos anteriores es usarlo fuera de su dominio, así que el
#: catálogo se restringe a supernovas posteriores a esta fecha y no hay
#: clasificador de respaldo: si BHRF no opinó, el objeto no entra.
MJD_FOTOMETRIA_FORZADA = 60310.0  # 1 de enero de 2024


class AlerceZTF(Broker):
    survey = "ZTF"
    bandas = ("g", "r")
    banda_principal = "g"
    banda_color = "r"
    clasificador = CLASIFICADOR
    version_clasificador = VERSION_CLASIFICADOR

    def __init__(
        self,
        cliente: httpx.AsyncClient | None = None,
        cache_dir: str | Path | None = None,
        ttl_horas: float = 24.0,
    ) -> None:
        self._cliente = cliente
        self._propio = cliente is None
        self._cache = Path(cache_dir) if cache_dir else None
        self._ttl = ttl_horas * 3600
        if self._cache:
            self._cache.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ HTTP

    async def _http(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,  # la API redirige /objects -> /objects/
                headers={"User-Agent": "alerce-epo-rubin/0.1 (educacion)"},
            )
        return self._cliente

    async def aclose(self) -> None:
        if self._cliente is not None and self._propio:
            await self._cliente.aclose()
            self._cliente = None

    def _ruta_cache(self, clave: str) -> Path | None:
        if not self._cache:
            return None
        seguro = clave.replace("/", "_").replace("?", "_").replace("&", "_")
        return self._cache / f"{seguro[:180]}.json"

    async def _get(self, ruta: str, params: dict[str, Any] | None = None) -> Any:
        """GET con caché en disco y reintentos con espera creciente."""
        clave = ruta if not params else f"{ruta}?{httpx.QueryParams(params)}"
        archivo = self._ruta_cache(clave)
        if archivo and archivo.exists():
            import time

            if time.time() - archivo.stat().st_mtime < self._ttl:
                try:
                    return json.loads(archivo.read_text())
                except json.JSONDecodeError:
                    archivo.unlink(missing_ok=True)

        cliente = await self._http()
        ultimo: Exception | None = None
        for intento in range(4):
            try:
                r = await cliente.get(f"{API}{ruta}", params=params)
                if r.status_code == 404:
                    raise BrokerError(f"No encontrado en ALeRCE: {ruta}")
                r.raise_for_status()
                datos = r.json()
                if archivo:
                    archivo.write_text(json.dumps(datos))
                return datos
            except BrokerError:
                raise
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                ultimo = exc
                if intento < 3:
                    await asyncio.sleep(1.5 * 2**intento)
        raise BrokerError(f"La API de ALeRCE falló en {ruta}: {ultimo}") from ultimo

    # ------------------------------------------------------------- endpoints

    async def curva_de_luz(self, oid: str) -> CurvaDeLuz:
        datos = await self._get(f"/objects/{oid}/lightcurve")
        return self._parsear_curva(oid, datos)

    def _parsear_curva(self, oid: str, datos: dict[str, Any]) -> CurvaDeLuz:
        dets: list[Deteccion] = []
        for d in datos.get("detections") or []:
            banda = BANDAS.get(d.get("fid"))
            mag, err = d.get("magpsf"), d.get("sigmapsf")
            if banda is None or mag is None or err is None:
                continue
            if not self._buena(d):
                continue
            dets.append(
                Deteccion(
                    mjd=float(d["mjd"]),
                    banda=banda,
                    mag=float(mag),
                    error=float(err),
                    candid=str(d["candid"]) if d.get("candid") else None,
                    tiene_estampilla=bool(d.get("has_stamp")),
                )
            )

        nodets: list[NoDeteccion] = []
        for n in datos.get("non_detections") or []:
            banda = BANDAS.get(n.get("fid"))
            lim = n.get("diffmaglim")
            if banda is None or lim is None or lim <= 0:
                continue
            nodets.append(
                NoDeteccion(mjd=float(n["mjd"]), banda=banda, limite=float(lim))
            )

        return CurvaDeLuz(
            oid=oid,
            survey=self.survey,
            detecciones=sorted(dets, key=lambda d: d.mjd),
            no_detecciones=sorted(nodets, key=lambda n: n.mjd),
        )

    @staticmethod
    def _buena(d: dict[str, Any]) -> bool:
        """Filtros de calidad para alertas de ZTF.

        **``drb`` se ignora a propósito.**  Es el real-bogus de deep learning que
        calcula **ZTF** y viaja en el paquete de alerta; ALeRCE sólo lo transmite,
        no lo produce.  Vale 0.0 en fuentes muy brillantes: en SN 2019np
        (ZTF19aacgslb) las seis detecciones del máximo (g ≈ 13,4) traen
        ``drb = 0.0`` pese a ser obviamente reales.  Como el fallo se concentra
        justo en las supernovas más brillantes —las mejores para el aula— el
        puntaje no sirve para este uso.

        Queda ``rb``, y los valores atípicos que se cuelen los descarta después
        el recorte sigma del ajuste (``backend.fotometria``).
        """
        if d.get("isdiffpos") not in (1, "1", "t", "T", True):
            return False  # el objeto se apagó respecto de la referencia
        if d.get("dubious"):
            return False
        rb = d.get("rb")
        return rb is None or rb > 0.4

    async def probabilidades(self, oid: str) -> list[dict[str, Any]]:
        return await self._get(f"/objects/{oid}/probabilities")

    @staticmethod
    def _extraer(
        filas: list[dict[str, Any]], nombre: str, version: str
    ) -> Clasificacion | None:
        propias = [
            p
            for p in filas
            if p.get("classifier_name") == nombre
            and str(p.get("classifier_version")) == version
        ]
        if not propias:
            return None
        mejor = min(propias, key=lambda p: p["ranking"])
        return Clasificacion(
            clasificador=nombre,
            version=version,
            clase=mejor["class_name"],
            probabilidad=float(mejor["probability"]),
            ranking=int(mejor["ranking"]),
            todas={p["class_name"]: float(p["probability"]) for p in propias},
        )

    async def clasificacion(self, oid: str) -> Clasificacion | None:
        """Veredicto BHRF.  ``None`` si el clasificador no corrió sobre el objeto."""
        try:
            filas = await self.probabilidades(oid)
        except BrokerError:
            return None
        return self._extraer(filas, self.clasificador, self.version_clasificador)

    async def cono(
        self, ra: float, dec: float, radio_arcsec: float, limite: int = 10
    ) -> list[dict[str, Any]]:
        datos = await self._get(
            "/objects/",
            {
                "ra": ra,
                "dec": dec,
                "radius": radio_arcsec,
                "page_size": limite,
                "count": "false",
            },
        )
        return datos.get("items", [])

    def url_estampilla(self, oid: str, candid: str, tipo: str = "science") -> str:
        """URL de nuestro propio endpoint, no la de ALeRCE.

        El PNG que sirve ALeRCE viene con estiramiento lineal y se ve casi
        negro; lo reescalamos nosotros a partir del FITS (ver
        ``backend.imagenes``).
        """
        return f"/api/estampilla/{oid}/{candid}/{tipo}.png"

    def url_estampilla_alerce(
        self, oid: str, candid: str, tipo: str = "science", formato: str = "fits"
    ) -> str:
        """URL original en ALeRCE, de donde bajamos los datos."""
        return f"{AVRO}/get_stamp?oid={oid}&candid={candid}&type={tipo}&format={formato}"

    async def fits_estampilla(self, oid: str, candid: str, tipo: str) -> bytes:
        """Descarga el recorte FITS con los valores reales del detector."""
        cliente = await self._http()
        url = self.url_estampilla_alerce(oid, candid, tipo, "fits")
        ultimo: Exception | None = None
        for intento in range(3):
            try:
                r = await cliente.get(url)
                r.raise_for_status()
                return r.content
            except httpx.HTTPError as exc:
                ultimo = exc
                if intento < 2:
                    await asyncio.sleep(1.0 * 2**intento)
        raise BrokerError(f"No se pudo bajar la estampilla {tipo} de {oid}: {ultimo}")

    # --------------------------------------------------- búsqueda verificada

    async def buscar_por_clase(
        self,
        clase: str = "SNIa",
        prob_min: float = 0.7,
        ndet: tuple[int, int] = (12, 2000),
        paginas: int = 5,
        por_pagina: int = 200,
        clasificador: str | None = None,
        firstmjd: tuple[float, float] | None = None,
    ) -> dict[str, tuple[float, float]]:
        """Objetos de una clase.  Devuelve ``{oid: (ra, dec)}``.

        ``clasificador`` permite usar la rama de transitorios
        (``lc_classifier_BHRF_forced_phot_transient``), que para supernovas da un
        conjunto de candidatas más limpio que el modelo plano.
        """
        encontrados: dict[str, tuple[float, float]] = {}
        for pagina in range(1, paginas + 1):
            lote = await self._get(
                "/objects/",
                {
                    "classifier": clasificador or self.clasificador,
                    "classifier_version": self.version_clasificador,
                    "class": clase,  # ojo: 'class', no 'class_name'
                    "probability": prob_min,
                    "ndet": list(ndet),
                    "page": pagina,
                    "page_size": por_pagina,
                    "count": "false",
                    **({"firstmjd": list(firstmjd)} if firstmjd else {}),
                },
            )
            items = lote.get("items", [])
            for o in items:
                encontrados.setdefault(o["oid"], (o["meanra"], o["meandec"]))
            if len(items) < por_pagina:
                break
        log.info("buscar_por_clase(%s): %d objetos", clase, len(encontrados))
        return encontrados


async def comprobar_filtro_clase(broker: AlerceZTF, clase: str = "SNIa") -> float:
    """Pureza del filtro ``class`` de ALeRCE, entre 0 y 1.

    Pide un lote con ``class=<clase>`` y comprueba objeto por objeto que la clase
    de ranking 1 sea efectivamente ésa.  Hay una prueba que lo llama para
    detectar una regresión en la API (o un cambio de nombre del parámetro, que es
    lo que nos costó caro al principio: con ``class_name`` la pureza era ~0).
    """
    encontrados = await broker.buscar_por_clase(clase, prob_min=0.7, paginas=1, por_pagina=50)
    if not encontrados:
        return 0.0
    clases = await asyncio.gather(*(broker.clasificacion(o) for o in encontrados))
    aciertos = sum(1 for c in clases if c and c.clase == clase and c.ranking == 1)
    return aciertos / len(encontrados)
