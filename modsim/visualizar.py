"""Exporta gráficas estáticas y un visor interactivo que funciona sin conexión."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, PercentFormatter
import numpy as np

GA = "#087e8b"
LP = "#ab512d"
TINTA = "#172d42"
GRILLA = "#dbe4eb"
NOMBRES = {"eil101": "eil101", "gr229": "gr229", "volcan72": "Volcán 72"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA, "ytick.color": TINTA, "text.color": TINTA,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRILLA,
                     "axes.grid": True, "grid.color": GRILLA, "grid.alpha": .65, "axes.axisbelow": True,
                     "legend.frameon": False, "savefig.facecolor": "white"})


def proyectar(puntos, geografico):
    """Centra la vista GEO en 130° E y parte segmentos en el borde si lo cruzan."""
    xy = np.asarray(puntos, dtype=float).copy()
    if geografico:
        xy[:, 0] = (xy[:, 0] - 130 + 180) % 360 - 180 + 130
    return xy


def dibujar_ruta(eje, xy, ruta, color, geografico):
    recorrido = xy[np.r_[ruta, ruta[0]]]
    if geografico:
        segmentos = [recorrido[0]]
        for a, b in zip(recorrido, recorrido[1:]):
            if abs(a[0] - b[0]) > 180:
                segmentos.append([np.nan, np.nan])
            segmentos.append(b)
        recorrido = np.asarray(segmentos)
    eje.plot(*recorrido.T, color=color, linewidth=1.25, alpha=.91)
    eje.scatter(*xy.T, s=11 if geografico else 14, color=TINTA, linewidths=0, zorder=3)
    eje.scatter(*xy[ruta[0]], s=46, color=color, edgecolor="white", linewidth=1, zorder=4)
    eje.set_aspect("equal", adjustable="box")
    eje.set_xlabel("Longitud (° E continua)" if geografico else "Coordenada x")


def guardar(figura, ruta):
    figura.savefig(ruta, dpi=190, bbox_inches="tight", pad_inches=.12)
    plt.close(figura)


def rutas(resultado, carpeta):
    filas = resultado["comparacion"]
    if resultado["lp"] and resultado["ga"]:
        filas = filas[:2]
    fig, ejes = plt.subplots(1, len(filas), figsize=(4.6 * len(filas), 3.1), squeeze=False)
    geo = resultado["metrica"] == "GEO"
    xy = proyectar(resultado["coordenadas"], geo)
    for eje, fila in zip(ejes[0], filas):
        nombre = "LP · óptimo certificado" if fila["metodo"] == "LP" else f"GA · puesto {fila['puesto']}"
        eje.set_title(f"{nombre}  |  D = {fila['distancia']:,}".replace(",", " "), loc="left", weight="bold")
        dibujar_ruta(eje, xy, fila["ruta"], LP if fila["metodo"] == "LP" else GA, geo)
    ejes[0][0].set_ylabel("Latitud (°)" if geo else "Coordenada y")
    fig.subplots_adjust(wspace=.27)
    guardar(fig, carpeta / f"{resultado['nombre']}_rutas.png")


def corrida_ilustrada(resultado):
    """Prefiere la semilla ganadora y muestra una mejora si esa semilla empezó en el óptimo."""
    ganadora = next(r for r in resultado["comparacion"] if r["metodo"] == "GA")
    principal = next(g for g in resultado["ga"] if g["semilla"] == ganadora["semilla"])
    if principal["historial"][0]["mejor"] == principal["D"]:
        return next((g for g in resultado["ga"] if g["historial"][0]["mejor"] > g["D"] == principal["D"]),
                    principal)
    return principal


def evolucion(resultado, carpeta):
    fig, (arriba, abajo) = plt.subplots(2, 1, figsize=(8.6, 4.2), sharex=True, layout="constrained")
    ganadora = next(r for r in resultado["comparacion"] if r["metodo"] == "GA")
    referencia = ganadora["optimo"]
    ilustrada = corrida_ilustrada(resultado)
    maximo = 0.0
    for corrida in resultado["ga"]:
        historial = corrida["historial"]
        x = [r["generacion"] for r in historial]
        mejor = np.array([r["mejor"] for r in historial])
        y = 100 * (mejor - referencia) / referencia if referencia else mejor
        maximo = max(maximo, float(y.max()))
        principal = corrida["semilla"] == ilustrada["semilla"]
        estilo = {"color": GA if principal else "#92a7b9", "alpha": 1 if principal else .62,
                  "linewidth": 2.0 if principal else .85, "zorder": 4 if principal else 2}
        arriba.step(x, y, where="post", **estilo)
        abajo.plot(x, [r["diversidad"] for r in historial], **estilo)
    if referencia:
        arriba.axhline(0, color=LP, linestyle="--", linewidth=1)
        if maximo > 3:
            arriba.set_yscale("symlog", linthresh=.3)
            arriba.yaxis.set_major_locator(FixedLocator([t for t in (0, .3, 1, 5, 15, 50) if t <= maximo]))
        else:
            arriba.set_ylim(-.04, max(.25, maximo * 1.08))
        arriba.yaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t:g}".replace(".", ",") + " %"))
    arriba.set_ylabel("Brecha al óptimo" if referencia else "Mejor distancia")
    arriba.set_title(f"Convergencia · semilla {ilustrada['semilla']} en color", loc="left", weight="bold")
    abajo.axhline(.18, linestyle="--", color=LP, linewidth=1)
    abajo.set_ylabel("Diversidad de aristas")
    abajo.set_xlabel("Generación")
    abajo.set_ylim(0, 1)
    guardar(fig, carpeta / f"{resultado['nombre']}_evolucion.png")


def resumen(resultados, carpeta):
    fig, eje = plt.subplots(figsize=(8.6, 3.45), layout="constrained")
    etiquetas = []
    for resultado in resultados:
        if not resultado["ga"]:
            continue
        ganadora = next(r for r in resultado["comparacion"] if r["metodo"] == "GA")
        ref = ganadora["optimo"]
        if not ref:
            continue
        i = len(etiquetas)
        etiquetas.append(NOMBRES[resultado["nombre"]])
        errores = [100 * (r["D"] - ref) / ref for r in resultado["ga"]]
        desplazamiento = np.linspace(-.12, .12, len(errores))
        eje.hlines(i, min(errores), max(errores), color="#aec5ce", linewidth=3, zorder=2)
        eje.scatter(errores, i + desplazamiento, s=40, color=GA, zorder=3)
        eje.scatter([np.median(errores)], [i], marker="D", color=LP, s=52, zorder=4)
    if not etiquetas:
        plt.close(fig)
        return
    eje.set_yticks(range(len(etiquetas)), etiquetas)
    eje.invert_yaxis()
    eje.axvline(0, color=TINTA, linewidth=.8)
    eje.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
    eje.set_xlabel("Brecha de la mejor ruta de cada corrida al óptimo")
    eje.set_title("Variabilidad entre semillas  ·  punto = corrida, rombo = mediana", loc="left", weight="bold")
    guardar(fig, carpeta / "brechas_semillas.png")


def exportar(resultados, salida):
    carpeta = salida / "graficas"
    carpeta.mkdir(exist_ok=True)
    visor = []
    for r in resultados:
        rutas(r, carpeta)
        if r["ga"]:
            evolucion(r, carpeta)
        visor.append({"nombre": r["nombre"], "metrica": r["metrica"], "ids": r["ids"],
                      "xy": proyectar(r["coordenadas"], r["metrica"] == "GEO").tolist(),
                      "config": r["config_ga"], "filas": r["comparacion"],
                      "semilla_ilustrada": corrida_ilustrada(r)["semilla"] if r["ga"] else None,
                      "lp": {k: r["lp"][k] for k in ("variables", "restricciones", "estado", "cota_continua")}
                      if r["lp"] else None,
                      "ga": [{k: g[k] for k in ("semilla", "D", "instantaneas", "historial")} for g in r["ga"]]})
    resumen(resultados, carpeta)
    plantilla = Path(__file__).with_name("visor.html").read_text(encoding="utf-8")
    datos = json.dumps(visor, ensure_ascii=False, separators=(",", ":"))
    (salida / "visor.html").write_text(plantilla.replace("/* DATOS */ null", datos), encoding="utf-8")
