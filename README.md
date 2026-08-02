# Supernovas en el aula · Supernovae in the classroom

Actividad escolar para medir **la distancia a una supernova de tipo Ia** con datos
reales del broker [ALeRCE](https://alerce.online) y el survey ZTF. Pensada para
estudiantes de 10 a 15 años, en español, con una vista para el docente y otra para
el curso. Preparada para migrar al Observatorio Rubin.

> *A classroom activity to measure the distance to a Type Ia supernova using real
> ALeRCE/ZTF data. Spanish first, English toggle included.*

---

## Para docentes: cómo se usa

1. Abre la página y elige una supernova. Las marcadas **Fácil** tienen muchas
   mediciones y un máximo muy claro: parte por ésas. Todas las del catálogo
   tienen cobertura densa alrededor del máximo, sin huecos grandes: si al
   graficar quedara un vacío de dos semanas justo donde hay que leer Δm15, la
   actividad no se podría hacer.
2. Cambia a **Docente** para ver el análisis automático (máximo, Δm15, distancia)
   y compararlo con la ley de Hubble.
3. Aprieta **Imprimir guía y pauta**: sale la hoja del estudiante y, aparte, la
   pauta de corrección.
4. **Descargar los datos (CSV)** para que el curso grafique en Excel o en
   Google Sheets, o **Imprimir papel milimetrado** para hacerlo a mano con los
   ejes ya puestos.
5. Pídeles que midan **varias** supernovas: la gracia del cierre es comparar la
   distancia estimada con la real para todas juntas. Con una sola no hay nada
   que discutir; con cinco o seis se ve si el método tiene sesgo, cuánta
   dispersión tiene y qué supernovas salieron peor y por qué.
6. Comparte el enlace de la barra de direcciones: lleva la supernova elegida.
   Agrega `&modo=estudiante` para asegurarte de que no vean las respuestas.

Cada resultado queda anotado en **«Mis resultados»**, una tabla arriba de la
página con el nombre de la supernova, el Δm15 medido, la distancia que calculó
el estudiante y la distancia real. Con cuatro o más aparece el botón **Graficar
mis resultados**, que entrega papel cuadriculado con los dos ejes a la misma
escala —distancia real contra distancia estimada— y preguntas para discutir. Si
el método funciona, los puntos caen sobre la diagonal; esa diagonal **no** viene
dibujada, es lo que tienen que descubrir. La tabla vive sólo en el navegador
(`localStorage`): las respuestas de los estudiantes nunca salen de su computador.

La vista de estudiante **no muestra la curva de luz dibujada**: ésa es la parte
que les toca hacer a ellos. Reciben la tabla de mediciones y el CSV, grafican, y
después escriben en dos casillas la magnitud del máximo y el Δm15 que midieron.
La distancia sale de *sus* números.

Tampoco reciben nunca el corrimiento al rojo ni la distancia: el servidor los
quita antes de mandar los datos, así que no basta con mirar el código de la
página.

### Qué ve el curso

De cada supernova se muestran **siempre las tres imágenes de la alerta**: lo que
vio el telescopio esa noche, cómo era esa zona del cielo antes, y la resta de
ambas. La tercera es la que explica sola por qué el brillo de la galaxia no
estropea la medición: en la resta la galaxia desaparece y queda sólo lo que
apareció.

La ficha también cuenta **qué había vivo en la Tierra** cuando esa luz salió.
"Hace 380 millones de años" no se imagina; "cuando los primeros peces empezaban
a salir del agua" sí. Los períodos y sus fechas están en `backend/eras.py`,
según la escala de la Comisión Internacional de Estratigrafía.

### Para el docente: de dónde sale la distancia

El panel de docente incluye una sección con la física completa, pensada para
leerse antes de entrar a la sala: la ley del inverso del cuadrado (con dibujo),
por qué los astrónomos miden en magnitudes, la diferencia entre magnitud
aparente y absoluta, y la derivación del **módulo de distancia**

    μ ≡ m − M = 5·log₁₀(d / 10 pc)

con el punto que suele quedar implícito: al restar m y M la luminosidad
intrínseca se cancela, así que μ depende **sólo** de la distancia. Medir el
módulo de distancia y medir la distancia son la misma operación en distintas
unidades, no un paso intermedio. De ahí sigue por qué hace falta una vela
estándar (M no se puede medir), por qué las SN Ia lo son, qué añade la relación
de Phillips y cómo esto conecta con el diagrama de Hubble y el Nobel de 2011.

### La ciencia, en corto

Las supernovas de tipo Ia explotan siempre de forma parecida, así que sirven como
*velas estándar*. La relación de Phillips afina la idea: las que se apagan más
lento son más luminosas, y **Δm15** —cuánto se apagan en los 15 días siguientes
al máximo— mide esa rapidez. Con la luminosidad real y el brillo observado sale
el módulo de distancia `μ = m − M`, y de ahí `d = 10^((μ+5)/5)` pársecs.

Los estudiantes hacen la versión de una sola ecuación (`M = −19,3`); el panel del
docente muestra además la corrección por Δm15, el color y la extinción galáctica.

---

## Instalación

```bash
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Abre <http://127.0.0.1:8000>. El repositorio ya trae el catálogo y la calibración
generados, así que funciona sin más pasos.

## Pruebas

```bash
pytest                # rápidas, sin internet
pytest --red          # incluye las que consultan ALeRCE de verdad
```

Las pruebas con `--red` verifican, entre otras cosas, que el máximo y el Δm15 de
SN 2021hpr y SN 2019np sigan coincidiendo con los valores publicados, y que cada
objeto del catálogo siga clasificado como SNIa en ALeRCE.

## Regenerar los datos

```bash
python3 scripts/calibrar_dm15.py --n 1500 --figura   # -> data/calibracion.json
python3 scripts/curar_catalogo.py --objetivo 30      # -> data/catalogo_snia.json
```

El primero es lento (simula SN Ia con SALT2); el segundo también, porque consulta
NED e IRSA objeto por objeto. Ambos guardan en `cache/` y se pueden reanudar.

---

## Publicarlo (GitHub Pages)

La forma más simple, y gratis: **no hace falta servidor**. El catálogo son 30
objetos fijos, así que todo lo que normalmente calcula FastAPI se puede resolver
una vez y guardar como archivos.

```bash
python3 scripts/construir_estatico.py     # deja todo en sitio/  (~5 MB)
python3 -m http.server -d sitio 8000      # para probarlo antes de publicar
```

Para dejarlo en línea:

1. Sube el repositorio a GitHub.
2. **Settings → Pages → Source: GitHub Actions**.
3. Listo. `.github/workflows/publicar.yml` corre las pruebas, construye el sitio
   y lo publica en cada `push` a `main`, más una vez al mes para refrescar las
   curvas de luz. Queda en `https://<usuario>.github.io/<repositorio>/`.

Lo que se publica es una carpeta de archivos: sirve igual en GitHub Pages, en un
pendrive o en el disco de una sala de computación **sin internet**. Sólo hay que
abrirlo desde un servidor web (`python3 -m http.server`), no con doble clic:
los módulos de JavaScript no funcionan con `file://`.

### Qué se pierde sin servidor

Una cosa, y conviene decidirla a conciencia: **en un sitio estático la respuesta
no se puede esconder**. El navegador necesita el corrimiento al rojo y la
extinción para hacer la cuenta del estudiante, así que quedan dentro de los
JSON. La interfaz sigue sin mostrarlos, pero quien abra las herramientas de
desarrollo los encuentra. Para una actividad de aula eso suele dar lo mismo; si
no da lo mismo, hay que desplegar el backend (`uvicorn backend.app:app`), que sí
los quita antes de enviar nada — a cambio de tener que mantener un servidor.

Todo lo demás funciona igual, incluida la actividad completa sin conexión.

### Cómo se evita tener la física en dos idiomas

El sitio estático se construye ejecutando **el mismo código Python** del
servidor, así que las curvas, los ajustes, las distancias, las imágenes y las
hojas imprimibles salen de una sola implementación. Lo único que el navegador
calcula por su cuenta son las cuatro líneas de aritmética del estudiante, en
`frontend/js/rutas.js`; `tests/test_cosmologia.py` ejecuta ese JavaScript con
node y lo compara contra el backend, así que no pueden separarse en silencio.

---

## Cómo está armado

```
backend/
  brokers/        base.py define la interfaz; alerce_ztf.py la implementa;
                  rubin.py es el hueco por donde entra LSST
  fotometria.py   máximo, Δm15 y sus incertidumbres (bootstrap)
  cosmologia.py   Phillips, extinción, módulo de distancia, ley de Hubble
  calibracion.py  lee data/calibracion.json — no hay números mágicos sueltos
  eras.py         qué vivía en la Tierra según la edad de la luz
  informe.py      CSV, papel milimetrado, hoja imprimible
  app.py          rutas JSON + archivos estáticos
frontend/         HTML/CSS/JS sin build ni dependencias
  js/cuaderno.js  los resultados acumulados del estudiante (sólo en su navegador)
scripts/          generadores de data/
```

Todo el cálculo científico vive en Python. El navegador sólo dibuja: así el
número que aparece en pantalla, el del CSV y el de la hoja impresa son el mismo.

### Camino a Rubin

`backend/brokers/base.py` es la costura. La aplicación trabaja con **nombres de
banda** (`'g'`, `'r'`) y no con los `fid` numéricos de ZTF, y los coeficientes de
cada survey están en `data/calibracion.json` bajo su propia llave. Para sumar
Rubin hay que completar `brokers/rubin.py`, ampliar las bandas a `ugrizy` y
correr `scripts/calibrar_dm15.py --survey LSST` (el script ya acepta las bandas
`lsstg`/`lsstr` de sncosmo).

---

## Notas sobre los datos, aprendidas a los golpes

Cosas que no son obvias y que costaron tiempo; están anotadas aquí para que no
haya que redescubrirlas.

- **El parámetro de clase de la API de ALeRCE se llama `class`, no `class_name`.**
  La API **descarta en silencio** los parámetros que no conoce, así que usar el
  nombre equivocado no da error: devuelve objetos de cualquier clase y parece que
  el filtro estuviera roto. Con `class` la pureza es del 100 %. `ndet`,
  `firstmjd` y `lastmjd` son rangos y se pasan como dos valores.
- **`drb` se ignora.** Es el real-bogus de deep learning que calcula **ZTF** y
  viaja en el paquete de alerta —ALeRCE sólo lo transmite—, y vale 0,0 en las
  fuentes muy brillantes: en SN 2019np (g ≈ 13,4) filtrar por `drb > 0.5`
  eliminaba las seis detecciones del pico. Como falla justo en las supernovas más
  brillantes, no sirve para este uso. Queda `rb`, y del resto se encarga el
  recorte sigma del ajuste.
- **El catálogo sólo tiene supernovas de 2024 en adelante.** BHRF se entrenó con
  fotometría forzada, que ZTF produce desde entonces; usarlo sobre alertas
  anteriores es sacarlo de su dominio. Por eso tampoco hay clasificador de
  respaldo: si BHRF no opinó, el objeto no entra.
- **No hay endpoint público de fotometría forzada** (404). La clasificación viene
  de BHRF (entrenado con ella); la fotometría que se grafica y se descarga es la
  de alertas.
- **El catálogo exige cobertura densa cerca del máximo**: sin huecos mayores a
  5 días entre −8 y +20 días del máximo, y con una medición real a menos de
  3 días del instante en que se lee Δm15. Un ajuste puede rellenar un hueco;
  un estudiante con lápiz y papel, no.
- **El catálogo evita las supernovas demasiado cercanas** (z < 0,015). No es
  esnobismo: a z = 0,0045 una velocidad peculiar normal de 300 km/s mueve la
  distancia de Hubble en ±22 %, y la actividad parecería fallar cuando en
  realidad falla la referencia. También evita las más brillantes que g = 14,
  donde ZTF satura.
- **Las estampillas se ven negras sin realzar.** El PNG que sirve ALeRCE trae un
  estiramiento lineal y el pixel mediano queda en 30/255. Se baja el **FITS** y
  se reescala en el servidor con `astropy.visualization`
  (`ImageNormalize` + `ManualInterval` + `AsinhStretch`), midiendo el brillo en
  la **zona central** para que la supernova siempre quede visible. Ver
  `backend/imagenes.py`. Los tipos válidos en `avro.alerce.online/get_stamp` son
  `science`, `template` y `difference` (`reference` da error 400).
- **La estampilla tiene que ser la del máximo, no la del descubrimiento.** En la
  alerta de descubrimiento la supernova está en el límite de detección: en
  ZTF25ackdapv la primera es de magnitud 19,7 y la del máximo de 15,3, sesenta
  veces más brillante.
- **En la imagen de referencia el centro está vacío** (la supernova aún no
  existía), así que el techo de la escala no puede salir del centro: si sale, la
  galaxia de al lado satura y la referencia se ve como una mancha blanca. Se
  detecta comparando con el ruido —el centro de la referencia de ZTF25ackdapv
  está a 2,9 sigma del cielo, contra 150-280 sigma en el resto— y en ese caso el
  techo se mide sobre el recorte completo.
- **ALeRCE puede tener dos `oid` para la misma supernova.** SN 2025oxy salió
  como `ZTF25aaxjntk` y como `ZTF25aaxnchn`. El curador descarta duplicados por
  nombre IAU y por posición (5″).

## Precisión que hay que esperar

Sobre supernovas sintéticas de SALT2, donde la respuesta se conoce exactamente,
la cadena completa recupera la distancia con un sesgo de −3 % y una dispersión
del 4 % usando la corrección de Δm15 (5,5 % con la vela estándar pura, que es lo
que hacen los estudiantes). Sobre las 30 supernovas reales del catálogo, la
mediana de la diferencia contra la ley de Hubble es **≈12 %**, y ahí ya entran
las velocidades peculiares de las galaxias.

Que no dé exacto es parte de la clase, no un defecto que esconder.

## Créditos

Datos del broker [ALeRCE](https://alerce.online) y del survey
[ZTF](https://www.ztf.caltech.edu/). Corrimientos al rojo de
[NED](https://ned.ipac.caltech.edu/) y extinción galáctica del servicio
[DUST de IRSA](https://irsa.ipac.caltech.edu/applications/DUST/)
(Schlafly & Finkbeiner 2011). Modelo SALT2 vía
[sncosmo](https://sncosmo.readthedocs.io/).
