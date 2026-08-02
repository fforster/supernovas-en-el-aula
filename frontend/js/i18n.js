/* Traducciones y formato de números.
 *
 * El formato importa más de lo que parece: en Chile "1.234,5" y en inglés
 * "1,234.5" son el mismo número, y mostrarlo mal confunde justo a quien recién
 * está aprendiendo a leer datos.
 */

import { urlIdioma } from './rutas.js';

const CACHE = new Map();

export class Traductor {
  constructor(idioma = 'es') {
    this.idioma = idioma;
    this.textos = {};
  }

  async cargar(idioma = this.idioma) {
    this.idioma = idioma;
    if (!CACHE.has(idioma)) {
      const r = await fetch(urlIdioma(idioma));
      if (!r.ok) throw new Error(`No se pudo cargar el idioma ${idioma}`);
      CACHE.set(idioma, await r.json());
    }
    this.textos = CACHE.get(idioma);
    document.documentElement.lang = idioma;
    return this;
  }

  /** t('clave', {n: 3}) → texto con {n} reemplazado. */
  t(clave, vars = {}) {
    let s = this.textos[clave];
    if (s === undefined) return clave; // visible a propósito: delata la falta
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
    return s;
  }

  num(x, decimales = 2) {
    if (x === null || x === undefined || !Number.isFinite(x)) return '—';
    return new Intl.NumberFormat(this.idioma === 'es' ? 'es-CL' : 'en-GB', {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    }).format(x);
  }

  entero(x) {
    return this.num(x, 0);
  }

  /** Sin separador de miles: para fechas julianas (MJD 58743,60, no 58.743,60). */
  numSinGrupos(x, decimales = 2) {
    if (x === null || x === undefined || !Number.isFinite(x)) return '—';
    return new Intl.NumberFormat(this.idioma === 'es' ? 'es-CL' : 'en-GB', {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
      useGrouping: false,
    }).format(x);
  }

  fecha(iso) {
    if (!iso) return '—';
    return new Intl.DateTimeFormat(this.idioma === 'es' ? 'es-CL' : 'en-GB', {
      year: 'numeric', month: 'long', day: 'numeric',
    }).format(new Date(iso));
  }

  /** Aplica las traducciones a todo el DOM marcado con data-i18n. */
  aplicar(raiz = document) {
    for (const el of raiz.querySelectorAll('[data-i18n]')) {
      el.textContent = this.t(el.dataset.i18n);
    }
    for (const el of raiz.querySelectorAll('[data-i18n-aria-label]')) {
      el.setAttribute('aria-label', this.t(el.dataset.i18nAriaLabel));
    }
  }
}
