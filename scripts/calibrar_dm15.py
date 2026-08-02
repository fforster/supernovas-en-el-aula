#!/usr/bin/env python3
"""Calibra la conversión de banda / calibrate the band conversion.

Produce ``data/calibracion.json``, que contiene los dos únicos ajustes que la
aplicación necesita para pasar de lo que se mide en ZTF a lo que pide la
relación de Phillips:

1. ``Δm15(B) = a + b · Δm15(g)`` — Phillips está definida en la banda B, pero
   ZTF observa en g.  Es una relación de **forma** de la curva de luz, así que
   no depende del brillo de la supernova.
2. ``m_B = m_g + c0 + c1·(g−r) + c2·z`` — corrección de color y corrección K.
   El término en z es la corrección K: a mayor corrimiento al rojo, el filtro g
   observado mira una parte distinta del espectro en reposo.

Método
------
Se simulan supernovas con SALT2 (el modelo estándar de SN Ia), con cadencia y
ruido parecidos a los de ZTF, y **se miden con el mismo código que usa la app**
(``backend.fotometria``).  Así el ajuste absorbe los sesgos de nuestro propio
estimador y no los de un estimador ideal.

La verdad de referencia sale del modelo sin ruido:

* ``Δm15(B)`` se evalúa directamente sobre el modelo en reposo (SALT2 define
  ``t0`` como el máximo en B, así que Δm15(B) = m_B(15 d) − m_B(0)).
* ``m_B`` verdadera es ``μ(z) + M_B``, con μ y M_B impuestos al simular.

Uso
---
    python3 scripts/calibrar_dm15.py                # ZTF, ~900 simulaciones
    python3 scripts/calibrar_dm15.py --n 2000 --figura
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import warnings
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend import fotometria as F  # noqa: E402
from backend.brokers.base import CurvaDeLuz, Deteccion  # noqa: E402

warnings.filterwarnings("ignore")

# --------------------------------------------------------------- configuración

#: Bandas de sncosmo por survey.  Para Rubin bastará con añadir una entrada.
SURVEYS = {
    "ZTF": {
        "banda": "g",
        "banda_color": "r",
        "banda_sncosmo": "ztfg",
        "banda_color_sncosmo": "ztfr",
        "limite_mag": 20.5,
        "cadencia_dias": 3.0,
        "R_B": 4.1,  # A_B/E(B−V), ley de Fitzpatrick R_V=3.1
    },
    "LSST": {
        "banda": "g",
        "banda_color": "r",
        "banda_sncosmo": "lsstg",
        "banda_color_sncosmo": "lsstr",
        "limite_mag": 24.0,
        "cadencia_dias": 4.0,
        "R_B": 4.1,
    },
}

#: Relación de Phillips que usa la app.  No se ajusta aquí: es la convención
#: pedagógica elegida, y queda en el JSON para poder cambiarla en un solo lugar.
PHILLIPS = {
    "M_B_0": -19.3,
    "pendiente": 0.6,
    "dm15_ref": 1.1,
    "dispersion": 0.15,
    "fuente": (
        "Phillips et al. (1999), forma simplificada M_B = -19.3 + 0.6·(Δm15(B) - 1.1), "
        "para H0 = 70 km/s/Mpc"
    ),
}

H0 = 70.0
C_KM_S = 299792.458


def cosmologia_sncosmo():
    from astropy.cosmology import FlatLambdaCDM

    return FlatLambdaCDM(H0=H0, Om0=0.3)


def ruido_ztf(mag: np.ndarray, limite: float) -> np.ndarray:
    """Error fotométrico aproximado en función de la magnitud.

    Ajustado a ojo sobre las curvas reales de ALeRCE: ~0,02 mag en las fuentes
    brillantes y ~0,25 mag cerca del límite de detección.
    """
    return np.clip(0.015 + 0.25 * 10 ** (0.4 * (mag - limite)), 0.015, 0.4)


def simular_una(
    modelo, modelo_reposo, cfg: dict, z: float, x1: float, c: float, rng
) -> dict | None:
    """Simula una SN, la mide con el código de la app y devuelve el par verdad/medida."""
    cosmo = cosmologia_sncosmo()

    # --- verdad de referencia, sin ruido -------------------------------------
    # Primero la forma de la curva en B, que fija Δm15(B) y por lo tanto, vía
    # Phillips, la luminosidad real de esta supernova.
    modelo_reposo.set(z=0.0, t0=0.0, x1=x1, c=c)
    try:
        mB0 = modelo_reposo.bandmag("bessellb", "ab", 0.0)
        mB15 = modelo_reposo.bandmag("bessellb", "ab", 15.0)
    except Exception:
        return None
    if not np.isfinite([mB0, mB15]).all():
        return None
    dm15_B = float(mB15 - mB0)

    # Cada supernova sintética recibe la luminosidad que le toca según Phillips.
    # Si en vez de esto se le pusiera M_B = -19,3 a todas, la simulación no
    # tendría relación ancho–luminosidad y validaría de más el camino de vela
    # estándar puro, que es justamente lo que la actividad quiere mejorar.
    M_B_real = PHILLIPS["M_B_0"] + PHILLIPS["pendiente"] * (
        dm15_B - PHILLIPS["dm15_ref"]
    )

    modelo.set(z=z, t0=0.0, x1=x1, c=c)
    modelo.set_source_peakabsmag(M_B_real, "bessellb", "ab", cosmo=cosmo)

    mu = float(cosmo.distmod(z).value)
    m_B_verdadera = mu + M_B_real  # magnitud aparente en B en reposo

    # --- observación simulada -------------------------------------------------
    paso = cfg["cadencia_dias"]
    fases = np.arange(-18.0, 45.0, paso) * (1 + z)
    fases = fases + rng.normal(0.0, 0.4, fases.size)  # jitter de cadencia
    # huecos por mal tiempo / luna: se cae ~20 % de las noches
    fases = fases[rng.random(fases.size) > 0.20]
    if fases.size < 8:
        return None

    dets: list[Deteccion] = []
    for banda_sn, banda in (
        (cfg["banda_sncosmo"], cfg["banda"]),
        (cfg["banda_color_sncosmo"], cfg["banda_color"]),
    ):
        # las dos bandas no se observan exactamente a la vez
        t = fases + rng.normal(0.0, 0.5, fases.size)
        try:
            mag = modelo.bandmag(banda_sn, "ab", t)
        except Exception:
            return None
        ok = np.isfinite(mag) & (mag < cfg["limite_mag"])
        if ok.sum() < 5:
            continue
        t, mag = t[ok], mag[ok]
        err = ruido_ztf(mag, cfg["limite_mag"])
        mag_obs = mag + rng.normal(0.0, err)
        dets += [
            Deteccion(mjd=float(ti), banda=banda, mag=float(mi), error=float(ei))
            for ti, mi, ei in zip(t, mag_obs, err)
        ]

    curva = CurvaDeLuz(oid="sim", survey="sim", detecciones=dets)

    # --- medición, con EL MISMO código que la app ----------------------------
    try:
        foto = F.medir(
            curva, z=z, banda=cfg["banda"], banda_color=cfg["banda_color"], n_bootstrap=0
        )
    except (F.MedicionImposible, ValueError, np.linalg.LinAlgError):
        return None

    return {
        "z": z,
        "x1": x1,
        "c": c,
        "dm15_B_verdadero": dm15_B,
        "dm15_banda_medido": foto.dm15.dm15,
        "m_banda_medida": foto.maximo.mag_max,
        "m_B_verdadera": m_B_verdadera,
        "color": foto.color_max,
        "error_t_max": foto.maximo.t_max,  # en fase, t0 real = 0
    }


def ajustar(muestras: list[dict]) -> dict:
    """Los dos ajustes lineales, por mínimos cuadrados con recorte de atípicos."""
    m = [s for s in muestras if s["color"] is not None]

    # 1) Δm15(B) = a + b·Δm15(g)
    x = np.array([s["dm15_banda_medido"] for s in muestras])
    y = np.array([s["dm15_B_verdadero"] for s in muestras])
    b, a = _recorte_lineal(x, y)
    res1 = y - (a + b * x)

    # 2) m_B − m_g = c0 + c1·(g−r) + c2·z
    A = np.column_stack(
        [
            np.ones(len(m)),
            np.array([s["color"] for s in m]),
            np.array([s["z"] for s in m]),
        ]
    )
    d = np.array([s["m_B_verdadera"] - s["m_banda_medida"] for s in m])
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    res2 = d - A @ coef

    return {
        "dm15": {
            "a": float(a),
            "b": float(b),
            "dispersion": float(np.std(res1)),
            "n": int(len(x)),
        },
        "color": {
            "c0": float(coef[0]),
            "c1": float(coef[1]),
            "c2": float(coef[2]),
            "dispersion": float(np.std(res2)),
            "n": int(len(m)),
        },
    }


def validar(muestras: list[dict], survey: str) -> dict:
    """Comprueba la cadena completa sobre supernovas sintéticas.

    Vuelve a recorrer las simulaciones ya medidas, esta vez pasándolas por
    ``backend.cosmologia`` con la calibración recién escrita, y compara la
    distancia obtenida con la distancia verdadera de la simulación.  Es la única
    prueba en la que conocemos la respuesta exacta: con supernovas reales y
    cercanas, la ley de Hubble está contaminada por velocidades peculiares.
    """
    from backend import cosmologia as C
    from backend.calibracion import cargar

    cargar.cache_clear()
    cosmo = cosmologia_sncosmo()
    resultado: dict[str, dict] = {}

    for nivel in ("estudiante", "docente"):
        errores = []
        for s in muestras:
            foto = F.Fotometria(
                oid="sim",
                banda=SURVEYS[survey]["banda"],
                z=s["z"],
                maximo=F.Maximo(
                    SURVEYS[survey]["banda"], 0.0, s["m_banda_medida"], 0.1, 0.03, 10, 4
                ),
                dm15=F.MedicionDm15(
                    SURVEYS[survey]["banda"], s["dm15_banda_medido"], 0.05, 0.0, 0.0, True
                ),
                color_max=s["color"],
                error_color_max=0.05,
                banda_color=SURVEYS[survey]["banda_color"],
                n_detecciones={},
                avisos=[],
            )
            d = C.calcular(foto, survey=survey, nivel=nivel, ebv=0.0, z=s["z"])
            verdadera = float(cosmo.luminosity_distance(s["z"]).value)
            errores.append(100.0 * (d.distancia_mpc - verdadera) / verdadera)
        a = np.array(errores)
        resultado[nivel] = {
            "sesgo_porcentual": float(np.median(a)),
            "dispersion_porcentual": float(np.std(a)),
            "fraccion_dentro_15pct": float(np.mean(np.abs(a) < 15.0)),
            "n": int(a.size),
        }
    return resultado


def _recorte_lineal(x: np.ndarray, y: np.ndarray, sigmas: float = 3.0):
    usar = np.ones(x.size, bool)
    b = a = 0.0
    for _ in range(3):
        b, a = np.polyfit(x[usar], y[usar], 1)
        r = y - (a + b * x)
        s = 1.4826 * np.median(np.abs(r[usar] - np.median(r[usar])))
        if s <= 0:
            break
        nuevo = np.abs(r - np.median(r[usar])) <= sigmas * s
        if nuevo.sum() < 20 or (nuevo == usar).all():
            break
        usar = nuevo
    return float(b), float(a)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--survey", default="ZTF", choices=sorted(SURVEYS))
    ap.add_argument("--n", type=int, default=900, help="número de simulaciones")
    ap.add_argument("--semilla", type=int, default=20260801)
    ap.add_argument("--figura", action="store_true", help="guarda la figura del método")
    ap.add_argument("--salida", default=str(RAIZ / "data" / "calibracion.json"))
    args = ap.parse_args()

    import sncosmo

    cfg = SURVEYS[args.survey]
    rng = np.random.default_rng(args.semilla)
    modelo = sncosmo.Model(source="salt2")
    modelo_reposo = sncosmo.Model(source="salt2")

    print(f"Simulando {args.n} SN Ia para {args.survey} con SALT2 "
          f"({modelo.source.name} {modelo.source.version})...")

    muestras: list[dict] = []
    intentos = 0
    while len(muestras) < args.n and intentos < args.n * 6:
        intentos += 1
        z = float(rng.uniform(0.005, 0.08))
        x1 = float(rng.normal(0.0, 1.0))
        c = float(rng.normal(0.0, 0.1))
        x1 = float(np.clip(x1, -3.0, 2.0))
        c = float(np.clip(c, -0.2, 0.4))
        s = simular_una(modelo, modelo_reposo, cfg, z, x1, c, rng)
        if s:
            muestras.append(s)
        if intentos % 200 == 0:
            print(f"  {len(muestras)}/{args.n} medidas ({intentos} intentos)")

    if len(muestras) < 100:
        print(f"ERROR: sólo {len(muestras)} simulaciones medibles.", file=sys.stderr)
        return 1

    print(f"  {len(muestras)} simulaciones medibles de {intentos} intentos "
          f"({100*len(muestras)/intentos:.0f} % de éxito)")

    ajustes = ajustar(muestras)
    d, co = ajustes["dm15"], ajustes["color"]
    print(f"\n  Δm15(B) = {d['a']:+.4f} + {d['b']:.4f}·Δm15({cfg['banda']})"
          f"   σ = {d['dispersion']:.3f} mag  (n={d['n']})")
    print(f"  m_B = m_{cfg['banda']} {co['c0']:+.4f} {co['c1']:+.4f}·color "
          f"{co['c2']:+.4f}·z   σ = {co['dispersion']:.3f} mag  (n={co['n']})")

    salida = Path(args.salida)
    datos = (
        json.loads(salida.read_text(encoding="utf-8"))
        if salida.exists()
        else {"surveys": {}}
    )
    datos.update(
        {
            "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "sin_calibrar": False,
            "H0": H0,
            "H0_unidades": "km/s/Mpc",
            "c_km_s": C_KM_S,
            "phillips": PHILLIPS,
        }
    )
    datos.setdefault("surveys", {})[args.survey] = {
        "banda": cfg["banda"],
        "banda_color": cfg["banda_color"],
        "R_B": cfg["R_B"],
        "dm15": ajustes["dm15"],
        "color": ajustes["color"],
        "procedencia": {
            "metodo": "simulaciones SALT2 medidas con backend.fotometria",
            "modelo": f"{modelo.source.name} {modelo.source.version}",
            "sncosmo": sncosmo.__version__,
            "n_simulaciones": len(muestras),
            "semilla": args.semilla,
            "rango_z": [0.005, 0.08],
            "rango_x1": [-3.0, 2.0],
            "rango_c": [-0.2, 0.4],
        },
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEscrito {salida}")

    # Validacion de la cadena completa con la calibración recién escrita.
    print("\nValidación sobre las mismas supernovas sintéticas:")
    val = validar(muestras, args.survey)
    for nivel, v in val.items():
        print(
            f"  {nivel:<11s} sesgo = {v['sesgo_porcentual']:+.1f} %   "
            f"dispersión = {v['dispersion_porcentual']:.1f} %   "
            f"dentro de ±15 % = {100*v['fraccion_dentro_15pct']:.0f} %"
        )
    datos["surveys"][args.survey]["validacion"] = val
    salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.figura:
        _figura(muestras, ajustes, cfg, RAIZ / "frontend" / "img" / "calibracion.png")
    return 0


def _figura(muestras, ajustes, cfg, destino: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d, co = ajustes["dm15"], ajustes["color"]
    fig, ejes = plt.subplots(1, 2, figsize=(11, 4.4))

    x = np.array([s["dm15_banda_medido"] for s in muestras])
    y = np.array([s["dm15_B_verdadero"] for s in muestras])
    ejes[0].scatter(x, y, s=8, alpha=0.35, color="#1b6ca8", edgecolors="none")
    xs = np.linspace(x.min(), x.max(), 50)
    ejes[0].plot(xs, d["a"] + d["b"] * xs, color="#d95f02", lw=2)
    ejes[0].set_xlabel(f"Δm15({cfg['banda']}) medido por la app")
    ejes[0].set_ylabel("Δm15(B) verdadero (SALT2)")
    ejes[0].set_title(
        f"Δm15(B) = {d['a']:+.3f} + {d['b']:.3f}·Δm15({cfg['banda']})\n"
        f"σ = {d['dispersion']:.3f} mag"
    )

    m = [s for s in muestras if s["color"] is not None]
    cx = np.array([s["color"] for s in m])
    cy = np.array([s["m_B_verdadera"] - s["m_banda_medida"] for s in m])
    cz = np.array([s["z"] for s in m])
    puntos = ejes[1].scatter(cx, cy, s=8, alpha=0.5, c=cz, cmap="viridis")
    fig.colorbar(puntos, ax=ejes[1], label="corrimiento al rojo z")
    ejes[1].set_xlabel(f"color ({cfg['banda']} − {cfg['banda_color']}) en el máximo")
    ejes[1].set_ylabel(f"m_B − m_{cfg['banda']}")
    ejes[1].set_title(
        f"m_B = m_{cfg['banda']} {co['c0']:+.3f} {co['c1']:+.3f}·color "
        f"{co['c2']:+.3f}·z\nσ = {co['dispersion']:.3f} mag"
    )

    for e in ejes:
        e.grid(alpha=0.25)
    fig.suptitle("Calibración de banda — SN Ia sintéticas SALT2 medidas con el código de la app")
    fig.tight_layout()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=130)
    print(f"Figura guardada en {destino}")


if __name__ == "__main__":
    raise SystemExit(main())
