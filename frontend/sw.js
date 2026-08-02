/* Service worker: que la actividad sobreviva a una caída de internet.
 *
 * Estrategia:
 *  - El "casco" de la aplicación (HTML, CSS, JS, traducciones) se guarda al
 *    instalar y se sirve desde la caché primero: arranca rápido y sin red.
 *  - Las respuestas de /api/ se guardan a medida que se piden (red primero,
 *    caché como respaldo), porque queremos datos frescos cuando hay conexión.
 */

const VERSION = 'snia-v1';
const CASCO = [
  '/',
  '/static/css/estilos.css',
  '/static/js/app.js',
  '/static/js/grafico.js',
  '/static/js/i18n.js',
  '/static/js/almacenamiento.js',
  '/static/js/rutas.js',
  '/static/js/cuaderno.js',
  '/static/i18n/es.json',
  '/static/i18n/en.json',
];

self.addEventListener('install', (ev) => {
  ev.waitUntil(
    caches.open(VERSION)
      // addAll falla entero si un solo archivo falla; los pedimos de a uno
      .then((c) => Promise.allSettled(CASCO.map((u) => c.add(u))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(
        claves.filter((k) => k !== VERSION).map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (ev) => {
  const { request } = ev;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // recursos de otros sitios

  // Navegaciones: red primero, y si no hay red, el casco guardado.
  //
  // Va con ignoreSearch porque TODAS las direcciones que se comparten llevan
  // query ("?objeto=ZTF25aaxjntk"), y caches.match() no calza una entrada
  // guardada como "/" con una petición a "/?objeto=X". Sin esto, sin conexión
  // fallaban justo los enlaces que el docente le pasa al curso.
  if (request.mode === 'navigate') {
    ev.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(VERSION);
        return (
          (await cache.match(request, { ignoreSearch: true })) ||
          (await cache.match('./', { ignoreSearch: true })) ||
          (await cache.match('/', { ignoreSearch: true })) ||
          Response.error()
        );
      }),
    );
    return;
  }

  // Las estampillas ya procesadas son inmutables —un candid es una observación
  // concreta— y pesan. Caché primero: en una escuela con mala conexión, la
  // segunda visita no vuelve a bajarlas.
  // includes y no startsWith: en GitHub Pages el sitio cuelga de
  // /repositorio/, así que la ruta es /repositorio/api/... y un startsWith('/api/')
  // no calzaría nunca.
  if (url.pathname.includes('/api/estampilla/')) {
    ev.respondWith(
      caches.match(request).then((guardado) => guardado || fetch(request).then((r) => {
        const copia = r.clone();
        if (r.ok) caches.open(VERSION).then((c) => c.put(request, copia));
        return r;
      })),
    );
    return;
  }

  if (url.pathname.includes('/api/')) {
    ev.respondWith(
      fetch(request)
        .then((r) => {
          const copia = r.clone();
          caches.open(VERSION).then((c) => c.put(request, copia));
          return r;
        })
        .catch(() => caches.match(request)),
    );
    return;
  }

  ev.respondWith(
    caches.match(request).then((guardado) => guardado || fetch(request)),
  );
});
