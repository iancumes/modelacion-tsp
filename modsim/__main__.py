"""Punto de entrada para ejecutar y exportar el experimento del curso."""

import argparse
import csv
from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import platform

from .exacto import resolver_exacto
from .genetico import Configuracion, SELECCIONES, resolver_ga
from .instancias import ESCENARIOS, RAIZ, REFERENCIAS, cargar

SEMILLAS = (42, 73, 101, 151, 211, 307, 401, 503)


def argumentos():
    p = argparse.ArgumentParser(description="Comparación de GA y programación entera para el TSP.")
    p.add_argument("--escenario", choices=(*ESCENARIOS, "todos"), default="todos")
    p.add_argument("--metodo", choices=("ambos", "ga", "lp"), default="ambos")
    p.add_argument("--poblacion", "--N", type=int, default=84, help="N, tamaño de población")
    p.add_argument("--iteraciones", "--maxIter", type=int, default=240, help="generaciones después de G0")
    p.add_argument("--seleccion", choices=SELECCIONES, default="mezcla")
    p.add_argument("--sobrevivientes", default="20%", help="cantidad entera o porcentaje explícito")
    p.add_argument("--cruce", default="55%", help="cantidad entera o porcentaje explícito")
    p.add_argument("--mutacion", default="25%", help="cantidad entera o porcentaje explícito")
    p.add_argument("--torneo", type=int, default=4, help="tamaño del torneo")
    p.add_argument("--semillas", type=int, nargs="+", default=SEMILLAS, metavar="S")
    p.add_argument("--salida", type=Path, default=RAIZ / "resultados")
    p.add_argument("--detalle-lp", action="store_true", help="muestra cada vuelta de separación DFJ")
    args = p.parse_args()
    config = Configuracion(args.poblacion, args.iteraciones, args.seleccion, args.sobrevivientes,
                           args.cruce, args.mutacion, args.torneo)
    try:
        config.cantidades()
    except ValueError as exc:
        p.error(str(exc))
    if len(set(args.semillas)) != len(args.semillas):
        p.error("Las semillas deben ser distintas.")
    return args, config


def comparar(instancia, exacto, corridas):
    """Clasifica las tres mejores rutas GA distintas reunidas entre todas las semillas."""
    referencia = exacto["D"] if exacto else REFERENCIAS.get(instancia.nombre)
    filas = []
    if exacto:
        filas.append({"metodo": "LP", "puesto": "Óptimo", "semilla": None, "segundos": exacto["segundos"],
                      "optimo": referencia, "distancia": exacto["D"], "error_pct": 0.0,
                      "ruta": exacto["best"]})
    vistos = {}
    for corrida in corridas:
        for ruta in corrida["top"]:
            vistos.setdefault(tuple(ruta["ruta"]), (ruta["D"], corrida))
    ganadoras = sorted(vistos, key=lambda ruta: (vistos[ruta][0], ruta))[:3]
    for puesto, ruta in enumerate(ganadoras, 1):
        d, corrida = vistos[ruta]
        error = 100 * (d - referencia) / referencia if referencia else None
        filas.append({"metodo": "GA", "puesto": puesto, "semilla": corrida["semilla"],
                      "segundos": corrida["segundos"], "optimo": referencia, "distancia": d,
                      "error_pct": error, "ruta": ruta})
    return filas


def guardar_tablas(resultados, salida):
    columnas = ("escenario", "ciudades", "metrica", "poblacion_ga", "iteraciones_ga", "variables_lp",
                "restricciones_lp", "metodo", "puesto", "semilla", "segundos", "optimo", "distancia",
                "error_pct")
    with (salida / "comparacion.csv").open("w", newline="", encoding="utf-8-sig") as f:
        tabla = csv.DictWriter(f, fieldnames=columnas)
        tabla.writeheader()
        for r in resultados:
            ga, lp = r["config_ga"], r["lp"]
            datos = {"escenario": r["nombre"], "ciudades": len(r["ids"]), "metrica": r["metrica"],
                     "poblacion_ga": ga["poblacion"] if ga else None,
                     "iteraciones_ga": ga["iteraciones"] if ga else None,
                     "variables_lp": lp["variables"] if lp else None,
                     "restricciones_lp": lp["restricciones"] if lp else None}
            for fila in r["comparacion"]:
                tabla.writerow({**datos, **{k: v for k, v in fila.items() if k != "ruta"}})

    with (salida / "rutas.csv").open("w", newline="", encoding="utf-8-sig") as f:
        tabla = csv.writer(f)
        tabla.writerow(("escenario", "metodo", "puesto", "paso", "ciudad", "distancia_tramo", "acumulada"))
        for r in resultados:
            instancia = cargar(RAIZ / "datos" / f"{r['nombre']}.tsp")
            for fila in r["comparacion"]:
                orden = fila["ruta"]
                acumulada = 0
                for paso, ciudad in enumerate((*orden, orden[0])):
                    parcial = int(instancia.costes[orden[paso-1], ciudad]) if paso else 0
                    acumulada += parcial
                    tabla.writerow((r["nombre"], fila["metodo"], fila["puesto"], paso,
                                    r["ids"][ciudad], parcial, acumulada))


def main():
    args, config = argumentos()
    escenarios = ESCENARIOS if args.escenario == "todos" else (args.escenario,)
    salida = args.salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)
    datos_entorno = {"python": platform.python_version(), "sistema": platform.platform(),
                     "procesador": platform.processor(),
                     "paquetes": {p: version(p) for p in ("numpy", "scipy", "numba", "pulp", "highspy", "matplotlib")}}
    resultados = []
    for nombre in escenarios:
        instancia = cargar(RAIZ / "datos" / f"{nombre}.tsp")
        print(f"\n{nombre} · {instancia.n} ciudades · {instancia.metrica}", flush=True)
        exacto, corridas = None, []
        if args.metodo != "lp":
            for semilla in args.semillas:
                corrida = resolver_ga(instancia, config, semilla)
                corridas.append(corrida)
                print(f"  GA semilla {semilla:<3} D={corrida['D']:<7} {corrida['segundos']:.2f} s", flush=True)
        if args.metodo != "ga":
            progreso = (lambda r: print(f"  {r}", flush=True)) if args.detalle_lp else None
            exacto = resolver_exacto(instancia, progreso=progreso)
            if nombre in REFERENCIAS and exacto["D"] != REFERENCIAS[nombre]:
                raise RuntimeError(f"El óptimo calculado de {nombre} difiere de TSPLIB.")
            print(f"  LP óptimo D={exacto['D']:<7} {exacto['segundos']:.2f} s", flush=True)
        comparacion = comparar(instancia, exacto, corridas)
        if exacto and any(r["distancia"] < exacto["D"] for r in comparacion):
            raise RuntimeError("Una ruta genética quedó por debajo del óptimo certificado.")
        resultado = {"nombre": nombre, "ids": instancia.ids, "metrica": instancia.metrica,
                     "coordenadas": instancia.coordenadas.tolist(), "entorno": datos_entorno,
                     "referencia_tsplib": REFERENCIAS.get(nombre), "lp": exacto, "ga": corridas,
                     "config_ga": {**asdict(config), "cantidades": config.cantidades()} if corridas else None,
                     "comparacion": comparacion}
        (salida / f"{nombre}.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        resultados.append(resultado)
    guardar_tablas(resultados, salida)
    from .visualizar import exportar

    exportar(resultados, salida)
    print(f"\nResultados disponibles en {salida}")


if __name__ == "__main__":
    main()
