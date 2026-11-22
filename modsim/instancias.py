"""Lectura TSPLIB, generación del escenario propio y verificación de rutas."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
ESCENARIOS = ("eil101", "gr229", "volcan72")
REFERENCIAS = {"eil101": 629, "gr229": 134602}


@dataclass(frozen=True)
class Instancia:
    nombre: str
    metrica: str
    ids: tuple[int, ...]
    coordenadas: np.ndarray  # x, y para dibujo. En GEO: longitud, latitud.
    costes: np.ndarray

    @property
    def n(self) -> int:
        return len(self.ids)


def volcan72() -> str:
    """El perímetro son miradores y el interior contiene tres senderos ficticios."""
    rng = np.random.default_rng(2026)
    angulo = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    radio = 41 + 4 * np.sin(3 * angulo) + rng.uniform(-1.8, 1.8, len(angulo))
    puntos = list(zip(1.15 * radio * np.cos(angulo), .87 * radio * np.sin(angulo)))
    for orientacion in (0.35, 2.45, 4.6):
        for paso in np.linspace(0, 1, 12):
            radio = 15 + 3 * np.sin(3 * np.pi * paso) + rng.uniform(-1.5, 1.5)
            angulo = orientacion + (paso - .5) * 2.02
            puntos.append((1.15 * radio * np.cos(angulo), .87 * radio * np.sin(angulo)))
    encabezado = ["NAME: volcan72", "TYPE: TSP", "COMMENT: Circuito ficticio de miradores y senderos",
                  "DIMENSION: 72", "EDGE_WEIGHT_TYPE: EUC_2D", "NODE_COORD_SECTION"]
    filas = [f"{i} {x + 60:.3f} {y + 45:.3f}" for i, (x, y) in enumerate(puntos, 1)]
    return "\n".join([*encabezado, *filas, "EOF", ""])


def cargar(ruta: Path) -> Instancia:
    """Lee instancias simétricas con coordenadas EUC_2D o GEO de TSPLIB."""
    cabecera, datos = ruta.read_text(encoding="ascii").split("NODE_COORD_SECTION", 1)
    meta = dict(tuple(campo.strip() for campo in linea.split(":", 1))
                for linea in cabecera.splitlines() if ":" in linea)
    filas = [linea.split() for linea in datos.splitlines() if linea.strip() not in ("", "EOF")]
    ids = tuple(int(fila[0]) for fila in filas)
    puntos = np.asarray([fila[1:] for fila in filas], dtype=float)
    if (meta.get("TYPE") != "TSP" or len(ids) != int(meta["DIMENSION"]) or len(ids) < 3
            or len(set(ids)) != len(ids) or puntos.shape != (len(ids), 2)
            or not np.isfinite(puntos).all()):
        raise ValueError(f"Instancia TSP inválida: {ruta}")

    metrica = meta["EDGE_WEIGHT_TYPE"]
    if metrica == "EUC_2D":
        diferencias = puntos[:, None, :] - puntos[None, :, :]
        costes = np.floor(np.linalg.norm(diferencias, axis=2) + .5).astype(np.int64)
    elif metrica == "GEO":
        # TSPLIB utiliza grados.minutos, truncamiento hacia cero y PI=3.141592.
        grados = np.trunc(puntos)
        decimal = grados + 5 / 3 * (puntos - grados)
        lat, lon = (decimal * (3.141592 / 180)).T
        q1 = np.cos(lon[:, None] - lon)
        q2 = np.cos(lat[:, None] - lat)
        q3 = np.cos(lat[:, None] + lat)
        argumento = .5 * ((1 + q1) * q2 - (1 - q1) * q3)
        costes = (6378.388 * np.arccos(np.clip(argumento, -1, 1)) + 1).astype(np.int64)
        puntos = decimal[:, ::-1].copy()
    else:
        raise ValueError(f"Métrica no implementada: {metrica}")
    np.fill_diagonal(costes, 0)
    return Instancia(meta["NAME"], metrica, ids, puntos, costes)


def canonica(ruta) -> tuple[int, ...]:
    """Representación única de un ciclo, incluso si se rota o se invierte."""
    ruta = tuple(map(int, ruta))
    inicio = ruta.index(min(ruta))
    giro = ruta[inicio:] + ruta[:inicio]
    return min(giro, giro[:1] + giro[:0:-1])


def distancia(instancia: Instancia, ruta) -> int:
    """Comprueba que todas las ciudades estén exactamente una vez y cierra el ciclo."""
    if sorted(ruta) != list(range(instancia.n)):
        raise ValueError("La ruta debe visitar cada ciudad exactamente una vez.")
    orden = np.asarray(ruta, dtype=int)
    return int(instancia.costes[orden, np.roll(orden, -1)].sum())
