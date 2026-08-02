/* Gráfico de curva de luz en SVG, accesible.
 *
 *
 * Este gráfico se muestra SÓLO en la vista de docente: el estudiante grafica los
 * datos por su cuenta, que es el punto de la actividad.
 *
 * Decisiones que importan:
 *  - El eje de magnitud va INVERTIDO (arriba = más brillante), como en
 *    astronomía. Se dice en la leyenda, no rotado en el eje, donde se cortaba.
 *  - Cada banda tiene color Y forma: círculo para g, triángulo para r. El color
 *    nunca es el único canal.
 *  - Se dibuja a mano y no con una librería para controlar el rol ARIA y el
 *    resumen que lee el lector de pantalla.
 */

const NS = 'http://www.w3.org/2000/svg';
const MARGEN = { arriba: 30, derecha: 20, abajo: 56, izquierda: 62 };
const ANCHO = 760;
const ALTO = 420;

function crear(tag, atributos = {}) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(atributos)) {
    if (v !== null && v !== undefined) el.setAttribute(k, String(v));
  }
  return el;
}

/** Marcas de eje "bonitas": 1, 2, 5, 10, 20, 50... */
function pasoLindo(rango, objetivo = 6) {
  const crudo = rango / objetivo;
  const magnitud = 10 ** Math.floor(Math.log10(crudo));
  const norm = crudo / magnitud;
  const paso = norm <= 1.5 ? 1 : norm <= 3 ? 2 : norm <= 7 ? 5 : 10;
  return paso * magnitud;
}

export class GraficoCurva {
  /**
   * @param {HTMLElement} contenedor
   * @param {(clave:string, vars?:object)=>string} t  función de traducción
   */
  constructor(contenedor, t, num = (x, d) => x.toFixed(d)) {
    this.contenedor = contenedor;
    this.t = t;
    // Formateador de números segun el idioma: el lector de pantalla debe leer
    // "15,08" en español y "15.08" en inglés, igual que lo que se ve escrito.
    this.num = num;
    this.datos = null;
  }

  /** @param {{detecciones:Array}} curva */
  dibujar(curva) {
    this.contenedor.innerHTML = '';
    const dets = (curva?.detecciones ?? []).filter((d) => Number.isFinite(d.mag));
    if (!dets.length) {
      const p = document.createElement('p');
      p.textContent = this.t('grafico.sin_datos');
      this.contenedor.append(p);
      return;
    }

    const t0 = Math.min(...dets.map((d) => d.mjd));
    const puntos = dets.map((d) => ({ ...d, dia: d.mjd - t0 }));
    this.t0 = t0;
    this.puntos = puntos;

    const dias = puntos.map((p) => p.dia);
    const mags = puntos.map((p) => p.mag);
    const errs = puntos.map((p) => p.error || 0);

    const xMin = 0;
    const xMax = Math.max(...dias) * 1.02 + 1;
    // el eje Y se invierte más abajo; aquí sólo fijamos los límites con holgura
    const yMin = Math.min(...mags.map((m, i) => m - errs[i])) - 0.3;
    const yMax = Math.max(...mags.map((m, i) => m + errs[i])) + 0.3;

    const anchoUtil = ANCHO - MARGEN.izquierda - MARGEN.derecha;
    const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo;

    const ex = (dia) => MARGEN.izquierda + ((dia - xMin) / (xMax - xMin)) * anchoUtil;
    // ¡invertido! magnitud chica (brillante) arriba
    const ey = (mag) => MARGEN.arriba + ((mag - yMin) / (yMax - yMin)) * altoUtil;
    this.ex = ex;
    this.ey = ey;
    this.xMax = xMax;
    this.limites = { xMin, xMax, yMin, yMax };

    const svg = crear('svg', {
      viewBox: `0 0 ${ANCHO} ${ALTO}`,
      role: 'img',
      'aria-label': this.t('grafico.resumen', {
        oid: curva.oid,
        n: puntos.length,
        dias: Math.round(xMax),
        max: this.num(Math.min(...mags), 1),
      }),
    });

    this.#ejes(svg, ex, ey, xMin, xMax, yMin, yMax, anchoUtil, altoUtil);
    this.#puntos(svg, puntos, ex, ey);

    this.contenedor.append(svg);
    this.svg = svg;
  }

  #ejes(svg, ex, ey, xMin, xMax, yMin, yMax, anchoUtil, altoUtil) {
    const g = crear('g');

    const pasoX = pasoLindo(xMax - xMin);
    for (let v = 0; v <= xMax; v += pasoX) {
      const x = ex(v);
      g.append(crear('line', {
        class: 'rejilla', x1: x, x2: x,
        y1: MARGEN.arriba, y2: MARGEN.arriba + altoUtil,
      }));
      const txt = crear('text', {
        class: 'eje-texto', x, y: MARGEN.arriba + altoUtil + 20, 'text-anchor': 'middle',
      });
      txt.textContent = String(Math.round(v));
      g.append(txt);
    }

    const pasoY = pasoLindo(yMax - yMin, 5);
    for (let v = Math.ceil(yMin / pasoY) * pasoY; v <= yMax; v += pasoY) {
      const y = ey(v);
      g.append(crear('line', {
        class: 'rejilla', x1: MARGEN.izquierda, x2: MARGEN.izquierda + anchoUtil, y1: y, y2: y,
      }));
      const txt = crear('text', {
        class: 'eje-texto', x: MARGEN.izquierda - 10, y: y + 4, 'text-anchor': 'end',
      });
      txt.textContent = v.toFixed(1);
      g.append(txt);
    }

    g.append(crear('line', {
      class: 'eje', x1: MARGEN.izquierda, x2: MARGEN.izquierda + anchoUtil,
      y1: MARGEN.arriba + altoUtil, y2: MARGEN.arriba + altoUtil,
    }));
    g.append(crear('line', {
      class: 'eje', x1: MARGEN.izquierda, x2: MARGEN.izquierda,
      y1: MARGEN.arriba, y2: MARGEN.arriba + altoUtil,
    }));

    const tx = crear('text', {
      class: 'eje-titulo', x: MARGEN.izquierda + anchoUtil / 2,
      y: ALTO - 12, 'text-anchor': 'middle',
    });
    tx.textContent = this.t('grafico.eje_x');
    g.append(tx);

    const ty = crear('text', {
      class: 'eje-titulo', x: 16, y: MARGEN.arriba + altoUtil / 2,
      'text-anchor': 'middle', transform: `rotate(-90 16 ${MARGEN.arriba + altoUtil / 2})`,
    });
    ty.textContent = this.t('grafico.eje_y');
    g.append(ty);

    // El recordatorio de que el eje va al revés ("↑ más brillante") vive en la
    // leyenda HTML, no aquí dentro: dibujado en el SVG chocaba con la etiqueta
    // de los marcadores cuando éstos quedaban cerca del borde izquierdo.

    svg.append(g);
  }

  #puntos(svg, puntos, ex, ey) {
    const g = crear('g');
    for (const p of puntos) {
      const x = ex(p.dia);
      const y = ey(p.mag);
      const clase = p.banda === 'g' ? 'punto--g' : 'punto--r';

      if (p.error) {
        g.append(crear('line', {
          class: `barra-error ${clase}`, x1: x, x2: x,
          y1: ey(p.mag - p.error), y2: ey(p.mag + p.error),
        }));
      }
      // forma distinta por banda: el color no puede ser el único indicio
      if (p.banda === 'g') {
        g.append(crear('circle', { class: clase, cx: x, cy: y, r: 4 }));
      } else {
        g.append(crear('polygon', {
          class: clase,
          points: `${x},${y - 4.6} ${x + 4.4},${y + 3.4} ${x - 4.4},${y + 3.4}`,
        }));
      }
    }
    svg.append(g);
  }

}

/** Rellena la tabla que refleja el gráfico para lectores de pantalla. */
export function llenarTabla(tabla, curva) {
  const cuerpo = tabla.querySelector('tbody');
  cuerpo.innerHTML = '';
  const dets = curva?.detecciones ?? [];
  if (!dets.length) return;
  const t0 = Math.min(...dets.map((d) => d.mjd));
  for (const d of [...dets].sort((a, b) => a.mjd - b.mjd)) {
    const fila = document.createElement('tr');
    for (const valor of [
      (d.mjd - t0).toFixed(2), d.banda, d.mag.toFixed(3), d.error.toFixed(3),
    ]) {
      const celda = document.createElement('td');
      celda.textContent = valor;
      fila.append(celda);
    }
    cuerpo.append(fila);
  }
}
