"""Estampillas legibles / readable stamps.

Las imágenes que entrega ALeRCE en PNG vienen con un estiramiento lineal sobre
todo el recorte, y en una imagen astronómica eso significa que casi todo queda
negro: el cielo ocupa casi todos los niveles y la supernova se pierde.  Antes
esto se parcheaba con un ``filter: brightness()`` en CSS, que sube el brillo de
todo por igual —incluido el ruido— y no puede comprimir el rango dinámico.

Aquí se hace bien: se pide el **FITS**, que trae los valores reales del
detector, y se normaliza con ``astropy.visualization``.

La decisión que importa
-----------------------
El límite superior de la escala se calcula sobre la **zona central** del
recorte, no sobre la imagen completa.  La supernova está justo en el centro, y
en el recorte completo domina el cielo: escalando con el recorte entero, la
supernova sale saturada o —si hay una estrella brillante en una esquina—
directamente invisible.  Midiendo el centro, la supernova siempre queda dentro
del rango visible.

El estiramiento es asinh, que muestra a la vez la galaxia brillante y la
supernova más débil sin quemar ninguna de las dos.
"""

from __future__ import annotations

import gzip
import io
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

#: Fracción del ancho del recorte que se considera "la zona central".
#: 0.4 sobre un recorte de 63 px son ~25 px: la supernova y su galaxia, sin
#: tragarse el cielo de los bordes.
FRACCION_CENTRAL = 0.4

#: El piso se calcula con estadística de sigma-clipping sobre el recorte
#: completo: mediana + K·sigma del cielo.  Con percentiles fijos no funcionaba,
#: porque el nivel de cielo cambia mucho de un campo a otro (y algunos recortes
#: traen NaN, que envenenan cualquier percentil).
#:
#: K es **negativo** a propósito: el piso queda por debajo del nivel del cielo,
#: así el ruido de fondo cae dentro del rango visible y se ve como grano.  Con
#: K positivo el cielo salía recortado a negro puro, y una imagen astronómica
#: sin grano parece un dibujo: conviene que se note que son medidas reales, con
#: su ruido.
K_SIGMA_PISO = -2.0

#: El techo sale de la zona central: es el brillo de la supernova.
PERCENTIL_TECHO = 99.5

#: Techo alternativo, del recorte completo, para cuando el centro está vacío.
#: En la imagen de referencia la supernova todavía no existe: en ZTF25ackdapv el
#: centro de la referencia está a sólo 2,9 sigma del cielo, mientras que en el
#: resto de las imágenes está a 150-280 sigma.  Ese contraste es tan grande que
#: distinguir ambos casos con un umbral de 3 sigma es de sobra.
PERCENTIL_TECHO_GLOBAL = 99.0

#: Por debajo de esto se considera que el centro no tiene ninguna fuente.
SIGMAS_CENTRO_VACIO = 3.0

#: Parámetro del estiramiento asinh (``AsinhStretch``): más chico estira más el
#: extremo débil.  Hace falta un valor bien pequeño porque el rango dinámico es
#: enorme —la supernova está a ~280 sigma del cielo—, y con el 0,1 por defecto
#: el fondo se aplastaba contra el negro.
ASINH_A = 0.008

#: Tamaño de salida. Los recortes son de 63 px; ampliarlos en el servidor evita
#: que el navegador los interpole y los deje borrosos.
LADO_SALIDA = 256


class ImagenNoDisponible(RuntimeError):
    pass


def _region_central(datos: np.ndarray) -> np.ndarray:
    n = min(datos.shape)
    radio = max(4, int(n * FRACCION_CENTRAL / 2))
    cy, cx = datos.shape[0] // 2, datos.shape[1] // 2
    return datos[
        max(0, cy - radio) : cy + radio + 1,
        max(0, cx - radio) : cx + radio + 1,
    ]


def normalizar(datos: np.ndarray) -> np.ndarray:
    """De valores del detector a 0-1, con la zona central bien expuesta."""
    from astropy.stats import sigma_clipped_stats
    from astropy.visualization import AsinhStretch, ImageNormalize, ManualInterval

    datos = np.asarray(datos, dtype=float)
    finitos = np.isfinite(datos)
    if not finitos.any():
        raise ImagenNoDisponible("El recorte no tiene datos válidos.")

    # Varios recortes traen NaN (p.ej. ZTF25aavczxs). Se rellenan con la mediana
    # para que no salgan como agujeros negros en el cielo, y sobre todo para que
    # no envenenen los percentiles: con un solo NaN, np.percentile devuelve NaN
    # y la imagen entera sale negra.
    if not finitos.all():
        datos = np.where(finitos, datos, np.nanmedian(datos))

    # Nivel y ruido del cielo, ignorando las fuentes brillantes.
    _, mediana, sigma = sigma_clipped_stats(datos, sigma=3.0, maxiters=5)
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = float(np.std(datos)) or 1.0
    piso = float(mediana + K_SIGMA_PISO * sigma)

    centro = _region_central(datos)
    techo = float(np.percentile(centro, PERCENTIL_TECHO))

    # Si el centro está vacío, el techo saldría al nivel del cielo y cualquier
    # galaxia de al lado saturaría: la referencia salía como una mancha blanca.
    # En ese caso —y sólo en ese caso— se mide el techo en el recorte completo.
    # Cuando el centro SÍ tiene fuente, manda el centro, que es lo que protege a
    # la supernova de una estrella brillante en una esquina.
    if not np.isfinite(techo) or techo <= piso + SIGMAS_CENTRO_VACIO * sigma:
        techo = float(np.percentile(datos, PERCENTIL_TECHO_GLOBAL))

    # Y si aun así no hay rango (imagen plana), un mínimo para no dividir por 0.
    if not np.isfinite(techo) or techo <= piso:
        techo = piso + max(3 * sigma, 1e-6)

    norma = ImageNormalize(
        interval=ManualInterval(piso, techo),
        stretch=AsinhStretch(a=ASINH_A),
        clip=True,
    )
    return np.asarray(norma(datos), dtype=float)


def a_png(datos: np.ndarray, lado: int = LADO_SALIDA) -> bytes:
    """Normaliza y devuelve un PNG en escala de grises."""
    from PIL import Image

    escala = normalizar(datos)
    bytes8 = (np.clip(escala, 0.0, 1.0) * 255).astype(np.uint8)
    # El eje y de FITS crece hacia arriba y el de una imagen hacia abajo.
    imagen = Image.fromarray(np.flipud(bytes8), mode="L")
    # NEAREST a propósito: son 63 píxeles reales y queremos que se vean como
    # píxeles, no como una mancha suavizada que aparenta más resolución.
    imagen = imagen.resize((lado, lado), Image.NEAREST)
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


def leer_fits(crudo: bytes) -> np.ndarray:
    """Datos del FITS que entrega ALeRCE (viene comprimido con gzip)."""
    from astropy.io import fits

    contenido = crudo
    if crudo[:2] == b"\x1f\x8b":
        contenido = gzip.decompress(crudo)
    with fits.open(io.BytesIO(contenido), memmap=False) as hdul:
        for hdu in hdul:
            if hdu.data is not None:
                return np.asarray(hdu.data, dtype=float)
    raise ImagenNoDisponible("El FITS no traía ninguna imagen.")


def procesar(crudo: bytes, cache: Path | None = None) -> bytes:
    png = a_png(leer_fits(crudo))
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(png)
    return png
