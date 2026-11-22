# El problema del viajante

Proyecto de **Modelación y Simulación 2026**, opción 1. Compara un algoritmo genético (GA) con un modelo exacto de programación lineal entera binaria (LP o MILP) en `eil101`, `gr229` y `volcan72`.

## Material del proyecto

| Archivo | Contenido |
|---|---|
| `output/pdf/Informe_tecnico_TSP.pdf` | Diseño, formulación, escenarios, resultados, visualizaciones, tablas y conclusiones. |
| `output/pdf/Presentacion_TSP.pdf` | Diapositivas para compartir en la sesión virtual. |
| `output/pdf/Guia_exposicion_TSP.pdf` | Guion, demostración y respuestas a preguntas sobre los métodos. |
| `resultados/visor.html` | Visor autónomo. Abre el archivo en el navegador y elige un escenario, un método o una semilla. |
| `resultados/comparacion.csv` | Óptimo y tres mejores rutas GA distintas por escenario, con tiempo y error. |
| `resultados/rutas.csv` | IDs originales, distancia de cada tramo y distancia acumulada, incluido el cierre de cada ciclo. |
| `resultados/<escenario>.json` | Corridas completas, rutas, historial en cada generación y registros del solver. |
| `resultados/graficas/` | Comparación de rutas, convergencia, diversidad y variación entre semillas en PNG. |

## Instalación y ejecución

La ejecución se verificó con Python 3.13.2 en Windows. Desde la carpeta del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m modsim --help
```

Para reproducir el experimento completo en una carpeta aparte:

```powershell
.\.venv\Scripts\python.exe -m modsim --salida resultados_reproducidos --detalle-lp
```

En Linux o macOS, el ejecutable del entorno es `.venv/bin/python`. Las tres instancias vienen incluidas. El solver exacto puede tardar varios minutos, según el equipo. El indicador `--detalle-lp` imprime cada resolución, su cota y los cortes nuevos. Abre `resultados_reproducidos/visor.html` cuando termine.

El verificador compara el modelo entero con una enumeración exhaustiva de un caso de ocho nodos y comprueba las rutas, brechas e historiales guardados:

```powershell
python -m modsim.comprobar
```

Los PDF incluidos pueden regenerarse con `python -m pip install reportlab==5.1.0` y `python documentacion/generar_pdf.py` después de ejecutar el experimento en `resultados/`.

Para la demostración en vivo, una corrida pequeña del GA escribe sus resultados en `demo/`:

```powershell
python -m modsim --escenario eil101 --metodo ga --poblacion 30 --iteraciones 45 --seleccion torneo --sobrevivientes 6 --cruce 16 --mutacion 8 --semillas 42 --salida demo
```

| Argumento | Control | Valor del experimento |
|---|---|---|
| `--escenario` | `todos`, `eil101`, `gr229` o `volcan72` | `todos` |
| `--metodo` | `ambos`, `ga` o `lp` | `ambos` |
| `--poblacion` / `--N` | Número de ciclos en la población | 84 |
| `--iteraciones` / `--maxIter` | Generaciones posteriores a la inicial G0 | 240 |
| `--seleccion` | `ranking`, `torneo`, `elitismo` o `mezcla` | `mezcla` |
| `--sobrevivientes` | Conteo entero o porcentaje con `%` | `20%` → 17 |
| `--cruce` | Conteo entero o porcentaje con `%` | `55%` → 46 |
| `--mutacion` | Conteo entero o porcentaje con `%` | `25%` → 21 |
| `--torneo` | Tamaño máximo de la muestra del torneo | 4 |
| `--semillas` | Enteros distintos separados por espacios | `42 73 101 151 211 307 401 503` |
| `--salida` | Carpeta de los resultados | `resultados/` |

Los tres cupos se convierten en cantidades mediante restos mayores. Deben sumar la población antes del redondeo. Por ejemplo, para N = 40 se puede configurar `--sobrevivientes 8 --cruce '55%' --mutacion 10`. Para que una corrida nueva conserve los resultados ya incluidos, usa una carpeta de salida distinta.

## Recorrido por el código

1. `modsim/instancias.py` lee TSPLIB, construye una matriz simétrica y comprueba que cada ruta sea una permutación. `volcan72()` reproduce el archivo de la tercera instancia con la semilla de diseño 2026.
2. `modsim/genetico.py` inicializa rutas, selecciona padres y sobrevivientes, aplica cruce de orden y mutación, y mejora rutas con 2-opt. `resolver_ga()` devuelve `best`, `D`, las tres mejores rutas distintas de cada corrida y su historial.
3. `modsim/exacto.py` construye el modelo DFJ en PuLP, resuelve con HiGHS, detecta subtours y agrega restricciones. `resolver_exacto()` devuelve `best`, `D`, el estado de optimalidad, el tamaño final del modelo y el historial de cortes.
4. `modsim/__main__.py` configura los experimentos, verifica las dos referencias de TSPLIB y exporta las tablas. El tiempo de GA corresponde a la corrida completa de origen. Dos rutas empatadas pueden provenir de la misma corrida.
5. `modsim/visualizar.py` genera las gráficas. `modsim/visor.html` es la plantilla del visor y se usa con los datos embebidos por el exportador. En los JSON, las rutas usan índices desde 0 de la lista `ids`. En `rutas.csv` se exportan directamente los IDs originales.

## Datos y referencias

- [Instancias simétricas de TSPLIB](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/tspindex.html). Los archivos `eil101.tsp` y `gr229.tsp` están descomprimidos a partir de los originales de Heidelberg.
- [Valores óptimos publicados de TSPLIB](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSP-BEST.html) y [convenciones para la distancia GEO](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSPFAQ.html).
- [Artículo original de Dantzig, Fulkerson y Johnson](https://doi.org/10.1287/opre.2.4.393) y [documentación de los solvers de PuLP](https://coin-or.github.io/pulp/technical/solvers.html).
