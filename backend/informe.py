"""Descargas e informes / downloads and reports.

Genera lo que el docente se lleva a la sala: los datos en CSV y una hoja
imprimible con la guía del estudiante y la pauta de corrección.
"""

from __future__ import annotations

from .brokers.base import CurvaDeLuz

#: Nombres de banda que ve el estudiante, sin jerga.
ETIQUETA_BANDA = {
    "es": {"g": "g (verde)", "r": "r (rojo)"},
    "en": {"g": "g (green)", "r": "r (red)"},
}


def csv_curva(
    curva: CurvaDeLuz,
    idioma: str = "es",
    locale_es: bool = True,
    incluir_no_detecciones: bool = False,
) -> str:
    """Los datos, listos para abrir en Excel o LibreOffice.

    ``locale_es`` usa punto y coma como separador y coma decimal, que es lo que
    esperan las planillas configuradas en español.  Con la coma decimal y el
    separador por defecto, Excel en español mete todas las columnas en una sola.
    """
    sep = ";" if locale_es else ","

    def num(x: float, d: int = 5) -> str:
        s = f"{x:.{d}f}"
        return s.replace(".", ",") if locale_es else s

    if idioma == "en":
        cabecera = ["mjd", "days_since_first", "band", "magnitude", "error", "type"]
    else:
        cabecera = ["mjd", "dias_desde_la_primera", "banda", "magnitud", "error", "tipo"]

    filas = [sep.join(cabecera)]
    if not curva.detecciones:
        return "\n".join(filas)

    t0 = min(d.mjd for d in curva.detecciones)
    for d in sorted(curva.detecciones, key=lambda x: x.mjd):
        filas.append(
            sep.join(
                [
                    num(d.mjd),
                    num(d.mjd - t0, 3),
                    d.banda,
                    num(d.mag, 3),
                    num(d.error, 3),
                    "deteccion" if idioma == "es" else "detection",
                ]
            )
        )
    if incluir_no_detecciones:
        for n in sorted(curva.no_detecciones, key=lambda x: x.mjd):
            filas.append(
                sep.join(
                    [
                        num(n.mjd),
                        num(n.mjd - t0, 3),
                        n.banda,
                        num(n.limite, 3),
                        "",
                        "limite" if idioma == "es" else "upper_limit",
                    ]
                )
            )
    return "\n".join(filas) + "\n"


TEXTOS = {
    "es": {
        "imprimir": "Imprimir",
        "datos_de": "Datos de",
        "pauta": "Pauta de corrección",
        "pasos": "Tu misión",
        "paso1": "Grafica los datos de la tabla: los días en el eje horizontal y la "
                 "magnitud en el vertical. ¡Ojo! El eje de magnitud va al revés: los "
                 "números más chicos (más brillante) van arriba.",
        "paso2": "Marca el punto más brillante. ¿En qué día ocurrió y qué magnitud tenía?",
        "paso3": "Busca la magnitud 15 días después del máximo. La diferencia entre "
                 "esa magnitud y la del máximo es Δm15. ¿Cuánto te dio?",
        "paso4": "Calcula la distancia. Suponemos que todas las supernovas de tipo Ia "
                 "brillan igual de verdad, con magnitud absoluta M = −19,3.",
        "paso5": "¿A cuántos millones de años luz corresponde? (1 pársec = 3,26 años luz)",
        "datos": "Los datos",
        "nota_datos": "Mediciones reales del telescopio ZTF, entregadas por el broker "
                      "ALeRCE. La banda g es luz verde y la banda r, luz roja.",
        "papel": "Papel para graficar",
        "nota_papel": "Los ejes ya están puestos en el rango de esta supernova.",
        "dia": "Día", "banda": "Banda", "mag": "Magnitud",
        "nota_pauta": "Los valores vienen del ajuste automático. Es normal que el "
                      "resultado de los estudiantes difiera un 10–20 %: la técnica "
                      "misma tiene esa precisión, y las galaxias además se mueven.",
        "eje_x": "Días desde la primera medición",
        "eje_y": "Magnitud (más chico = más brillante)",
        "no_medible": "No se pudo medir esta curva de luz automáticamente.",
        # coma decimal: en la hoja en inglés va con punto
        "formula_distancia": "M = −19,3     μ = m − M     d = 10^((μ+5)/5) pc",
        "de_donde_distancia": "De dónde sale la distancia (para el docente)",
        "de_donde_texto": (
            "La luz se diluye con la distancia: al alejarse d, la energía se "
            "reparte sobre una esfera de área 4πd², así que el flujo cae como "
            "1/d². En magnitudes eso se escribe μ = m − M = 5·log₁₀(d/10 pc). "
            "La luminosidad intrínseca se cancela al restar, de modo que μ —el "
            "módulo de distancia— depende SÓLO de la distancia: medir μ y medir "
            "la distancia son la misma operación, en distintas unidades "
            "(d = 10^((μ+5)/5) pársecs). El problema es que hace falta M, que no "
            "se puede medir; por eso se usan las SN Ia, que explotan todas con "
            "casi la misma masa y por lo tanto tienen M_B ≈ −19,3. Δm15 corrige "
            "el resto: las que se apagan más lento son algo más luminosas."
        ),
        "que_medimos": "Qué vamos a medir",
        "que_medimos_texto": (
            "Del gráfico salen tres cosas: el día del máximo t(máx), la magnitud "
            "en el máximo m(máx), y Δm15, que es cuánta magnitud perdió la "
            "supernova en los 15 días siguientes al máximo. Como todas las "
            "supernovas de tipo Ia emiten casi la misma luz, comparar cuánta "
            "emitió con cuánta nos llega da la distancia."
        ),
    },
    "en": {
        "imprimir": "Print",
        "datos_de": "Data from",
        "pauta": "Answer key",
        "pasos": "Your mission",
        "paso1": "Plot the data from the table: days on the horizontal axis and "
                 "magnitude on the vertical one. Careful! The magnitude axis is "
                 "upside down: smaller numbers (brighter) go at the top.",
        "paso2": "Mark the brightest point. On which day did it happen, and what "
                 "magnitude did it have?",
        "paso3": "Find the magnitude 15 days after the peak. The difference between "
                 "that magnitude and the peak one is Δm15. What did you get?",
        "paso4": "Work out the distance. We assume every Type Ia supernova really "
                 "shines the same, with absolute magnitude M = −19.3.",
        "paso5": "How many million light years is that? (1 parsec = 3.26 light years)",
        "datos": "The data",
        "nota_datos": "Real measurements from the ZTF telescope, served by the ALeRCE "
                      "broker. Band g is green light and band r is red light.",
        "papel": "Graph paper",
        "nota_papel": "The axes are already set to this supernova's range.",
        "dia": "Day", "banda": "Band", "mag": "Magnitude",
        "nota_pauta": "These values come from the automatic fit. A 10–20 % difference "
                      "from the students' result is normal: that is the accuracy of "
                      "the technique, and galaxies also move on their own.",
        "eje_x": "Days since the first measurement",
        "eje_y": "Magnitude (smaller = brighter)",
        "no_medible": "This light curve could not be measured automatically.",
        "formula_distancia": "M = −19.3     μ = m − M     d = 10^((μ+5)/5) pc",
        "de_donde_distancia": "Where the distance comes from (for teachers)",
        "de_donde_texto": (
            "Light thins out with distance: after travelling d, the energy is "
            "spread over a sphere of area 4πd², so the flux falls as 1/d². In "
            "magnitudes that reads μ = m − M = 5·log₁₀(d/10 pc). The intrinsic "
            "luminosity cancels in the subtraction, so μ — the distance modulus "
            "— depends ONLY on distance: measuring μ and measuring the distance "
            "are the same operation in different units "
            "(d = 10^((μ+5)/5) parsecs). The catch is that you need M, which "
            "cannot be measured; hence Type Ia supernovae, which all explode at "
            "almost the same mass and so have M_B ≈ −19.3. Δm15 corrects the "
            "rest: the ones that fade more slowly are slightly more luminous."
        ),
        "que_medimos": "What we are going to measure",
        "que_medimos_texto": (
            "Three things come out of the plot: the day of maximum t(peak), the "
            "magnitude at maximum m(peak), and Δm15, the magnitude the supernova "
            "lost in the 15 days after the peak. Since all Type Ia supernovae "
            "give off almost the same light, comparing how much it gave off with "
            "how much reaches us gives the distance."
        ),
    },
}


def papel_milimetrado(rangos: dict[str, float], idioma: str = "es") -> str:
    """SVG de papel para graficar, con los ejes ya en el rango del objeto.

    Se genera por objeto en vez de usar una cuadrícula genérica para que los
    estudiantes no pierdan la clase eligiendo escalas: los números ya están.
    """
    txt = TEXTOS.get(idioma, TEXTOS["es"])
    ancho, alto = 700, 500
    ml, mr, ma, mb = 60, 20, 24, 50
    util_x, util_y = ancho - ml - mr, alto - ma - mb

    t0, t1 = rangos["t_min"], rangos["t_max"]
    m0, m1 = rangos["mag_min"], rangos["mag_max"]

    # ~10 divisiones grandes en cada eje, con subdivisiones finas de 1/5
    paso_t = max(1.0, round((t1 - t0) / 10))
    paso_m = max(0.1, round((m1 - m0) / 8 * 2) / 2)

    p = [f'<svg viewBox="0 0 {ancho} {alto}" xmlns="http://www.w3.org/2000/svg" role="img" '
         f'aria-label="{txt["papel"]}">']

    t = t0
    while t <= t1 + 1e-9:
        for k in range(5):
            tt = t + k * paso_t / 5
            if tt > t1:
                break
            x = ml + (tt - t0) / (t1 - t0) * util_x
            clase = "papel-linea--fuerte" if k == 0 else "papel-linea"
            p.append(f'<line class="{clase}" x1="{x:.1f}" y1="{ma}" x2="{x:.1f}" y2="{ma+util_y}"/>')
        x = ml + (t - t0) / (t1 - t0) * util_x
        p.append(f'<text class="papel-texto" x="{x:.1f}" y="{ma+util_y+14}" '
                 f'text-anchor="middle">{t:.0f}</text>')
        t += paso_t

    m = m0
    while m <= m1 + 1e-9:
        for k in range(5):
            mm = m + k * paso_m / 5
            if mm > m1:
                break
            y = ma + (mm - m0) / (m1 - m0) * util_y
            clase = "papel-linea--fuerte" if k == 0 else "papel-linea"
            p.append(f'<line class="{clase}" x1="{ml}" y1="{y:.1f}" x2="{ml+util_x}" y2="{y:.1f}"/>')
        y = ma + (m - m0) / (m1 - m0) * util_y
        p.append(f'<text class="papel-texto" x="{ml-6}" y="{y+3:.1f}" '
                 f'text-anchor="end">{m:.1f}</text>')
        m += paso_m

    p.append(f'<text class="papel-texto" x="{ml+util_x/2}" y="{alto-14}" '
             f'text-anchor="middle" style="font-size:11px">{txt["eje_x"]}</text>')
    p.append(f'<text class="papel-texto" x="14" y="{ma+util_y/2}" text-anchor="middle" '
             f'style="font-size:11px" transform="rotate(-90 14 {ma+util_y/2})">'
             f'{txt["eje_y"]}</text>')
    p.append("</svg>")
    return "".join(p)


def filas_tabla(curva: CurvaDeLuz, idioma: str = "es") -> list[tuple[str, str, str, str]]:
    """Las mediciones, formateadas para la hoja impresa."""
    dets = curva.detecciones
    if not dets:
        return []
    t0 = min(d.mjd for d in dets)
    coma = idioma == "es"

    def n(x: float, d: int) -> str:
        s = f"{x:.{d}f}"
        return s.replace(".", ",") if coma else s

    return [
        (n(d.mjd - t0, 1), d.banda, n(d.mag, 2), n(d.error, 2))
        for d in sorted(dets, key=lambda x: x.mjd)
    ]


def rangos_ejes(curva: CurvaDeLuz, banda: str = "g") -> dict[str, float]:
    """Rangos redondos para el papel milimetrado que se imprime.

    Se redondea hacia afuera a números "bonitos" para que los estudiantes puedan
    marcar los ejes a mano sin pelear con decimales.

    El eje de tiempo **no** cubre toda la curva: se corta unos 45 días después
    del punto más brillante.  Muchas curvas de ZTF siguen hasta el día 180, y
    dibujar los 180 días aplasta justo la parte que hay que medir —la subida y
    los 15 días siguientes al máximo— hasta volverla ilegible.  El recorte es
    grueso a propósito: no revela dónde está el máximo.
    """
    dets = curva.por_banda(banda) or curva.detecciones
    if not dets:
        return {"t_min": 0, "t_max": 60, "mag_min": 14, "mag_max": 20}

    t0 = min(d.mjd for d in curva.detecciones)
    dia_brillante = min(dets, key=lambda d: d.mag).mjd - t0
    t_fin = min(
        max(d.mjd - t0 for d in dets),
        float(int((dia_brillante + 45) / 10 + 1) * 10),
    )

    visibles = [d for d in dets if (d.mjd - t0) <= t_fin]
    ms = [d.mag for d in visibles] or [d.mag for d in dets]
    return {
        "t_min": 0.0,
        "t_max": float(max(20, int(t_fin / 10 + 1) * 10)),
        # el eje de magnitud va al revés: arriba lo más brillante
        "mag_min": float(int(min(ms) * 2) / 2 - 0.5),
        "mag_max": float(int(max(ms) * 2 + 1) / 2 + 0.5),
    }
