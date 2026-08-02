/* El cuaderno del estudiante: sus resultados, acumulados.
 *
 * Cada supernova medida deja una fila. Con una sola supernova el resultado es
 * anecdótico; con seis o siete se puede graficar la distancia estimada contra
 * la real y discutir si el método funciona, dónde falla y por qué. Ése es el
 * salto de "hice un cálculo" a "hice ciencia".
 *
 * Todo vive en el navegador (localStorage). Las respuestas del estudiante nunca
 * salen de su computador: no hay cuentas, no hay servidor que las guarde, y la
 * escuela no tiene que preocuparse de datos de menores.
 */

const CLAVE = 'snia:cuaderno';

/** Cuántas filas hacen falta para que valga la pena graficar. */
export const MINIMO_PARA_GRAFICAR = 4;

export function leer() {
  try {
    const crudo = localStorage.getItem(CLAVE);
    const filas = crudo ? JSON.parse(crudo) : [];
    return Array.isArray(filas) ? filas : [];
  } catch {
    return [];
  }
}

function escribir(filas) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(filas));
    return true;
  } catch {
    return false; // modo privado o cuota llena: se pierde, no es fatal
  }
}

/** Guarda (o reemplaza) el resultado de una supernova.
 *
 * Se reemplaza por ``oid`` a propósito: si el estudiante repite la medición
 * porque le quedó mal, queremos su mejor intento, no las dos filas.
 */
export function guardar(entrada) {
  const filas = leer().filter((f) => f.oid !== entrada.oid);
  filas.push({ ...entrada, cuando: new Date().toISOString() });
  filas.sort((a, b) => a.d_real - b.d_real);
  escribir(filas);
  return filas;
}

export function borrar(oid) {
  const filas = leer().filter((f) => f.oid !== oid);
  escribir(filas);
  return filas;
}

export function vaciar() {
  escribir([]);
  return [];
}

/** CSV para abrir en la planilla y graficar ahí. */
export function csv(idioma = 'es') {
  const filas = leer();
  const coma = idioma === 'es';
  const sep = coma ? ';' : ',';
  const n = (x, d = 1) => {
    const s = Number(x).toFixed(d);
    return coma ? s.replace('.', ',') : s;
  };
  const cab = coma
    ? ['supernova', 'magnitud_maxima', 'dm15', 'distancia_estimada_Mpc', 'distancia_real_Mpc']
    : ['supernova', 'peak_magnitude', 'dm15', 'estimated_distance_Mpc', 'true_distance_Mpc'];

  return [
    cab.join(sep),
    ...filas.map((f) => [
      f.nombre, n(f.mag_max, 2), n(f.dm15, 2), n(f.d_estimada, 1), n(f.d_real, 1),
    ].join(sep)),
  ].join('\n') + '\n';
}

/** Papel cuadriculado con los dos ejes a la MISMA escala.
 *
 * Que sea cuadrado y con el mismo rango en los dos ejes es la clave del
 * ejercicio: así, si el método funciona, los puntos caen sobre la diagonal.
 * La diagonal no se dibuja —eso es lo que tienen que descubrir ellos.
 */
export function papelCuadriculado(filas, textos) {
  const NS = 'http://www.w3.org/2000/svg';
  const A = 520;
  const M = { i: 62, d: 16, a: 16, b: 52 };
  const util = A - M.i - M.d;

  const maximo = Math.max(
    10,
    ...filas.flatMap((f) => [f.d_estimada, f.d_real].filter(Number.isFinite)),
  );
  // se redondea hacia arriba a un número cómodo de subdividir
  const paso = Math.max(10, Math.ceil(maximo / 6 / 10) * 10);
  const tope = Math.ceil(maximo / paso) * paso + paso;

  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${A} ${A}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', textos.papelAlt);

  const el = (tag, attrs, texto) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (texto !== undefined) e.textContent = texto;
    svg.append(e);
    return e;
  };

  const ex = (v) => M.i + (v / tope) * util;
  const ey = (v) => M.a + util - (v / tope) * util;

  for (let v = 0; v <= tope + 1e-9; v += paso / 5) {
    const fuerte = Math.abs(v % paso) < 1e-9;
    const clase = fuerte ? 'papel-linea--fuerte' : 'papel-linea';
    el('line', { class: clase, x1: ex(v), y1: M.a, x2: ex(v), y2: M.a + util });
    el('line', { class: clase, x1: M.i, y1: ey(v), x2: M.i + util, y2: ey(v) });
    if (fuerte) {
      el('text', {
        class: 'papel-texto', x: ex(v), y: M.a + util + 16, 'text-anchor': 'middle',
      }, String(Math.round(v)));
      el('text', {
        class: 'papel-texto', x: M.i - 6, y: ey(v) + 4, 'text-anchor': 'end',
      }, String(Math.round(v)));
    }
  }

  el('text', {
    class: 'papel-texto', x: M.i + util / 2, y: A - 12,
    'text-anchor': 'middle', style: 'font-size:12px',
  }, textos.ejeX);
  el('text', {
    class: 'papel-texto', x: 14, y: M.a + util / 2, 'text-anchor': 'middle',
    style: 'font-size:12px', transform: `rotate(-90 14 ${M.a + util / 2})`,
  }, textos.ejeY);

  return svg;
}
