"""Pruebas del reescalado de estampillas."""

from __future__ import annotations

import io

import numpy as np
import pytest

from backend import imagenes


def cielo_con_fuente(
    lado: int = 63, cielo: float = 100.0, ruido: float = 5.0,
    brillo: float = 5000.0, pos: tuple[int, int] | None = None, semilla: int = 3,
) -> np.ndarray:
    """Recorte sintético: cielo con ruido más una fuente gaussiana."""
    rng = np.random.default_rng(semilla)
    d = rng.normal(cielo, ruido, (lado, lado))
    if brillo:
        cy, cx = pos if pos else (lado // 2, lado // 2)
        y, x = np.mgrid[0:lado, 0:lado]
        d += brillo * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * 1.5**2))
    return d


def test_la_fuente_central_queda_visible():
    """Lo esencial: la supernova está al centro y tiene que verse."""
    escala = imagenes.normalizar(cielo_con_fuente())
    assert escala[29:34, 29:34].max() > 0.8, "la fuente central salió apagada"


def test_el_ruido_del_fondo_se_ve():
    """El cielo no debe quedar recortado a negro puro.

    Una imagen astronómica sin grano parece un dibujo. Se comprueba que el fondo
    tenga variación (el ruido se ve) y que no esté ni aplastado contra el negro
    ni lavado hacia el blanco.
    """
    escala = imagenes.normalizar(cielo_con_fuente())
    fondo = np.concatenate([escala[:12, :].ravel(), escala[-12:, :].ravel()])
    assert fondo.std() > 0.02, "el ruido del fondo quedó recortado: se ve todo negro"
    assert 0.05 < fondo.mean() < 0.6, f"el fondo quedó en {fondo.mean():.2f}"
    assert (fondo <= 0.01).mean() < 0.5, "más de la mitad del fondo es negro puro"


def test_una_estrella_brillante_en_la_esquina_no_esconde_el_centro():
    """El techo se mide en el centro justamente para que esto no pase."""
    d = cielo_con_fuente(brillo=3000.0)
    d += 60000.0 * np.exp(
        -((np.mgrid[0:63, 0:63][0] - 5) ** 2 + (np.mgrid[0:63, 0:63][1] - 5) ** 2)
        / (2 * 2.0**2)
    )
    escala = imagenes.normalizar(d)
    assert escala[29:34, 29:34].max() > 0.7, "la estrella de la esquina se comió la escala"


def test_una_galaxia_brillante_fuera_del_centro_no_satura():
    """Regresión: la imagen de referencia de ZTF25ackdapv salía blanca.

    En la referencia la supernova todavía no existe, así que el centro está
    vacío; si el techo saliera sólo del centro, la galaxia de al lado saturaría.
    """
    d = cielo_con_fuente(brillo=0.0)  # centro sin fuente
    y, x = np.mgrid[0:63, 0:63]
    d += 8000.0 * np.exp(-((y - 20) ** 2 + (x - 45) ** 2) / (2 * 4.0**2))
    escala = imagenes.normalizar(d)
    saturados = (escala >= 0.99).mean()
    assert saturados < 0.10, f"{saturados:.0%} de la imagen saturada"


def test_sobrevive_a_los_nan():
    """Varios recortes traen NaN; con un solo percentil envenenado sale negra."""
    d = cielo_con_fuente()
    d[0, :] = np.nan
    d[:, 0] = np.nan
    escala = imagenes.normalizar(d)
    assert np.isfinite(escala).all()
    assert escala[29:34, 29:34].max() > 0.8


def test_imagen_plana_no_revienta():
    escala = imagenes.normalizar(np.full((63, 63), 42.0))
    assert np.isfinite(escala).all()


def test_todo_nan_da_error_claro():
    with pytest.raises(imagenes.ImagenNoDisponible):
        imagenes.normalizar(np.full((63, 63), np.nan))


def test_produce_un_png_valido():
    from PIL import Image

    png = imagenes.a_png(cielo_con_fuente(), lado=128)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    imagen = Image.open(io.BytesIO(png))
    assert imagen.size == (128, 128)
    assert imagen.mode == "L"


def test_el_png_no_sale_ni_todo_negro_ni_todo_blanco():
    from PIL import Image

    a = np.array(Image.open(io.BytesIO(imagenes.a_png(cielo_con_fuente()))))
    assert a.max() > 200, "no hay nada brillante"
    assert a.min() < 50, "no hay fondo oscuro"


def test_lee_fits_con_y_sin_gzip():
    import gzip

    from astropy.io import fits

    datos = cielo_con_fuente().astype(np.float32)
    crudo = io.BytesIO()
    fits.PrimaryHDU(datos).writeto(crudo)

    assert imagenes.leer_fits(crudo.getvalue()).shape == (63, 63)
    assert imagenes.leer_fits(gzip.compress(crudo.getvalue())).shape == (63, 63)
