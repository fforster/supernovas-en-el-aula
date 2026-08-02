"""Broker de Rubin/LSST — esqueleto / Rubin/LSST broker — stub.

Cuando ALeRCE sirva alertas de Rubin, esta clase se completa y el resto de la
aplicación no cambia: el pipeline científico, el frontend y los informes ya
trabajan con nombres de banda ('g', 'r', ...) y no con ``fid`` numéricos.

Lo que habrá que hacer aquí:

1. Apuntar a la API de Rubin de ALeRCE y traducir su esquema a
   :class:`~backend.brokers.base.CurvaDeLuz`.
2. Ampliar ``bandas`` a ``ugrizy``.
3. Añadir un bloque ``rubin`` en ``data/calibracion.json`` con la conversión
   Δm15(banda) → Δm15(B) y el término de color, recalculada con
   ``scripts/calibrar_dm15.py --survey rubin`` (el script ya acepta cualquier
   conjunto de bandas de sncosmo, p.ej. ``lsstg``/``lsstr``).
"""

from __future__ import annotations

from typing import Any

from .base import Broker, Clasificacion, CurvaDeLuz


class RubinNoDisponible(NotImplementedError):
    """Rubin aún no está conectado en esta versión."""


class AlerceRubin(Broker):
    survey = "LSST"
    bandas = ("u", "g", "r", "i", "z", "y")
    banda_principal = "g"
    banda_color = "r"
    clasificador = "por_definir"
    version_clasificador = "por_definir"

    _MENSAJE = (
        "El broker de Rubin todavía no está implementado. "
        "Ver backend/brokers/rubin.py para los pasos pendientes."
    )

    async def curva_de_luz(self, oid: str) -> CurvaDeLuz:
        raise RubinNoDisponible(self._MENSAJE)

    async def clasificacion(self, oid: str) -> Clasificacion | None:
        raise RubinNoDisponible(self._MENSAJE)

    async def cono(
        self, ra: float, dec: float, radio_arcsec: float, limite: int = 10
    ) -> list[dict[str, Any]]:
        raise RubinNoDisponible(self._MENSAJE)

    def url_estampilla(self, oid: str, candid: str, tipo: str = "science") -> str:
        raise RubinNoDisponible(self._MENSAJE)
