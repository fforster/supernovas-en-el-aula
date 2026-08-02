/* Controlador de la aplicación.
 *
 * El estado vive en la URL (?objeto=…&modo=…&idioma=…) para que el docente
 * pueda pegar un enlace en el chat del curso y todos caigan en la misma
 * supernova, en la vista que corresponde.
 */

import { Traductor } from './i18n.js';
import { GraficoCurva, llenarTabla } from './grafico.js';
import { traerConCache, guardar } from './almacenamiento.js';
import * as cuaderno from './cuaderno.js';
import * as rutas from './rutas.js';

const $ = (sel) => document.querySelector(sel);

const estado = {
  modo: 'estudiante',
  idioma: 'es',
  oid: null,
  catalogo: null,
  objeto: null,
  analisis: null,
  calibracion: null,
};

let T = new Traductor('es');
let grafico = null;

/* --------------------------------------------------------------- URL */

function leerURL() {
  const p = new URLSearchParams(location.search);
  estado.modo = p.get('modo') === 'docente' ? 'docente' : 'estudiante';
  estado.idioma = p.get('idioma') === 'en' ? 'en' : 'es';
  estado.oid = p.get('objeto');
}

function escribirURL({ reemplazar = false } = {}) {
  const p = new URLSearchParams();
  if (estado.oid) p.set('objeto', estado.oid);
  if (estado.modo !== 'estudiante') p.set('modo', estado.modo);
  if (estado.idioma !== 'es') p.set('idioma', estado.idioma);
  const url = `${location.pathname}${p.toString() ? `?${p}` : ''}`;
  if (reemplazar) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
}

/* ------------------------------------------------------------ errores */

function mostrarError(mensaje) {
  $('#vista-catalogo').hidden = true;
  $('#vista-objeto').hidden = true;
  $('#vista-error').hidden = false;
  $('#error-texto').textContent = mensaje;
}

/* ----------------------------------------------------------- catálogo */

async function cargarCatalogo() {
  $('#catalogo-estado').textContent = T.t('catalogo.cargando');
  try {
    const { datos, desdeCache } = await traerConCache(
      rutas.urlCatalogo(estado.idioma),
      `catalogo:${estado.idioma}`,
    );
    estado.catalogo = datos;
    $('#aviso-offline').hidden = !desdeCache;
    $('#catalogo-estado').textContent = '';
    $('#pie-calibracion').textContent = '';
    pintarCatalogo();
  } catch (error) {
    mostrarError(T.t('error.red'));
  }
}

function pintarCatalogo() {
  const lista = $('#catalogo-lista');
  const filtro = $('#filtro-dificultad').value;
  lista.innerHTML = '';

  const objetos = estado.catalogo.objetos.filter(
    (o) => !filtro || o.dificultad === filtro,
  );

  for (const o of objetos) {
    const li = document.createElement('li');
    li.className = 'tarjeta';

    if (o.estampillas) {
      const triplete = document.createElement('ul');
      triplete.className = 'triplete triplete--compacto';
      pintarTriplete(triplete, o.estampillas, o.nombre_sn || o.oid, { compacto: true });
      li.append(triplete);
    }

    const h3 = document.createElement('h3');
    h3.textContent = o.nombre_sn || o.oid;
    li.append(h3);

    const insignia = document.createElement('p');
    const span = document.createElement('span');
    span.className = `insignia insignia--${o.dificultad}`;
    span.textContent = T.t(`dificultad.${o.dificultad}`);
    insignia.append(span);
    li.append(insignia);

    const explica = document.createElement('p');
    explica.textContent = T.t(`dificultad.explica.${o.dificultad}`);
    li.append(explica);

    const puntos = document.createElement('p');
    puntos.className = 'tenue';
    puntos.textContent = T.t('catalogo.puntos', { n: o.n_g + o.n_r });
    li.append(puntos);

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'boton';
    boton.textContent = T.t('catalogo.elegir');
    // el nombre accesible dice CUÁL supernova, no sólo "elegir"
    boton.setAttribute('aria-label', `${T.t('catalogo.elegir')}: ${o.nombre_sn || o.oid}`);
    boton.addEventListener('click', () => {
      estado.oid = o.oid;
      escribirURL();
      abrirObjeto();
    });
    li.append(boton);

    lista.append(li);
  }
}


/** Las tres imágenes de la alerta: ciencia, referencia y diferencia.
 *
 * Van siempre juntas. La de diferencia es la que hace evidente que ahí apareció
 * algo que antes no estaba, y por qué el brillo de la galaxia no arruina la
 * medición: en la resta, la galaxia ya no está.
 */
function pintarTriplete(contenedor, estampillas, nombre, { compacto = false } = {}) {
  contenedor.innerHTML = '';
  if (!estampillas) return false;

  for (const tipo of ['science', 'template', 'difference']) {
    if (!estampillas[tipo]) continue;
    const li = document.createElement('li');

    const img = document.createElement('img');
    img.src = estampillas[tipo];
    img.loading = 'lazy';
    img.className = 'estampilla';
    // El nombre accesible dice qué imagen es y de qué supernova; el pie de foto
    // repite lo mismo en pantalla, así que la alt no aporta y sería redundante
    // en la versión compacta de las tarjetas.
    img.alt = compacto
      ? ''
      : T.t('estampillas.alt', { tipo: T.t(`estampillas.${tipo}`), nombre });
    li.append(img);

    const pie = document.createElement('p');
    pie.className = 'triplete__pie';
    pie.textContent = T.t(`estampillas.${tipo}`);
    li.append(pie);

    if (!compacto) {
      const ayuda = document.createElement('p');
      ayuda.className = 'ayuda';
      ayuda.textContent = T.t(`estampillas.${tipo}_ayuda`);
      li.append(ayuda);
    }
    contenedor.append(li);
  }
  return contenedor.children.length > 0;
}

/* ------------------------------------------------------------- objeto */

async function abrirObjeto() {
  $('#vista-error').hidden = true;
  try {
    const { datos, desdeCache } = await traerConCache(
      rutas.urlObjeto(estado.oid, estado.modo, estado.idioma),
      `objeto:${estado.oid}:${estado.modo}:${estado.idioma}`,
    );
    estado.objeto = datos;
    $('#aviso-offline').hidden = !desdeCache;
  } catch (error) {
    mostrarError(T.t('error.red'));
    return;
  }

  $('#vista-catalogo').hidden = true;
  $('#vista-objeto').hidden = false;

  const o = estado.objeto;
  $('#objeto-titulo').textContent = o.nombre_sn || o.oid;
  $('#objeto-historia').textContent = o.historia || '';

  $('#bloque-estampillas').hidden = !pintarTriplete(
    $('#triplete'), o.estampillas, o.nombre_sn || o.oid,
  );

  if (o.clasificacion) {
    $('#clasif-texto').textContent = T.t('clasif.texto', {
      p: T.num(o.clasificacion.probabilidad * 100, 0),
    });
    $('#clasif-detalle').textContent = T.t('clasif.detalle', {
      nombre: o.clasificacion.clasificador,
      version: o.clasificacion.version,
    });
  }

  $('#descargar-csv').href = rutas.urlCsv(o.oid, estado.idioma);
  $('#descargar-csv').setAttribute('download', `${o.oid}.csv`);

  llenarTabla($('#tabla-curva'), o.curva);

  // La curva dibujada es SÓLO para el docente. El estudiante recibe los mismos
  // datos —tabla y CSV— pero tiene que graficarlos él: si ve la curva hecha,
  // la actividad se reduce a leer un número de la pantalla.
  if (estado.modo === 'docente') {
    grafico = new GraficoCurva(
      $('#grafico-contenedor'),
      (k, v) => T.t(k, v),
      (x, d) => T.num(x, d),
    );
    grafico.dibujar(o.curva);
  } else {
    grafico = null;
    $('#grafico-contenedor').innerHTML = '';
    limpiarMedicion();
  }

  aplicarModo();
  $('#principal').focus();
}

/** Trae el esquema explicativo y lo inserta en línea.
 *
 * En línea y no como <img>: así hereda las clases y los colores del proyecto, y
 * se ve bien igual en modo claro que en oscuro.
 */
async function pintarEsquema() {
  const caja = $('#esquema-dibujo');
  if (!caja || caja.dataset.idioma === estado.idioma) return;
  try {
    const svg = await (await fetch(rutas.urlEsquema(estado.idioma))).text();
    caja.innerHTML = svg;
    caja.dataset.idioma = estado.idioma;
  } catch {
    caja.innerHTML = '';
  }
}

/** Sección del docente: diagrama de la ley del inverso del cuadrado y tabla μ↔d.
 *
 * La tabla se calcula con la MISMA fórmula que usa el backend
 * (d = 10^((μ+5)/5) pársecs) en vez de escribirla a mano: si alguien cambia la
 * definición del módulo de distancia, la tabla lo sigue en vez de quedar
 * contradiciendo al resto de la página.
 */
async function pintarMetodo() {
  const caja = $('#metodo-ley');
  if (caja && caja.dataset.idioma !== estado.idioma) {
    try {
      caja.innerHTML = await (await fetch(rutas.urlLeyInversa(estado.idioma))).text();
      caja.dataset.idioma = estado.idioma;
    } catch {
      caja.innerHTML = '';
    }
  }

  // El rango del catálogo lo entrega el servidor ya calculado: escrito a mano
  // se desactualiza en cuanto se vuelve a curar el catálogo.
  const r = estado.catalogo?.rango_modulo;
  const nota = document.querySelector('[data-i18n="metodo.s4_p5"]');
  if (nota && r?.mu_min) {
    nota.textContent = T.t('metodo.s4_p5', {
      mu_min: T.num(r.mu_min, 1),
      mu_max: T.num(r.mu_max, 1),
      d_min: T.entero(r.d_min),
      d_max: T.entero(r.d_max),
    });
  }

  const cuerpo = $('#tabla-modulo tbody');
  if (!cuerpo || cuerpo.dataset.idioma === estado.idioma) return;
  cuerpo.innerHTML = '';
  for (const mu of [30, 33, 35, 37, 40]) {
    const mpc = 10 ** ((mu + 5) / 5) / 1e6;
    const fila = document.createElement('tr');
    const a = document.createElement('td');
    a.textContent = T.num(mu, 0);
    const b = document.createElement('td');
    b.textContent = `${mpc >= 100 ? T.entero(mpc) : T.num(mpc, 0)} Mpc`;
    fila.append(a, b);
    cuerpo.append(fila);
  }
  cuerpo.dataset.idioma = estado.idioma;
}

function aplicarModo() {
  const docente = estado.modo === 'docente';
  $('#panel-docente').hidden = !docente;
  $('#panel-estudiante').hidden = docente;
  $('#bloque-grafico').hidden = !docente;
  if (!docente) pintarEsquema();
  if (docente) { $('#cierre').hidden = true; pintarMetodo(); }
  pintarCuaderno();
  if (docente && estado.oid) cargarAnalisis();
}

/* -------------------------------------------------------- estudiante */

function limpiarMedicion() {
  $('#entrada-mag').value = '';
  $('#entrada-dm15').value = '';
  $('#error-mag').textContent = '';
  $('#error-dm15').textContent = '';
  $('#entrada-mag').removeAttribute('aria-invalid');
  $('#entrada-dm15').removeAttribute('aria-invalid');
  $('#resultado').hidden = true;
}

/** Lee un campo y devuelve el número, o null dejando el error a la vista. */
function leerCampo(idEntrada, idError, min, max, claveRango) {
  const entrada = $(idEntrada);
  const error = $(idError);
  // Se acepta la coma decimal: en Chile es lo que los niños escriben.
  const crudo = entrada.value.trim().replace(',', '.');
  let mensaje = '';

  if (crudo === '') mensaje = T.t('error.falta_valor');
  else if (!Number.isFinite(Number(crudo))) mensaje = T.t('error.falta_valor');
  else if (Number(crudo) < min || Number(crudo) > max) mensaje = T.t(claveRango);

  error.textContent = mensaje;
  if (mensaje) {
    entrada.setAttribute('aria-invalid', 'true');
    return null;
  }
  entrada.removeAttribute('aria-invalid');
  return Number(crudo);
}

async function calcularDistancia(ev) {
  ev?.preventDefault();

  const magMax = leerCampo('#entrada-mag', '#error-mag', 5, 25, 'error.rango_mag');
  const dm15 = leerCampo('#entrada-dm15', '#error-dm15', 0, 5, 'error.rango_dm15');
  if (magMax === null || dm15 === null) {
    // el foco va al primer campo con problema, para no dejar a nadie perdido
    const malo = document.querySelector('#form-medicion [aria-invalid="true"]');
    malo?.focus();
    return;
  }

  let datos;
  try {
    datos = await rutas.comprobar(estado.oid, {
      dm15, magMax, ficha: estado.objeto, calibracion: estado.calibracion,
    });
  } catch {
    mostrarError(T.t('error.red'));
    return;
  }

  const lista = $('#resultado-lista');
  lista.innerHTML = '';
  const filas = [
    [T.t('resultado.dm15'), T.num(dm15, 2)],
    [T.t('resultado.luminosidad'), T.num(datos.tu_resultado.M_B, 2)],
    [T.t('resultado.modulo'), T.num(datos.tu_resultado.mu, 2)],
    [T.t('resultado.distancia'), `${T.entero(datos.tu_resultado.distancia_mpc)} Mpc`],
    ['', T.t('resultado.anios_luz', {
      n: T.entero(datos.tu_resultado.distancia_anios_luz / 1e6),
    })],
  ];
  for (const [dt, dd] of filas) {
    const a = document.createElement('dt');
    a.textContent = dt;
    const b = document.createElement('dd');
    b.textContent = dd;
    lista.append(a, b);
  }

  const dif = Math.abs(datos.respuesta.diferencia_porcentual);
  const veredicto = dif < 10
    ? T.t('resultado.excelente')
    : dif < 25 ? T.t('resultado.bien') : T.t('resultado.revisa');
  $('#resultado-veredicto').textContent = [
    T.t('resultado.comparar', { d: T.entero(datos.respuesta.distancia_hubble_mpc) }),
    T.t('resultado.dif', { p: T.num(dif, 0) }),
    veredicto,
  ].join(' ');

  // Al cuaderno: una supernova sola no dice nada, varias sí.
  cuaderno.guardar({
    oid: estado.oid,
    nombre: estado.objeto?.nombre_sn || estado.oid,
    mag_max: magMax,
    dm15,
    d_estimada: datos.tu_resultado.distancia_mpc,
    d_real: datos.respuesta.distancia_hubble_mpc,
  });
  pintarCuaderno();

  $('#resultado').hidden = false;
  $('#resultado-titulo').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}


/** Traduce un {codigo, params, texto} del backend.
 *
 * Los textos que se muestran en pantalla no pueden nacer como frases en Python:
 * la interfaz puede estar en inglés. Viajan como código y se arman aquí. El
 * `texto` que trae el JSON (en español) es sólo el respaldo por si apareciera
 * un código sin traducir.
 */
function traducirRef(prefijo, ref) {
  if (!ref) return '—';
  if (typeof ref === 'string') return ref;          // formato antiguo
  const clave = `${prefijo}.${ref.codigo}`;
  const t = T.t(clave, ref.params || {});
  return t === clave ? (ref.texto ?? clave) : t;
}

/* ---------------------------------------------------------- cuaderno */

/** Repinta la tabla de resultados acumulados. */
function pintarCuaderno() {
  const filas = cuaderno.leer();
  const seccion = $('#cuaderno');
  // En modo docente no se muestra: el cuaderno es del estudiante.
  seccion.hidden = estado.modo !== 'estudiante' || filas.length === 0;

  const cuerpo = $('#cuaderno-tabla tbody');
  cuerpo.innerHTML = '';
  for (const f of filas) {
    const tr = document.createElement('tr');
    const dif = 100 * (f.d_estimada - f.d_real) / f.d_real;
    for (const valor of [
      f.nombre,
      T.num(f.dm15, 2),
      T.entero(f.d_estimada),
      T.entero(f.d_real),
      `${dif > 0 ? '+' : ''}${T.num(dif, 0)} %`,
    ]) {
      const td = document.createElement('td');
      td.textContent = valor;
      tr.append(td);
    }
    const td = document.createElement('td');
    const quitar = document.createElement('button');
    quitar.type = 'button';
    quitar.className = 'boton boton--texto';
    quitar.textContent = '×';
    quitar.setAttribute('aria-label', T.t('cuaderno.quitar', { nombre: f.nombre }));
    quitar.addEventListener('click', () => {
      cuaderno.borrar(f.oid);
      pintarCuaderno();
    });
    td.append(quitar);
    tr.append(td);
    cuerpo.append(tr);
  }

  const faltan = cuaderno.MINIMO_PARA_GRAFICAR - filas.length;
  $('#cuaderno-progreso').textContent = faltan > 0
    ? T.t('cuaderno.progreso', {
        n: filas.length, min: cuaderno.MINIMO_PARA_GRAFICAR, faltan,
      })
    : T.t('cuaderno.progreso_listo', { n: filas.length });
  $('#cuaderno-graficar').disabled = filas.length < cuaderno.MINIMO_PARA_GRAFICAR;
}

function descargarCuaderno() {
  const blob = new Blob([cuaderno.csv(estado.idioma)], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = estado.idioma === 'es' ? 'mis-resultados.csv' : 'my-results.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function mostrarCierre() {
  const filas = cuaderno.leer();
  if (filas.length < cuaderno.MINIMO_PARA_GRAFICAR) return;

  $('#vista-catalogo').hidden = true;
  $('#vista-objeto').hidden = true;
  $('#cierre').hidden = false;

  const papel = $('#cierre-papel');
  papel.innerHTML = '';
  papel.append(cuaderno.papelCuadriculado(filas, {
    papelAlt: T.t('cierre.papel_alt'),
    ejeX: T.t('cierre.eje_x'),
    ejeY: T.t('cierre.eje_y'),
  }));

  $('#cierre-titulo').focus?.();
  $('#cierre-titulo').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ----------------------------------------------------------- docente */

async function cargarAnalisis() {
  const nivel = $('#nivel-calculo').value;
  try {
    const r = await fetch(rutas.urlAnalisis(estado.oid, nivel));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    estado.analisis = await r.json();
  } catch {
    $('#docente-datos').innerHTML = '';
    return;
  }

  const { fotometria: f, distancia: d } = estado.analisis;
  const o = estado.objeto;
  const lista = $('#docente-datos');
  lista.innerHTML = '';

  const filas = [
    [T.t('docente.t_max'), T.numSinGrupos(f.maximo.t_max, 2)],
    [T.t('docente.mag_max'), `${T.num(f.maximo.mag_max, 3)} ± ${T.num(f.maximo.error_mag_max, 3)}`],
    [T.t('docente.color'), f.color_max === null ? '—' : T.num(f.color_max, 3)],
    [T.t('docente.dm15_g'), `${T.num(f.dm15.dm15, 3)} ± ${T.num(f.dm15.error_dm15, 3)}`],
    [T.t('docente.dm15_B'), d.dm15_B === null ? '—' : T.num(d.dm15_B, 3)],
    [T.t('docente.M_B'), T.num(d.M_B, 2)],
    [T.t('docente.mu'), `${T.num(d.mu, 2)} ± ${T.num(d.error_mu, 2)}`],
    [T.t('docente.distancia'), `${T.entero(d.distancia_mpc)} ± ${T.entero(d.error_distancia_mpc)} Mpc`],
    [T.t('docente.hubble'), `${T.entero(d.distancia_hubble_mpc)} Mpc`],
    [T.t('docente.dif'), `${T.num(d.diferencia_porcentual, 1)} %`],
    [T.t('docente.z'), T.num(o.z, 4)],
    [T.t('docente.extincion'), T.num(o.ebv, 4)],
  ];
  for (const [dt, dd] of filas) {
    const a = document.createElement('dt');
    a.textContent = dt;
    const b = document.createElement('dd');
    b.textContent = dd;
    lista.append(a, b);
  }

  const avisos = $('#docente-avisos');
  const ul = avisos.querySelector('ul');
  ul.innerHTML = '';
  for (const av of d.avisos || []) {
    const li = document.createElement('li');
    // Los avisos vienen del backend como {codigo, params, texto}: se traducen
    // aquí. El `texto` (en español) es sólo el respaldo por si apareciera un
    // código nuevo sin traducir; antes se mostraba siempre, y la interfaz en
    // inglés terminaba con las advertencias en español.
    li.textContent = traducirRef('aviso', av);
    ul.append(li);
  }
  avisos.hidden = !(d.avisos || []).length;

  $('#docente-origen').textContent = T.t('docente.origen', {
    z_fuente: traducirRef('zfuente', o.z_fuente),
  });
  $('#pie-calibracion').textContent = T.t('pie.calibracion', {
    fecha: T.fecha(estado.analisis.calibracion.generado),
  });
}

/* ------------------------------------------------------------ eventos */

function conectar() {
  for (const radio of document.querySelectorAll('input[name="modo"]')) {
    radio.addEventListener('change', () => {
      estado.modo = radio.value;
      escribirURL();
      if (estado.oid) abrirObjeto();
      else aplicarModo();
    });
  }

  $('#idioma').addEventListener('change', async (ev) => {
    estado.idioma = ev.target.value;
    escribirURL();
    await T.cargar(estado.idioma);
    T.aplicar();
    await cargarCatalogo();
    // T.aplicar() repone los textos crudos, incluido el de la sección del
    // docente que lleva marcadores ({mu_min}...). aplicarModo() vuelve a
    // rellenarlos; sin esta línea quedaban los marcadores a la vista.
    aplicarModo();
    if (estado.oid) abrirObjeto();
  });

  $('#filtro-dificultad').addEventListener('change', pintarCatalogo);

  $('#volver').addEventListener('click', () => {
    estado.oid = null;
    escribirURL();
    $('#vista-objeto').hidden = true;
    $('#vista-catalogo').hidden = false;
    $('#cierre').hidden = true;
    $('#resultado').hidden = true;
    $('#catalogo-titulo').focus?.();
  });

  $('#form-medicion').addEventListener('submit', calcularDistancia);

  $('#cuaderno-csv').addEventListener('click', descargarCuaderno);
  $('#cuaderno-graficar').addEventListener('click', mostrarCierre);
  $('#cierre-imprimir').addEventListener('click', () => window.print());
  $('#cierre-volver').addEventListener('click', () => {
    $('#cierre').hidden = true;
    $('#vista-catalogo').hidden = false;
    $('#catalogo-titulo').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // Borrar todo pide confirmación en el propio botón: un confirm() del
  // navegador bloquea la página y no se puede traducir.
  let confirmandoVaciar = false;
  $('#cuaderno-vaciar').addEventListener('click', (ev) => {
    const boton = ev.currentTarget;
    if (!confirmandoVaciar) {
      confirmandoVaciar = true;
      boton.textContent = T.t('cuaderno.vaciar_confirmar', {
        n: cuaderno.leer().length,
      });
      setTimeout(() => {
        confirmandoVaciar = false;
        boton.textContent = T.t('cuaderno.vaciar');
      }, 5000);
      return;
    }
    confirmandoVaciar = false;
    boton.textContent = T.t('cuaderno.vaciar');
    cuaderno.vaciar();
    $('#cierre').hidden = true;
    pintarCuaderno();
  });
  $('#reiniciar').addEventListener('click', () => {
    limpiarMedicion();
    $('#entrada-mag').focus();
  });

  $('#nivel-calculo').addEventListener('change', cargarAnalisis);

  // Las hojas imprimibles las arma el servidor y se abren en otra pestaña: así
  // el docente puede imprimirlas o guardarlas en PDF sin perder lo que tiene
  // en pantalla, y la pauta nunca se le muestra por accidente al curso.
  $('#imprimir-informe').addEventListener('click', () => {
    window.open(rutas.urlHoja(estado.oid, estado.idioma, { pauta: true }), '_blank');
  });
  $('#imprimir-papel').addEventListener('click', () => {
    window.open(rutas.urlHoja(estado.oid, estado.idioma, { papel: true }), '_blank');
  });
  $('#reintentar').addEventListener('click', () => location.reload());

  $('#guardar-offline').addEventListener('click', async (ev) => {
    const boton = ev.currentTarget;
    guardar(`objeto:${estado.oid}:${estado.modo}:${estado.idioma}`, estado.objeto);
    boton.textContent = T.t('offline.guardado');
    boton.disabled = true;
  });

  window.addEventListener('popstate', async () => {
    leerURL();
    sincronizarControles();
    if (estado.oid) await abrirObjeto();
    else {
      $('#vista-objeto').hidden = true;
      $('#vista-catalogo').hidden = false;
    }
  });

  window.addEventListener('online', () => { $('#aviso-offline').hidden = true; });
  window.addEventListener('offline', () => { $('#aviso-offline').hidden = false; });
}

function sincronizarControles() {
  $(`#modo-${estado.modo}`).checked = true;
  $('#idioma').value = estado.idioma;
}

/* -------------------------------------------------------------- inicio */

async function inicio() {
  leerURL();
  T = await new Traductor(estado.idioma).cargar();
  if (rutas.ESTATICO) {
    // Sin servidor, la aritmética del estudiante corre aquí y necesita los
    // coeficientes.
    try {
      estado.calibracion = await (await fetch(rutas.urlCalibracion())).json();
    } catch {
      estado.calibracion = null;
    }
  }
  T.aplicar();
  sincronizarControles();
  conectar();
  escribirURL({ reemplazar: true });

  await cargarCatalogo();
  if (estado.oid) await abrirObjeto();
  else aplicarModo();
  pintarCuaderno();

  if ('serviceWorker' in navigator) {
    // relativo: en GitHub Pages el ámbito debe ser /repositorio/, no la raíz
    navigator.serviceWorker.register('./sw.js').catch(() => {
      // sin service worker la app sigue funcionando; sólo se pierde el offline
    });
  }
}

inicio();
