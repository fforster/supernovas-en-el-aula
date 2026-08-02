/* De dónde salen los datos: servidor o sitio estático.
 *
 * La misma aplicación corre de dos maneras:
 *
 *  - Con `uvicorn`, hablando con la API de FastAPI (para desarrollar y para
 *    quien quiera montar un servidor).
 *  - Como sitio estático en GitHub Pages, donde no hay servidor y cada
 *    "respuesta" es un archivo que dejó preparado `scripts/construir_estatico.py`.
 *
 * Todo lo que cambia entre los dos modos está aquí. El resto del frontend no se
 * entera. El modo se marca con `data-estatico` en la etiqueta <html>.
 */

export const ESTATICO = document.documentElement.dataset.estatico === 'true';

/** Base para las rutas relativas.
 *
 * En GitHub Pages el sitio cuelga de /usuario.github.io/repositorio/, no de la
 * raíz, así que ninguna ruta puede empezar con "/".
 */
const BASE = new URL('.', document.baseURI).href;

const api = (cola) => (ESTATICO ? `${BASE}api/${cola}` : `/api/${cola}`);

export function urlCatalogo(idioma) {
  return ESTATICO ? api(`catalogo-${idioma}.json`) : api(`catalogo?idioma=${idioma}`);
}

export function urlObjeto(oid, modo, idioma) {
  return ESTATICO
    ? api(`objeto/${oid}-${modo}-${idioma}.json`)
    : api(`objeto/${oid}?modo=${modo}&idioma=${idioma}`);
}

export function urlAnalisis(oid, nivel) {
  return ESTATICO
    ? api(`analisis/${oid}-${nivel}.json`)
    : api(`analisis/${oid}?nivel=${nivel}`);
}

export function urlCsv(oid, idioma) {
  return ESTATICO ? api(`datos/${oid}-${idioma}.csv`) : api(`datos/${oid}.csv?idioma=${idioma}`);
}

export function urlHoja(oid, idioma, { pauta = false, papel = false } = {}) {
  if (ESTATICO) {
    const sufijo = papel ? 'papel' : pauta ? 'pauta' : 'guia';
    return api(`hoja/${oid}-${idioma}-${sufijo}.html`);
  }
  const p = new URLSearchParams({ idioma });
  if (pauta) p.set('pauta', 'true');
  if (papel) p.set('papel', 'true');
  return api(`hoja/${oid}?${p}`);
}

/** El cálculo del estudiante, a partir de SUS números.
 *
 * En el sitio estático no hay servidor que lo haga, así que se calcula acá. Son
 * las mismas cuatro líneas de `backend/cosmologia.py`, y los coeficientes salen
 * del mismo `calibracion.json`, así que no hay dos fuentes de verdad para la
 * física: sólo esta aritmética está duplicada.
 *
 * `tests/test_cosmologia.py::test_la_formula_del_estudiante_es_la_del_backend`
 * fija los valores que esta función tiene que reproducir.
 */
export function calcularLocal({ dm15, magMax, ficha, calibracion }) {
  const cal = calibracion;
  const s = cal.surveys[ficha.survey] ?? cal.surveys.ZTF;

  const dm15B = s.dm15.a + s.dm15.b * dm15;
  const M_B = cal.phillips.M_B_0 + cal.phillips.pendiente * (dm15B - cal.phillips.dm15_ref);
  const m_B = magMax + s.color.c0 - s.R_B * ficha.ebv;
  const mu = m_B - M_B;
  const d = 10 ** ((mu + 5) / 5) / 1e6; // pársecs -> megapársecs

  const z = ficha.z;
  const dHubble = (cal.c_km_s / cal.H0) * z * (1 + z / 2);

  return {
    tu_resultado: {
      dm15_B: dm15B,
      M_B,
      mu,
      distancia_mpc: d,
      distancia_anios_luz: d * 1e6 * 3.261563777,
    },
    respuesta: {
      distancia_hubble_mpc: dHubble,
      z,
      diferencia_porcentual: (100 * (d - dHubble)) / dHubble,
    },
  };
}

/** Pide el resultado al servidor, o lo calcula aquí si no hay servidor. */
export async function comprobar(oid, { dm15, magMax, ficha, calibracion }) {
  if (ESTATICO) {
    return calcularLocal({ dm15, magMax, ficha, calibracion });
  }
  const r = await fetch(
    `${api(`comprobar/${oid}`)}?dm15=${dm15.toFixed(4)}&mag_max=${magMax.toFixed(4)}`,
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/** Los archivos de traducción: bajo /static/ con servidor, al lado si no. */
export function urlIdioma(idioma) {
  return ESTATICO ? `${BASE}i18n/${idioma}.json` : `/static/i18n/${idioma}.json`;
}

export function urlEsquema(idioma) {
  return ESTATICO ? api(`esquema-${idioma}.svg`) : api(`esquema-${idioma}.svg`);
}

export function urlCalibracion() {
  return ESTATICO ? api('calibracion.json') : api('calibracion');
}
