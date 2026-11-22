"""TSP entero en PuLP con restricciones de subtour de Dantzig, Fulkerson y Johnson."""

from math import ceil
from time import perf_counter

import numpy as np
import pulp
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order, connected_components, maximum_flow

from .instancias import Instancia, canonica, distancia


def componentes(n, izquierda, derecha, activas):
    """Componentes del soporte de una solución simétrica."""
    i, j = izquierda[activas], derecha[activas]
    grafo = csr_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    cantidad, etiquetas = connected_components(grafo, directed=False)
    return [tuple(map(int, np.flatnonzero(etiquetas == k))) for k in range(cantidad)]


def cortes_fraccionarios(n, izquierda, derecha, valores):
    """Examina cortes mínimos desde una raíz a cada destino del grafo de soporte."""
    positivas = valores > 1e-8
    grupos = componentes(n, izquierda, derecha, positivas)
    if len(grupos) > 1:
        return grupos

    # SciPy usa capacidades enteras. El escalado propone cortes y el valor real
    # se verifica antes de agregarlos. Todo corte DFJ es válido para un tour.
    i, j = izquierda[positivas], derecha[positivas]
    pesos = np.rint(1_000_000 * valores[positivas]).astype(np.int64)
    grafo = csr_matrix((np.tile(pesos, 2), (np.r_[i, j], np.r_[j, i])), shape=(n, n))
    candidatos = set()
    for destino in range(1, n):
        flujo = maximum_flow(grafo, 0, destino)
        if flujo.flow_value >= 1_999_990:
            continue
        residual = grafo - flujo.flow
        residual.eliminate_zeros()
        lado = breadth_first_order(residual, 0, return_predecessors=False)
        pertenece = np.zeros(n, dtype=bool)
        pertenece[lado] = True
        if valores[pertenece[izquierda] != pertenece[derecha]].sum() < 2 - 1e-6:
            candidatos.add(tuple(sorted(map(int, lado))))
    return sorted(candidatos)


def reconstruir(n, izquierda, derecha, seleccion):
    """Recorre un único ciclo a partir del nodo de índice cero."""
    vecinos = [[] for _ in range(n)]
    for i, j in zip(izquierda[seleccion], derecha[seleccion]):
        vecinos[i].append(int(j))
        vecinos[j].append(int(i))
    if any(len(lista) != 2 for lista in vecinos):
        raise RuntimeError("La solución entera incumple alguna ecuación de grado.")
    ruta = [0, vecinos[0][0]]
    while len(ruta) < n:
        previo, actual = ruta[-2:]
        a, b = vecinos[actual]
        ruta.append(b if a == previo else a)
    if 0 not in vecinos[ruta[-1]]:
        raise RuntimeError("La ruta reconstruida no cierra.")
    return canonica(ruta)


def resolver_exacto(instancia: Instancia, *, progreso=None) -> dict:
    """Construye el modelo completo y añade cortes sin usar rutas o valores de TSPLIB."""
    inicio = perf_counter()
    n = instancia.n
    izquierda, derecha = np.triu_indices(n, k=1)
    pesos = instancia.costes[izquierda, derecha]
    modelo = pulp.LpProblem(instancia.nombre, pulp.LpMinimize)
    variables = [pulp.LpVariable(f"x_{i}_{j}", cat=pulp.LpBinary)
                 for i, j in zip(izquierda, derecha)]
    modelo += pulp.lpSum(int(p) * x for p, x in zip(pesos, variables))
    incidentes = [[] for _ in range(n)]
    for i, j, x in zip(izquierda, derecha, variables):
        incidentes[i].append(x)
        incidentes[j].append(x)
    for i, lista in enumerate(incidentes):
        modelo += pulp.lpSum(lista) == 2, f"grado_{i}"

    cortes = set()
    historial = []
    universo = set(range(n))

    def agregar(grupos):
        antes = len(cortes)
        for grupo in grupos:
            complemento = tuple(sorted(universo.difference(grupo)))
            lado = min(grupo, complemento, key=lambda g: (len(g), g))
            if len(lado) < 2 or lado in cortes:
                continue
            pertenece = np.zeros(n, dtype=bool)
            pertenece[list(lado)] = True
            aristas = np.flatnonzero(pertenece[izquierda] & pertenece[derecha])
            modelo.addConstraint(pulp.lpSum(variables[k] for k in aristas) <= len(lado) - 1,
                                 f"dfj_{len(cortes)}")
            cortes.add(lado)
        return len(cortes) - antes

    for entero in (False, True):
        motor = pulp.HiGHS(mip=entero, msg=False, gapRel=0, gapAbs=0, threads=1)
        fase = "entera" if entero else "continua"
        while True:
            estado = modelo.solve(motor)
            if estado != pulp.LpStatusOptimal or modelo.sol_status != pulp.LpSolutionOptimal:
                raise RuntimeError(f"HiGHS no certificó el modelo ({fase}): {pulp.LpStatus[estado]}.")
            valores = np.fromiter((v.value() for v in variables), dtype=float)
            objetivo = float(pesos @ valores)
            if entero and np.max(np.abs(valores - np.rint(valores))) > 1e-5:
                raise RuntimeError("El solver devolvió valores no enteros.")
            grupos = (componentes(n, izquierda, derecha, valores > .5) if entero
                      else cortes_fraccionarios(n, izquierda, derecha, valores))
            nuevos = agregar(grupos) if not entero or len(grupos) > 1 else 0
            registro = {"fase": fase, "objetivo": objetivo, "cortes_nuevos": nuevos,
                        "segundos_acumulados": perf_counter() - inicio}
            historial.append(registro)
            if progreso:
                progreso(registro)
            if nuevos == 0:
                break
        if not entero:
            cota_continua = objetivo

    if len(grupos) != 1:
        raise RuntimeError("La solución entera final contiene subtours.")
    ruta = reconstruir(n, izquierda, derecha, valores > .5)
    coste = distancia(instancia, ruta)
    if abs(objetivo - coste) > 1e-4 or ceil(cota_continua - 1e-6) > coste:
        raise RuntimeError("Inconsistencia entre el solver y la validación independiente.")
    return {"best": ruta, "D": coste, "segundos": perf_counter() - inicio,
            "estado": "Óptimo certificado", "variables": len(variables),
            "restricciones": n + len(cortes), "cortes_dfj": len(cortes),
            "cota_continua": cota_continua, "historial": historial}
