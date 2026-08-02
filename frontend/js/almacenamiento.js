/* Caché en el navegador, para escuelas con mala conexión.
 *
 * Muchas salas de clase tienen internet inestable o compartido. Una vez que el
 * docente abre una supernova, sus datos quedan guardados y la actividad se puede
 * hacer completa sin conexión.
 */

const PREFIJO = 'snia:';
const DIAS_VALIDEZ = 30;

function clave(nombre) {
  return PREFIJO + nombre;
}

export function guardar(nombre, valor) {
  try {
    localStorage.setItem(
      clave(nombre),
      JSON.stringify({ guardado: Date.now(), valor }),
    );
    return true;
  } catch {
    // Cuota llena o modo privado: no es un error fatal, sólo perdemos la caché.
    return false;
  }
}

export function leer(nombre) {
  try {
    const crudo = localStorage.getItem(clave(nombre));
    if (!crudo) return null;
    const { guardado, valor } = JSON.parse(crudo);
    if (Date.now() - guardado > DIAS_VALIDEZ * 864e5) {
      localStorage.removeItem(clave(nombre));
      return null;
    }
    return valor;
  } catch {
    return null;
  }
}

/** Trae de la red y guarda; si la red falla, usa lo guardado. */
export async function traerConCache(url, nombre) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const datos = await r.json();
    guardar(nombre, datos);
    return { datos, desdeCache: false };
  } catch (error) {
    const guardadoPrevio = leer(nombre);
    if (guardadoPrevio) return { datos: guardadoPrevio, desdeCache: true };
    throw error;
  }
}

export function estaEnCache(nombre) {
  return leer(nombre) !== null;
}
