"""Comprueba las rutas archivadas, las comparaciones y un caso exacto enumerable."""

import argparse
import csv
from itertools import permutations
import json
from math import comb, isclose
from pathlib import Path

import numpy as np

from .exacto import resolver_exacto
from .genetico import Configuracion, cruce_ox
from .instancias import ESCENARIOS, RAIZ, REFERENCIAS, Instancia, canonica, cargar, distancia, volcan72


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def verificar_algoritmos():
    """Un caso pequeño permite validar el solver de forma independiente y exhaustiva."""
    from random import Random

    xy = np.array([(0, 0), (1, 2), (2, 0), (21, 1), (22, 0), (21, 3), (9, 3), (12, -3)])
    costes = np.floor(np.linalg.norm(xy[:, None, :] - xy, axis=2) + .5).astype(np.int64)
    instancia = Instancia("control8", "EUC_2D", tuple(range(1, 9)), xy, costes)
    criterio = min(distancia(instancia, (0, *ruta)) for ruta in permutations(range(1, 8)))
    lp = resolver_exacto(instancia)
    exigir(lp["D"] == criterio and lp["cortes_dfj"] > 0, "Caso exacto de ocho nodos.")
    exigir(Configuracion().cantidades() == (17, 46, 21), "Conversión por restos mayores.")
    a = tuple(range(12))
    rng = Random(2026)
    for _ in range(100):
        b = tuple(rng.sample(a, len(a)))
        exigir(sorted(cruce_ox(a, b, rng)) == list(a), "Cruce de orden inválido.")
    propia = (RAIZ / "datos" / "volcan72.tsp").read_text(encoding="ascii")
    exigir(propia == volcan72(), "El archivo de Volcán 72 no coincide con su generador.")


def verificar_resultados(carpeta):
    esperadas = {}
    for nombre in ESCENARIOS:
        a = cargar(RAIZ / "datos" / f"{nombre}.tsp")
        r = json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
        lp = r["lp"]
        exigir(lp["D"] == distancia(a, lp["best"]), f"Distancia LP inválida en {nombre}.")
        exigir(lp["D"] == REFERENCIAS.get(nombre, lp["D"]), f"Referencia TSPLIB de {nombre}.")
        exigir(lp["variables"] == comb(a.n, 2) and lp["restricciones"] == a.n + lp["cortes_dfj"],
               f"Conteo del modelo de {nombre}.")
        exigir(lp["historial"][-1]["cortes_nuevos"] == 0, f"Cierre de la fase entera de {nombre}.")
        exigir(isclose(lp["historial"][-1]["objetivo"], lp["D"], abs_tol=1e-4),
               f"Objetivo final del solver de {nombre}.")
        acumuladas = {}
        for corrida in r["ga"]:
            historial = corrida["historial"]
            exigir(len(historial) == r["config_ga"]["iteraciones"] + 1, "Longitud del historial.")
            exigir(all(h["generacion"] == i and 0 <= h["diversidad"] <= 1
                       for i, h in enumerate(historial)), "Generación o diversidad inválida.")
            exigir(all(v["mejor"] <= u["mejor"] for u, v in zip(historial, historial[1:])),
                   "La mejor distancia acumulada aumentó.")
            exigir(corrida["D"] == historial[-1]["mejor"] == distancia(a, corrida["best"]),
                   "Distancia final de la corrida inconsistente.")
            for f in [*corrida["top"], *corrida["instantaneas"]]:
                exigir(distancia(a, f["ruta"]) == f["D"] and f["D"] >= lp["D"], f"Ruta GA de {nombre}.")
                if "generacion" in f:
                    exigir(historial[f["generacion"]]["mejor"] == f["D"], "Instantánea inconsistente.")
            for f in corrida["top"]:
                acumuladas[canonica(f["ruta"])] = f["D"]
        exigir(len(r["comparacion"]) == 4, f"Se esperaban cuatro soluciones para {nombre}.")
        top = sorted(acumuladas, key=lambda ruta: (acumuladas[ruta], ruta))[:3]
        exigir([tuple(f["ruta"]) for f in r["comparacion"][1:]] == top, "El top tres global difiere.")
        for f in r["comparacion"]:
            clave = (nombre, f["metodo"], str(f["puesto"]))
            error = 100 * (distancia(a, f["ruta"]) - lp["D"]) / lp["D"]
            exigir(f["optimo"] == lp["D"] and isclose(f["error_pct"], error), "Brecha inconsistente.")
            esperadas[clave] = (f["distancia"], [a.ids[i] for i in (*f["ruta"], f["ruta"][0])])

    rutas = {}
    with (carpeta / "rutas.csv").open(encoding="utf-8-sig", newline="") as archivo:
        for row in csv.DictReader(archivo):
            clave = (row["escenario"], row["metodo"], row["puesto"])
            rutas.setdefault(clave, []).append(row)
    exigir(rutas.keys() == esperadas.keys(), "Rutas esperadas en CSV.")
    for clave, (coste, recorrido) in esperadas.items():
        filas = rutas[clave]
        exigir([int(f["ciudad"]) for f in filas] == recorrido, f"IDs y cierre en {clave}.")
        exigir(sum(int(f["distancia_tramo"]) for f in filas) == coste == int(filas[-1]["acumulada"]),
               f"Suma de tramos en {clave}.")
    print(f"Verificadas {len(esperadas)} rutas de la tabla y todas las rutas GA archivadas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resultados", type=Path, default=RAIZ / "resultados")
    parser.add_argument("--solo-algoritmos", action="store_true")
    args = parser.parse_args()
    verificar_algoritmos()
    print("Modelo exacto contrastado con las 5040 permutaciones del caso de control.")
    if not args.solo_algoritmos:
        verificar_resultados(args.resultados)
