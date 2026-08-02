"""Interfaz común de brokers / Common broker interface.

Ésta es la costura por la que el proyecto migrará de ZTF a Rubin/LSST: la app
nunca habla directamente con una API de survey, sólo con esta interfaz.

This is the seam through which the project will migrate from ZTF to Rubin/LSST:
the app never talks to a survey API directly, only to this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Deteccion:
    """Una medición de brillo / a single brightness measurement."""

    mjd: float
    banda: str  # 'g', 'r', ... (nombre de banda, no un id numérico)
    mag: float
    error: float
    candid: str | None = None
    tiene_estampilla: bool = False

    def dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NoDeteccion:
    """Un límite superior: el survey miró y no vio nada.

    An upper limit: the survey looked and saw nothing.
    """

    mjd: float
    banda: str
    limite: float

    def dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CurvaDeLuz:
    oid: str
    survey: str
    detecciones: list[Deteccion] = field(default_factory=list)
    no_detecciones: list[NoDeteccion] = field(default_factory=list)

    def por_banda(self, banda: str) -> list[Deteccion]:
        """Detecciones de una banda, ordenadas en el tiempo."""
        return sorted(
            (d for d in self.detecciones if d.banda == banda), key=lambda d: d.mjd
        )

    @property
    def bandas(self) -> list[str]:
        return sorted({d.banda for d in self.detecciones})

    def dict(self) -> dict[str, Any]:
        return {
            "oid": self.oid,
            "survey": self.survey,
            "detecciones": [d.dict() for d in self.detecciones],
            "no_detecciones": [n.dict() for n in self.no_detecciones],
            "bandas": self.bandas,
        }


@dataclass
class Clasificacion:
    """Veredicto del clasificador de machine learning del broker."""

    clasificador: str
    version: str
    clase: str
    probabilidad: float
    ranking: int
    todas: dict[str, float] = field(default_factory=dict)

    def dict(self) -> dict[str, Any]:
        return asdict(self)


class BrokerError(RuntimeError):
    """La API del broker falló o devolvió algo inesperado."""


class Broker(ABC):
    """Contrato mínimo que cualquier broker debe cumplir para esta app."""

    #: Nombre legible del survey, p.ej. "ZTF"
    survey: str
    #: Bandas disponibles, en orden de longitud de onda
    bandas: tuple[str, ...]
    #: Banda usada como referencia para medir el máximo y Δm15
    banda_principal: str
    #: Banda usada para el color en el máximo
    banda_color: str
    #: Clasificador cuya opinión mostramos a docentes y estudiantes
    clasificador: str
    version_clasificador: str

    @abstractmethod
    async def curva_de_luz(self, oid: str) -> CurvaDeLuz:
        """Fotometría del objeto."""

    @abstractmethod
    async def clasificacion(self, oid: str) -> Clasificacion | None:
        """Clasificación del objeto según ``self.clasificador``."""

    @abstractmethod
    async def cono(
        self, ra: float, dec: float, radio_arcsec: float, limite: int = 10
    ) -> list[dict[str, Any]]:
        """Búsqueda en cono alrededor de una posición."""

    #: Las tres imágenes que acompañan a cada alerta, en el orden en que se
    #: explican: lo que vio el telescopio, cómo era antes, y la resta.
    TIPOS_ESTAMPILLA = ("science", "template", "difference")

    @abstractmethod
    def url_estampilla(self, oid: str, candid: str, tipo: str = "science") -> str:
        """URL de una de las imágenes de descubrimiento."""

    def urls_estampillas(self, oid: str, candid: str) -> dict[str, str]:
        """El triplete completo: ciencia, referencia y diferencia.

        Se muestran siempre las tres: la resta es la que explica de un vistazo
        por qué el brillo de la galaxia no contamina la medición, y es lo que
        hace evidente que ahí *apareció* algo que antes no estaba.
        """
        return {t: self.url_estampilla(oid, candid, t) for t in self.TIPOS_ESTAMPILLA}
