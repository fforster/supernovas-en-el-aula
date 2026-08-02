"""Dibujo explicativo de una curva de luz / schematic light curve.

Antes de medir hay que entender qué se mide.  Este esquema muestra, sobre una
curva de tipo Ia idealizada, dónde está el máximo, qué son ``t_max`` y
``m_max``, y qué significa Δm15.

Se genera aquí, en Python, y no en el navegador, para tener **un solo dibujo**:
el mismo SVG se inyecta en la página y se imprime en la guía del estudiante.
Usa las clases CSS del proyecto (``.eje``, ``.rejilla``, ...), así que hereda
los colores y funciona igual en modo claro y oscuro.
"""

from __future__ import annotations

#: Curva de luz típica de una SN Ia en la banda B, en magnitudes **relativas al
#: máximo** y fase en días desde el máximo.  Los valores reproducen una
#: supernova normal, de Δm15 ≈ 1,1: sube en unas tres semanas y baja mucho más
#: lento.  Es un dibujo explicativo, no un ajuste: para medir de verdad están
#: los datos reales.
FORMA = [
    (-18, 3.90), (-16, 3.10), (-14, 2.40), (-12, 1.80), (-10, 1.32),
    (-8, 0.92), (-6, 0.58), (-4, 0.30), (-2, 0.10), (0, 0.00),
    (2, 0.06), (4, 0.22), (6, 0.45), (8, 0.72), (10, 0.99),
    (12, 1.24), (15, 1.10 + 0.48), (18, 1.85), (21, 2.02), (24, 2.15),
    (28, 2.28), (32, 2.40), (36, 2.50), (40, 2.58),
]

#: Δm15 del dibujo: cuánto ha bajado la curva 15 días después del máximo.
DM15_DIBUJO = 1.58

TEXTOS = {
    "es": {
        "titulo": "Qué vamos a medir",
        "eje_x": "Días",
        "eje_y": "Magnitud",
        "mas_brillante": "↑ más brillante",
        "maximo": "máximo",
        "t_max_corto": "t(máx)",
        "m_max_corto": "m(máx)",
        "t_max": "t(máx): el día más brillante",
        "m_max": "m(máx): qué tan brillante llegó a verse",
        "quince": "15 días después",
        "dm15": "Δm15",
        "dm15_pie": "cuánto se apagó en esos 15 días",
        "alt": (
            "Dibujo de una curva de luz de supernova tipo Ia. El brillo sube "
            "durante unas tres semanas hasta un máximo y después baja poco a "
            "poco. Se marcan el día del máximo, la magnitud en el máximo, y la "
            "diferencia de magnitud entre el máximo y 15 días después, que es "
            "Δm15."
        ),
    },
    "en": {
        "titulo": "What we are going to measure",
        "eje_x": "Days",
        "eje_y": "Magnitude",
        "mas_brillante": "↑ brighter",
        "maximo": "peak",
        "t_max_corto": "t(peak)",
        "m_max_corto": "m(peak)",
        "t_max": "t(peak): the brightest day",
        "m_max": "m(peak): how bright it got",
        "quince": "15 days later",
        "dm15": "Δm15",
        "dm15_pie": "how much it faded in those 15 days",
        "alt": (
            "Sketch of a Type Ia supernova light curve. The brightness rises "
            "for about three weeks to a peak and then slowly fades. The day of "
            "maximum, the magnitude at maximum, and the magnitude difference "
            "between the peak and 15 days later — which is Δm15 — are marked."
        ),
    },
}

ANCHO, ALTO = 720, 400
# abajo hay sitio de sobra: si no, el título del eje se pega a las
# etiquetas t(máx) y +15 d
MARGEN = {"i": 64, "d": 150, "a": 30, "b": 64}  # derecha ancha: caben etiquetas


def curva_esquematica(idioma: str = "es") -> str:
    """SVG del dibujo explicativo."""
    t = TEXTOS.get(idioma, TEXTOS["es"])
    util_x = ANCHO - MARGEN["i"] - MARGEN["d"]
    util_y = ALTO - MARGEN["a"] - MARGEN["b"]

    x0, x1 = -20.0, 42.0
    # el rango cubre toda la curva: empieza 3,9 mag bajo el máximo
    y0, y1 = -0.5, 4.15  # magnitud relativa; el eje va invertido

    def ex(dia: float) -> float:
        return MARGEN["i"] + (dia - x0) / (x1 - x0) * util_x

    def ey(mag: float) -> float:
        return MARGEN["a"] + (mag - y0) / (y1 - y0) * util_y

    p: list[str] = [
        f'<svg viewBox="0 0 {ANCHO} {ALTO}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="{t["alt"]}">'
    ]

    # ------------------------------------------------------------------ ejes
    p.append(
        f'<line class="eje" x1="{MARGEN["i"]}" y1="{MARGEN["a"] + util_y}" '
        f'x2="{MARGEN["i"] + util_x}" y2="{MARGEN["a"] + util_y}"/>'
        f'<line class="eje" x1="{MARGEN["i"]}" y1="{MARGEN["a"]}" '
        f'x2="{MARGEN["i"]}" y2="{MARGEN["a"] + util_y}"/>'
    )
    p.append(
        f'<text class="eje-titulo" x="{MARGEN["i"] + util_x / 2}" y="{ALTO - 14}" '
        f'text-anchor="middle">{t["eje_x"]}</text>'
        f'<text class="eje-titulo" x="18" y="{MARGEN["a"] + util_y / 2}" '
        f'text-anchor="middle" transform="rotate(-90 18 '
        f'{MARGEN["a"] + util_y / 2})">{t["eje_y"]}</text>'
        f'<text class="eje-texto" x="{MARGEN["i"] + 4}" y="{MARGEN["a"] - 10}" '
        f'text-anchor="start">{t["mas_brillante"]}</text>'
    )

    # --------------------------------------------------------------- la curva
    puntos = " ".join(f"{ex(d):.1f},{ey(m):.1f}" for d, m in FORMA)
    p.append(f'<polyline class="esquema__curva" points="{puntos}"/>')

    # --------------------------------------------- máximo y quince días después
    xm, ym = ex(0), ey(0.0)
    x15, y15 = ex(15), ey(DM15_DIBUJO)

    # líneas guía
    p.append(
        f'<line class="esquema__guia" x1="{xm}" y1="{ym}" x2="{xm}" '
        f'y2="{MARGEN["a"] + util_y}"/>'
        f'<line class="esquema__guia" x1="{MARGEN["i"]}" y1="{ym}" x2="{xm}" y2="{ym}"/>'
        f'<line class="esquema__guia" x1="{x15}" y1="{y15}" x2="{x15}" '
        f'y2="{MARGEN["a"] + util_y}"/>'
        f'<line class="esquema__guia" x1="{MARGEN["i"]}" y1="{y15}" x2="{x15}" y2="{y15}"/>'
    )

    # la flecha doble de Δm15, justo a la derecha del punto de +15 días
    xf = x15 + 26
    p.append(
        f'<line class="esquema__flecha" x1="{xf}" y1="{ym}" x2="{xf}" y2="{y15}"/>'
        f'<polygon class="esquema__punta" points="'
        f'{xf},{ym} {xf - 5},{ym + 11} {xf + 5},{ym + 11}"/>'
        f'<polygon class="esquema__punta" points="'
        f'{xf},{y15} {xf - 5},{y15 - 11} {xf + 5},{y15 - 11}"/>'
        f'<line class="esquema__guia" x1="{xm}" y1="{ym}" x2="{xf + 8}" y2="{ym}"/>'
        f'<line class="esquema__guia" x1="{x15}" y1="{y15}" x2="{xf + 8}" y2="{y15}"/>'
    )

    p.append(
        f'<circle class="esquema__punto" cx="{xm}" cy="{ym}" r="6"/>'
        f'<circle class="esquema__punto esquema__punto--15" cx="{x15}" cy="{y15}" r="6"/>'
    )

    # ------------------------------------------------------------- etiquetas
    p.append(
        f'<text class="esquema__etiqueta" x="{xm}" y="{ym - 14}" '
        f'text-anchor="middle">{t["maximo"]}</text>'
        f'<text class="esquema__nota" x="{xm + 4}" y="{MARGEN["a"] + util_y + 20}" '
        f'text-anchor="middle">{t["t_max_corto"]}</text>'
        f'<text class="esquema__nota" x="{MARGEN["i"] - 8}" y="{ym + 4}" '
        f'text-anchor="end">{t["m_max_corto"]}</text>'
        f'<text class="esquema__nota" x="{x15}" y="{MARGEN["a"] + util_y + 20}" '
        f'text-anchor="middle">+15 d</text>'
    )
    p.append(
        f'<text class="esquema__dm15" x="{xf + 14}" y="{(ym + y15) / 2 + 2}" '
        f'text-anchor="start">{t["dm15"]}</text>'
        f'<text class="esquema__nota" x="{xf + 14}" y="{(ym + y15) / 2 + 20}" '
        f'text-anchor="start">{t["quince"]}</text>'
    )

    p.append("</svg>")
    return "".join(p)


# ---------------------------------------------------------------------------
# Ley del inverso del cuadrado
# ---------------------------------------------------------------------------

TEXTOS_LEY = {
    "es": {
        "fuente": "supernova",
        "d": "distancia d",
        "d2": "2d",
        "d3": "3d",
        "c1": "1 cuadrado",
        "c4": "4 cuadrados",
        "c9": "9 cuadrados",
        "b1": "brillo × 1",
        "b4": "× 1/4",
        "b9": "× 1/9",
        "alt": (
            "Dibujo de la ley del inverso del cuadrado. La luz de una supernova "
            "sale en todas direcciones. Al doble de distancia la misma luz se "
            "reparte sobre cuatro veces más superficie, así que el brillo cae a "
            "un cuarto; al triple de distancia se reparte sobre nueve veces más "
            "superficie y el brillo cae a un noveno."
        ),
    },
    "en": {
        "fuente": "supernova",
        "d": "distance d",
        "d2": "2d",
        "d3": "3d",
        "c1": "1 square",
        "c4": "4 squares",
        "c9": "9 squares",
        "b1": "brightness × 1",
        "b4": "× 1/4",
        "b9": "× 1/9",
        "alt": (
            "Sketch of the inverse square law. Light from a supernova spreads in "
            "all directions. At twice the distance the same light is spread over "
            "four times the area, so the brightness drops to a quarter; at three "
            "times the distance it spreads over nine times the area and the "
            "brightness drops to a ninth."
        ),
    },
}

#: Inclinación de las pantallas, para que se vean en perspectiva y no de canto.
SESGO = 0.34


def _pantalla(cx: float, cy: float, h: float, n: int) -> str:
    """Una pantalla cuadrada en perspectiva, dividida en n×n celdas.

    Se dibuja como paralelogramo: ``O`` es la esquina superior izquierda, ``U``
    el vector que recorre el ancho (inclinado) y ``V`` el que baja.
    """
    ox, oy = cx - h, cy - h - h * SESGO
    ux, uy = 2 * h, 2 * h * SESGO
    vx, vy = 0.0, 2 * h

    partes = [
        f'<polygon class="ley__pantalla" points="'
        f"{ox:.1f},{oy:.1f} {ox + ux:.1f},{oy + uy:.1f} "
        f'{ox + ux + vx:.1f},{oy + uy + vy:.1f} {ox + vx:.1f},{oy + vy:.1f}"/>'
    ]
    for i in range(1, n):
        f = i / n
        partes.append(
            f'<line class="ley__celda" x1="{ox + f * ux:.1f}" y1="{oy + f * uy:.1f}" '
            f'x2="{ox + f * ux + vx:.1f}" y2="{oy + f * uy + vy:.1f}"/>'
        )
        partes.append(
            f'<line class="ley__celda" x1="{ox + f * vx:.1f}" y1="{oy + f * vy:.1f}" '
            f'x2="{ox + ux + f * vx:.1f}" y2="{oy + uy + f * vy:.1f}"/>'
        )
    return "".join(partes)


def ley_inversa(idioma: str = "es") -> str:
    """SVG de la ley del inverso del cuadrado.

    Las tres pantallas están a distancias 1d, 2d y 3d de la fuente y su tamaño
    crece en proporción, así que los rayos que salen de la supernova pasan
    exactamente por las esquinas de las tres: es la misma luz repartida sobre
    1, 4 y 9 cuadrados.
    """
    t = TEXTOS_LEY.get(idioma, TEXTOS_LEY["es"])
    ancho, alto = 700, 380
    sx, cy = 54.0, 176.0
    k = 0.22  # semitamaño por unidad de distancia

    p: list[str] = [
        f'<svg viewBox="0 0 {ancho} {alto}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="{t["alt"]}">'
    ]

    pantallas = []
    for i, dist in enumerate((130.0, 260.0, 390.0), start=1):
        pantallas.append((sx + dist, k * dist, i))

    # Rayos hasta las esquinas de la pantalla más lejana: por construcción pasan
    # también por las esquinas de las dos más cercanas.
    cx3, h3, _ = pantallas[-1]
    for ex, ey in (
        (cx3 - h3, cy - h3 - h3 * SESGO),
        (cx3 + h3, cy - h3 + h3 * SESGO),
        (cx3 + h3, cy + h3 + h3 * SESGO),
        (cx3 - h3, cy + h3 - h3 * SESGO),
    ):
        p.append(
            f'<line class="ley__rayo" x1="{sx:.1f}" y1="{cy:.1f}" '
            f'x2="{ex:.1f}" y2="{ey:.1f}"/>'
        )

    # De atrás hacia adelante, para que la más chica quede encima.
    for cx, h, n in reversed(pantallas):
        p.append(_pantalla(cx, cy, h, n))

    p.append(f'<circle class="ley__fuente" cx="{sx:.1f}" cy="{cy:.1f}" r="8"/>')
    p.append(
        f'<text class="ley__nota" x="{sx:.1f}" y="{cy - 18:.1f}" '
        f'text-anchor="middle">{t["fuente"]}</text>'
    )

    etiquetas = (
        (pantallas[0], t["d"], t["c1"], t["b1"]),
        (pantallas[1], t["d2"], t["c4"], t["b4"]),
        (pantallas[2], t["d3"], t["c9"], t["b9"]),
    )
    for (cx, h, _), dist, celdas, brillo in etiquetas:
        base = cy + h + h * SESGO + 26
        p.append(
            f'<text class="ley__etiqueta" x="{cx:.1f}" y="{base:.1f}" '
            f'text-anchor="middle">{dist}</text>'
            f'<text class="ley__nota" x="{cx:.1f}" y="{base + 17:.1f}" '
            f'text-anchor="middle">{celdas}</text>'
            f'<text class="ley__brillo" x="{cx:.1f}" y="{base + 35:.1f}" '
            f'text-anchor="middle">{brillo}</text>'
        )

    p.append("</svg>")
    return "".join(p)
