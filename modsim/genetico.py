"""GA de permutaciones con cruce OX, mutación y mejora local 2-opt."""

from bisect import bisect_left
from dataclasses import dataclass
from math import floor, isclose
from random import Random
from time import perf_counter

import numpy as np
from numba import njit

from .instancias import Instancia, canonica, distancia

SELECCIONES = ("ranking", "torneo", "elitismo", "mezcla")


@dataclass(frozen=True)
class Configuracion:
    poblacion: int = 84
    iteraciones: int = 240
    seleccion: str = "mezcla"
    sobrevivientes: str = "20%"
    cruce: str = "55%"
    mutacion: str = "25%"
    torneo: int = 4

    def cantidades(self) -> tuple[int, int, int]:
        """Convierte porcentajes a conteos por restos mayores, respetando enteros."""
        if self.poblacion < 4 or self.iteraciones < 1 or self.torneo < 2:
            raise ValueError("Se requiere N ≥ 4, maxIter ≥ 1 y torneo ≥ 2.")
        if self.seleccion not in SELECCIONES:
            raise ValueError(f"Selección desconocida: {self.seleccion}")
        valores = []
        for entrada in (self.sobrevivientes, self.cruce, self.mutacion):
            texto = str(entrada).strip()
            if texto.endswith("%"):
                valores.append(self.poblacion * float(texto[:-1]) / 100)
            else:
                valores.append(int(texto))
        if any(not (0 <= v <= self.poblacion) for v in valores) or not isclose(
            sum(valores), self.poblacion, rel_tol=0, abs_tol=1e-7
        ):
            raise ValueError("Sobrevivientes, cruce y mutación deben sumar N o 100%.")
        cantidades = [floor(v) for v in valores]
        prioridad = sorted(range(3), key=lambda k: valores[k] - cantidades[k], reverse=True)
        for k in prioridad[:self.poblacion - sum(cantidades)]:
            cantidades[k] += 1
        return tuple(cantidades)


@njit(cache=True)
def dos_opt(orden, costes, pasos):
    """Busca la mejor inversión 2-opt en cada pasada, con un límite de pasadas."""
    n = len(orden)
    for _ in range(pasos):
        mejor_delta = 0
        inicio = fin = 0
        for i in range(n - 2):
            a, b = orden[i], orden[i + 1]
            limite = n - 1 if i == 0 else n  # evita invertir el ciclo entero
            for j in range(i + 2, limite):
                c, d = orden[j], orden[(j + 1) % n]
                delta = costes[a, c] + costes[b, d] - costes[a, b] - costes[c, d]
                if delta < mejor_delta:
                    mejor_delta, inicio, fin = delta, i + 1, j
        if mejor_delta == 0:
            break
        while inicio < fin:
            orden[inicio], orden[fin] = orden[fin], orden[inicio]
            inicio += 1
            fin -= 1
    return orden


def cruce_ox(a, b, rng):
    """Conserva un segmento de A y rellena en el orden cíclico de B."""
    n = len(a)
    inicio, fin = sorted(rng.sample(range(n + 1), 2))
    segmento = a[inicio:fin]
    vistos = set(segmento)
    restantes = [ciudad for ciudad in b[fin:] + b[:fin] if ciudad not in vistos]
    huecos_finales = n - fin
    return tuple(restantes[huecos_finales:]) + segmento + tuple(restantes[:huecos_finales])


def mutar(ruta, rng, diversidad):
    """Invierte un tramo o reordena cuatro tramos mediante un doble puente."""
    n = len(ruta)
    if n >= 8 and rng.random() < (.55 if diversidad < .18 else .25):
        a, b, c, d = sorted(rng.sample(range(n), 4))
        return ruta[:a] + ruta[c:d] + ruta[b:c] + ruta[a:b] + ruta[d:]
    a, b = sorted(rng.sample(range(n), 2))
    return ruta[:a] + ruta[a:b+1][::-1] + ruta[b+1:]


def diversidad_aristas(poblacion: np.ndarray, n: int) -> float:
    """Fracción media de aristas distintas entre todos los pares de rutas."""
    siguiente = np.roll(poblacion, -1, axis=1)
    aristas = np.minimum(poblacion, siguiente) * n + np.maximum(poblacion, siguiente)
    apariciones = np.bincount(aristas.ravel())
    p = len(poblacion)
    coincidencias = np.dot(apariciones, apariciones - 1)
    return 1 - float(coincidencias) / (p * (p - 1) * n)


def resolver_ga(instancia: Instancia, config: Configuracion, semilla: int) -> dict:
    """Devuelve best, D, tres rutas distintas y el historial de todas las generaciones."""
    sobrevivientes, cruces, mutaciones = config.cantidades()
    n, p = instancia.n, config.poblacion
    matriz, ciudades = instancia.costes, tuple(range(n))
    dos_opt(np.arange(n, dtype=np.int64), matriz, 0)  # excluye arranque JIT del cronómetro
    inicio = perf_counter()
    rng = Random(semilla)
    cercanos = np.argsort(matriz, axis=1, kind="stable").tolist()
    acumulado_ranking = [r * (2 * p - r + 1) // 2 for r in range(1, p + 1)]

    def ruta_voraz(ancho):
        ciudad = rng.randrange(n)
        ruta = [ciudad]
        pendientes = set(ciudades) - {ciudad}
        while pendientes:
            opciones = []
            for vecino in cercanos[ciudad]:
                if vecino in pendientes:
                    opciones.append(vecino)
                    if len(opciones) == ancho:
                        break
            ciudad = rng.choice(opciones)
            pendientes.remove(ciudad)
            ruta.append(ciudad)
        return tuple(ruta)

    def mejorar(ruta, pasos):
        return canonica(dos_opt(np.asarray(ruta, dtype=np.int64), matriz, pasos))

    def escoger(esquema, usados=None):
        if esquema == "mezcla":
            esquema = "ranking" if rng.random() < .5 else "torneo"
        if esquema == "ranking" and usados is None:
            return bisect_left(acumulado_ranking, rng.randint(1, acumulado_ranking[-1]))
        disponibles = range(p) if usados is None else [i for i in range(p) if i not in usados]
        if esquema == "ranking":
            return rng.choices(disponibles, weights=[p - i for i in disponibles])[0]
        if esquema == "torneo":
            return min(rng.sample(disponibles, min(config.torneo, len(disponibles))))
        return rng.randrange(max(2, sobrevivientes))

    poblacion = []
    for i in range(p):
        if i < p * .25:
            ruta = mejorar(ruta_voraz(1), 2)
        elif i < p * .75:
            ruta = mejorar(ruta_voraz(3), 1)
        else:
            ruta = canonica(rng.sample(ciudades, n))
        poblacion.append(ruta)

    mejores = {}
    historial = []
    instantaneas = []
    for generacion in range(config.iteraciones + 1):
        arreglo = np.asarray(poblacion, dtype=np.int64)
        costes = matriz[arreglo, np.roll(arreglo, -1, axis=1)].sum(axis=1)
        orden = np.argsort(costes, kind="stable")
        poblacion = [poblacion[i] for i in orden]
        diversidad = diversidad_aristas(arreglo, n)
        previo = min(mejores.values(), default=float("inf"))
        for ruta, indice in zip(poblacion, orden):
            mejores[ruta] = int(costes[indice])
        mejores = dict(sorted(mejores.items(), key=lambda par: (par[1], par[0]))[:3])
        mejor = next(iter(mejores))
        coste = mejores[mejor]
        if generacion == 0 or coste < previo or generacion == config.iteraciones:
            instantaneas.append({"generacion": generacion, "D": coste, "ruta": mejor})
        historial.append({"generacion": generacion, "mejor": coste,
                          "media": float(costes.mean()), "diversidad": diversidad})
        if generacion == config.iteraciones:
            break

        # El campeón siempre sobrevive si se solicitó al menos un sobreviviente.
        elites = sobrevivientes if config.seleccion == "elitismo" else min(1, sobrevivientes)
        if config.seleccion == "mezcla" and sobrevivientes:
            elites = max(1, sobrevivientes // 4)
        elegidos = list(range(elites))
        usados = set(elegidos)
        while len(elegidos) < sobrevivientes:
            indice = escoger(config.seleccion, usados)
            usados.add(indice)
            elegidos.append(indice)
        nueva = [poblacion[i] for i in elegidos]
        presentes = set(nueva)

        for i in range(cruces + mutaciones):
            a = escoger(config.seleccion)
            if i < cruces:
                b = escoger(config.seleccion)
                if a == b:
                    b = (a + rng.randrange(1, p)) % p
                hijo = cruce_ox(poblacion[a], poblacion[b], rng)
                hijo = mejorar(hijo, 2 if rng.random() < .7 else 0)
            elif n >= 20 and diversidad < .18 and rng.random() < .45:
                # Una mutación fuerte conserva el resto del recorrido y reabre la búsqueda.
                padre = poblacion[rng.randrange(p)]
                longitud = rng.randint(n // 5, n // 3)
                inicio_tramo = rng.randrange(n - longitud + 1)
                fin_tramo = inicio_tramo + longitud
                segmento = padre[inicio_tramo:fin_tramo]
                hijo = canonica(padre[:inicio_tramo] + tuple(rng.sample(segmento, longitud))
                                + padre[fin_tramo:])
            else:
                hijo = mejorar(mutar(poblacion[a], rng, diversidad), 4)
            # Una perturbación adicional reduce clones sin cambiar el tamaño de la población.
            for _ in range(3):
                if hijo not in presentes:
                    break
                hijo = canonica(mutar(hijo, rng, diversidad))
            nueva.append(hijo)
            presentes.add(hijo)
        poblacion = nueva

    for ruta, coste in mejores.items():
        if distancia(instancia, ruta) != coste:
            raise RuntimeError("Falló la validación independiente de la ruta GA.")
    return {"semilla": semilla, "best": mejor, "D": mejores[mejor],
            "segundos": perf_counter() - inicio,
            "top": [{"ruta": ruta, "D": coste} for ruta, coste in mejores.items()],
            "historial": historial, "instantaneas": instantaneas}
