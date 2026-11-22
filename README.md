# El problema del viajante

Proyecto de Modelación y Simulación 2026. Compara un algoritmo genético (GA) y programación lineal entera (LP) en `eil101`, `gr229` y el escenario ficticio Volcán 72.

## Ejecución

Desde PowerShell con Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m modsim --help
.\.venv\Scripts\python.exe -m modsim --salida resultados --detalle-lp
```

El experimento genera las tablas, gráficas y un visor sin conexión en `resultados/`. El modelo exacto de `gr229` puede tardar varios minutos. En Linux o macOS, el ejecutable del entorno es `.venv/bin/python`.

Para una demostración corta:

```powershell
python -m modsim --escenario eil101 --metodo ga --N 30 --maxIter 45 --seleccion torneo --sobrevivientes 6 --cruce 16 --mutacion 8 --semillas 42 --salida demo
```

Para comprobar el modelo exacto contra un caso pequeño calculado de forma exhaustiva, ejecuta `python -m modsim.comprobar --solo-algoritmos`. Después de generar los resultados completos, ejecuta `python -m modsim.comprobar`.

## Código y datos

- `modsim/instancias.py` carga las instancias, calcula las distancias y valida cada ciclo.
- `modsim/genetico.py` implementa selección, cruce de orden, mutación y búsqueda local 2-opt.
- `modsim/exacto.py` formula el modelo en PuLP y usa HiGHS para resolverlo con cortes DFJ.
- `modsim/visualizar.py` y `modsim/visor.html` generan las visualizaciones.
- `documentacion/generar_pdf.py` reproduce los PDF con ReportLab 5.1.0 después de generar los resultados en `resultados/`.
- `datos/` contiene las instancias originales de [TSPLIB](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/tspindex.html) y la instancia ficticia generada para el proyecto.
