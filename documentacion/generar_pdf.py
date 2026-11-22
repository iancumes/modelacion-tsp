"""Compone el informe, las diapositivas y la guía a partir de los JSON medidos."""

import json
from pathlib import Path
from statistics import median
import sys

import matplotlib
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from modsim.visualizar import corrida_ilustrada

RESULTADOS = RAIZ / "resultados"
SALIDA = RAIZ / "output" / "pdf"
NOMBRES = {"eil101": "eil101", "gr229": "gr229", "volcan72": "Volcán 72"}
TINTA = colors.HexColor("#172d42")
TEAL = colors.HexColor("#087e8b")
COBRE = colors.HexColor("#ab512d")
SECUNDARIO = colors.HexColor("#455e70")
LINEA = colors.HexColor("#cbd9e1")
FONDO = colors.HexColor("#eff5f6")

TSPLIB = "https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/tspindex.html"
OPTIMOS = "https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSP-BEST.html"
FAQ = "https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSPFAQ.html"
REPOSITORIO = "https://github.com/iancumes/modelacion-tsp"


def fuentes():
    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for nombre, archivo in [("Texto", "DejaVuSans.ttf"), ("Negrita", "DejaVuSans-Bold.ttf"),
                            ("Cursiva", "DejaVuSans-Oblique.ttf"), ("Codigo", "DejaVuSansMono.ttf")]:
        pdfmetrics.registerFont(TTFont(nombre, str(base / archivo)))
    pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="Negrita", italic="Cursiva", boldItalic="Negrita")


def num(n, dec=0):
    if n is None:
        return "–"
    return f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")


def lista_num(xs, dec=0):
    return ", ".join(num(x, dec) for x in xs)


def ga1(r):
    return next(fila for fila in r["comparacion"] if fila["metodo"] == "GA")


def enlace(texto, url):
    return f'<link href="{url}" color="#087e8b"><u>{texto}</u></link>'


class Documento:
    def __init__(self, archivo, titulo, ancho=612, alto=792, margen=46, pie="Modelación y Simulación 2026"):
        self.c = Canvas(str(SALIDA / archivo), pagesize=(ancho, alto), pageCompression=1)
        self.c.setTitle(titulo)
        self.c.setSubject("TSP simétrico: algoritmo genético y programación entera")
        self.ancho, self.alto, self.margen, self.pie = ancho, alto, margen, pie
        self.w = ancho - 2 * margen
        self.n = 0

    def pagina(self, seccion, titulo="", tam=29):
        if self.n:
            self.c.showPage()
        self.n += 1
        self.c.setStrokeColor(LINEA)
        self.c.line(self.margen, 42, self.ancho - self.margen, 42)
        self.c.setFillColor(SECUNDARIO)
        self.c.setFont("Texto", 8.5)
        self.c.drawString(self.margen, 26, self.pie)
        self.c.drawRightString(self.ancho - self.margen, 26, str(self.n))
        self.y = self.alto - 48
        if seccion:
            self.texto(seccion.upper(), tam=9, color=TEAL, fuente="Negrita", despues=8)
        if titulo:
            self.texto(titulo, tam=tam, fuente="Negrita", interlineado=tam * 1.16, despues=13)

    def texto(self, texto, tam=10.6, fuente="Texto", color=TINTA, interlineado=None, despues=9):
        estilo = ParagraphStyle("texto", fontName=fuente, fontSize=tam, leading=interlineado or tam * 1.4,
                                textColor=color)
        p = Paragraph(texto, estilo)
        _, alto = p.wrap(self.w, self.alto)
        self.y -= alto
        p.drawOn(self.c, self.margen, self.y)
        self.y -= despues
        self.verificar()

    def sub(self, texto):
        self.texto(texto, tam=13, fuente="Negrita", despues=4)

    def nota(self, texto):
        self.texto(texto, tam=9.2, color=SECUNDARIO, despues=9)

    def codigo(self, lineas):
        alto = 13 * len(lineas) + 16
        self.c.setFillColor(FONDO)
        self.c.roundRect(self.margen, self.y - alto, self.w, alto, 5, stroke=0, fill=1)
        self.c.setFillColor(TINTA)
        self.c.setFont("Codigo", 9)
        for i, linea in enumerate(lineas):
            if pdfmetrics.stringWidth(linea, "Codigo", 9) > self.w - 24:
                raise ValueError(f"Línea de código demasiado ancha: {linea}")
            self.c.drawString(self.margen + 12, self.y - 15 - i * 13, linea)
        self.y -= alto + 9
        self.verificar()

    def tabla(self, cabecera, filas, anchos, tam=10, espacio=7):
        matriz = [cabecera, *filas]
        tabla = Table(matriz, colWidths=anchos)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TINTA), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Negrita"), ("FONTNAME", (0, 1), (-1, -1), "Texto"),
            ("FONTSIZE", (0, 0), (-1, -1), tam), ("LEADING", (0, 0), (-1, -1), tam + 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [FONDO, colors.white]),
            ("TEXTCOLOR", (0, 1), (-1, -1), TINTA), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("ALIGN", (1, 0), (-1, 0), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), espacio), ("BOTTOMPADDING", (0, 0), (-1, -1), espacio),
            ("LINEBELOW", (0, -1), (-1, -1), .6, LINEA),
        ]))
        for fila in matriz:
            for valor, ancho in zip(fila, anchos):
                if pdfmetrics.stringWidth(str(valor), "Negrita", tam) > ancho - 12:
                    raise ValueError(f"Celda demasiado ancha para {ancho} pt: {valor}")
        _, alto = tabla.wrap(self.w, self.alto)
        self.y -= alto
        tabla.drawOn(self.c, self.margen, self.y)
        self.y -= 11
        self.verificar()

    def imagen(self, archivo, alto_max, ancho_max=None):
        imagen = ImageReader(str(RESULTADOS / "graficas" / archivo))
        w, h = imagen.getSize()
        factor = min((ancho_max or self.w) / w, alto_max / h)
        self.y -= h * factor
        self.c.drawImage(imagen, self.margen + (self.w - w * factor) / 2, self.y,
                         width=w * factor, height=h * factor)
        self.y -= 6
        self.verificar()

    def verificar(self):
        if self.y < 48:
            raise ValueError(f"Contenido demasiado alto en la página {self.n}: y={self.y:.1f}")

    def guardar(self):
        self.c.save()


def tabla_principal(d, resultados, grande=False):
    filas = [[NOMBRES[r["nombre"]], num(len(r["ids"])), num(r["lp"]["D"]),
              num(ga1(r)["distancia"]), f'{num(ga1(r)["error_pct"], 3)} %'] for r in resultados]
    d.tabla(["Escenario", "Ciudades", "Óptimo LP", "Mejor GA", "Brecha"], filas,
            [200, 138, 180, 180, 166] if grande else [110, 83, 108, 108, 111],
            tam=18 if grande else 10, espacio=13 if grande else 8)


def informe(resultados):
    d = Documento("Informe_tecnico_TSP.pdf", "Informe técnico · El problema del viajante")
    d.pagina("Proyecto del curso · Opción 1")
    d.y -= 44
    d.texto("El problema<br/>del viajante", tam=47, fuente="Negrita", interlineado=53, despues=17)
    d.texto("Algoritmo genético y programación lineal entera", tam=15, color=TEAL, despues=22)
    d.texto("Se busca un circuito que visite todas las ciudades una vez y vuelva al origen con la menor distancia total. El experimento compara la calidad y el tiempo de un algoritmo genético con la solución certificada de un modelo entero en tres instancias simétricas.", tam=12, despues=22)
    tabla_principal(d, resultados)
    b = resultados[1]
    d.texto(f'El GA igualó el óptimo en <b>eil101</b> y <b>Volcán 72</b>. Su mejor ruta para <b>gr229</b> quedó a <b>{num(ga1(b)["error_pct"], 3)} %</b> del óptimo. PuLP y HiGHS certificaron las tres distancias de referencia.', tam=11.5, despues=20)
    d.nota("Las distancias se leen en la unidad de cada instancia. Las brechas porcentuales toman como referencia el óptimo de la misma instancia.")
    d.sub("Código fuente y reproducción")
    d.texto(enlace("github.com/iancumes/modelacion-tsp", REPOSITORIO))

    d.pagina("Escenarios y metodología", "Datos y diseño experimental")
    d.tabla(["Escenario", "Nodos", "Métrica", "Referencia externa"],
            [["eil101", "101", "EUC_2D", "629"], ["gr229", "229", "GEO", "134 602"],
             ["Volcán 72", "72", "EUC_2D", "Instancia propia"]], [126, 67, 111, 216])
    d.sub("Dos instancias de TSPLIB")
    d.texto(f'{enlace("eil101 y gr229", TSPLIB)} se obtuvieron del catálogo de Heidelberg. eil101 corresponde a Christofides y Eilon. gr229, de Grötschel, corresponde al subconjunto Asia/Australia de una instancia de 666 nodos. Los {enlace("óptimos publicados", OPTIMOS)} se consultaron para comprobar el resultado del modelo entero.')
    d.sub("Circuito ficticio de un volcán")
    d.texto("Se diseñaron 36 miradores alrededor de un perímetro elíptico ondulado y 36 paradas interiores, repartidas en tres senderos curvos de 12 puntos alrededor del cráter. El generador aplica perturbaciones con semilla 2026 y guarda las coordenadas con tres decimales. El circuito puede conectar cualquier par de paradas con costo directo.")
    d.sub("Distancias de entrada")
    d.texto("En EUC_2D, d<sub>ij</sub> = ⌊√[(x<sub>i</sub> − x<sub>j</sub>)² + (y<sub>i</sub> − y<sub>j</sub>)²] + 0,5⌋. En GEO, cada coordenada g.mm se separa en grado truncado g y parte fraccional f. Se convierte a radianes con θ = (3,141592/180) (g + 5f/3).")
    d.texto("Para latitudes φ y longitudes λ, se calculan q₁ = cos(λᵢ−λⱼ), q₂ = cos(φᵢ−φⱼ) y q₃ = cos(φᵢ+φⱼ). La distancia GEO es ⌊6378,388·arccos{[(1+q₁)q₂−(1−q₁)q₃]/2}+1⌋. La matriz fija dᵢᵢ = 0. El mapa usa grados decimales y una longitud continua centrada en 130° E.")
    d.sub("Protocolo de comparación")
    d.texto("Se usó la misma matriz para ambos métodos. El GA corrió ocho veces por escenario con las semillas 42, 73, 101, 151, 211, 307, 401 y 503. Cada corrida usó una población de 84 y 240 generaciones después de G0. El modelo entero se resolvió con HiGHS en un hilo y tolerancias de brecha absoluta y relativa de cero.")
    d.texto("Los tiempos de pared incluyen el cálculo de una corrida GA o la construcción y resolución completa del modelo LP, respectivamente. Se excluyeron la compilación inicial de 2-opt, la lectura de datos y la exportación. Equipo de referencia Intel Core i9-13900H, Windows y Python 3.13.2.")

    d.pagina("Diseño del algoritmo", "Algoritmo genético híbrido")
    d.texto("Un cromosoma es una permutación de los n nodos. Se minimiza D(π) = ∑<sub>k=0…n−1</sub> d<sub>πₖ,π₍ₖ₊₁₎ mod n</sub>. Se rota cada ciclo para empezar en el nodo de menor índice y se elige la menor de sus dos orientaciones. Esto permite reconocer duplicados en un TSP simétrico.")
    d.sub("Inicialización y selección")
    d.texto("La población inicial combina 25 % de vecino más cercano, 50 % de vecino aleatorio dentro de los tres más cercanos disponibles y 25 % de permutaciones uniformes. Las dos variantes voraces reciben hasta dos o una pasadas de mejora 2-opt, respectivamente.")
    d.texto("<b>Ranking.</b> El índice r, con r = 1 para el mejor, recibe peso N − r + 1. <b>Torneo.</b> Se muestrea uniformemente sin reemplazo y gana la ruta de menor distancia. <b>Elitismo.</b> Sobreviven las S mejores y los padres se eligen uniformemente entre las primeras max(2, S). <b>Mezcla.</b> Se reserva al menos un élite si S &gt; 0 y se usa ranking o torneo con probabilidad 1/2 en cada selección restante. Ranking y torneo preservan al campeón cuando S &gt; 0.")
    d.sub("Recombinación, mutación y diversidad")
    d.texto("El cruce OX selecciona dos posiciones distintas uniformemente, conserva el tramo del primer padre y rellena los huecos con el orden cíclico del segundo. En el 70 % de estos hijos se aplican hasta dos mejoras 2-opt. La mutación ordinaria invierte un segmento o aplica un doble puente y después usa hasta cuatro mejoras 2-opt. Cada mejora sustituye dos aristas cuando baja la distancia.")
    d.texto("La diversidad es la fracción media de aristas distintas entre dos rutas. Con c<sub>e</sub> apariciones de la arista e, se calcula como 1 − ∑<sub>e</sub> c<sub>e</sub>(c<sub>e</sub>−1)/[N(N−1)n]. Cuando cae por debajo de 0,18, se eleva la probabilidad de doble puente de 0,25 a 0,55 y se dedica el 45 % de los intentos de mutación a barajar un tramo de una ruta elegida uniformemente. Además, cada clon propuesto recibe hasta tres perturbaciones adicionales.")
    d.sub("Cupos y salida")
    d.texto("El experimento distribuye 20 %, 55 % y 25 % en 17 sobrevivientes, 46 hijos por cruce y 21 por mutación. Cada generación ordena la población por distancia, actualiza el archivo de las tres mejores rutas únicas, registra la media y la diversidad y conserva instantáneas de las mejoras de D. La salida devuelve <b>best</b> (ruta) y <b>D</b> (distancia).")
    d.codigo(["G0 = poblacion inicial", "repetir maxIter generaciones:",
              "    evaluar, archivar y seleccionar sobrevivientes", "    crear hijos con OX y variantes de mutacion",
              "evaluar la ultima poblacion y devolver best, D"])

    d.pagina("Formulación y prueba", "Programación lineal entera")
    d.texto("El modelo DFJ se construye en PuLP sobre el grafo completo no dirigido. Sea V el conjunto de ciudades, E el conjunto de pares i &lt; j y d<sub>ij</sub> el costo de la arista. Cada variable x<sub>ij</sub> ∈ {0,1} indica si se utiliza el par {i,j}.")
    d.codigo(["minimizar   Σ_{i<j} d_ij x_ij", "sujeto a    Σ_{e incidente a i} x_e = 2           para todo i ∈ V",
              "            Σ_{e con ambos extremos en S} x_e ≤ |S| − 1",
              "            para todo S ⊂ V con 2 ≤ |S| ≤ n − 2", "            x_e ∈ {0,1}                         para todo e ∈ E"])
    d.texto("La ecuación de grado exige dos aristas por nodo. Por sí sola permite ciclos separados. Los cortes de Dantzig, Fulkerson y Johnson (DFJ) impiden que un subconjunto propio forme un ciclo cerrado. Bajo el grado dos su forma equivalente es ∑<sub>e∈δ(S)</sub>x<sub>e</sub> ≥ 2, donde δ(S) reúne las aristas que salen de S.")
    d.sub("Separación y certificación")
    d.texto("Primero se resuelve la relajación lineal. Se identifican componentes del soporte y se proponen cortes mínimos entre un nodo raíz y los demás. Para proponer los cortes se escalan los pesos a enteros, y se comprueba la violación con los valores originales. Luego se exige que las variables sean binarias. Si el solver encuentra varios ciclos, se agrega un corte por componente, evitando duplicados y complementos, y se resuelve de nuevo.")
    d.texto("Cada modelo intermedio contiene todas las rutas factibles del TSP. Su óptimo es una cota inferior. Cuando el óptimo entero del modelo contiene un único ciclo, ese mismo valor es alcanzable por una ruta del TSP. La igualdad entre cota y valor alcanzable certifica la optimalidad. El código reconstruye el tour y vuelve a sumar sus aristas.")
    formatos = []
    for r in resultados:
        lp = r["lp"]
        formatos.append([NOMBRES[r["nombre"]], num(lp["variables"]), num(lp["cortes_dfj"]),
                         num(lp["restricciones"]), num(lp["cota_continua"], 3), num(lp["D"])])
    d.tabla(["Escenario", "Variables", "Cortes DFJ", "Restr. totales", "Cota relajada", "Ciclo final"],
            formatos, [99, 75, 82, 93, 96, 75], tam=9)
    d.nota("El conteo final es n(n−1)/2 variables binarias y n ecuaciones de grado más los cortes DFJ agregados. La cota relajada es el último valor de la fase continua, antes de la fase entera.")

    for r in resultados:
        pagina_resultado(d, r)

    d.pagina("Resultados y conclusiones", "Calidad, tiempo y repetibilidad")
    d.imagen("brechas_semillas.png", 208)
    d.nota("Cada punto es la mejor ruta de una corrida completa. La altura dentro de una fila separa visualmente los puntos y carece de interpretación cuantitativa.")
    a, b, c = resultados
    d.texto(f'<b>Calidad.</b> En eil101, {sum(g["D"] == a["lp"]["D"] for g in a["ga"])} de 8 corridas igualaron el óptimo. En gr229, la mejor distancia fue {num(ga1(b)["distancia"])} y en Volcán 72 fue {num(ga1(c)["distancia"])}. La mediana entre semillas fue {num(median(g["D"] for g in b["ga"]),1)} y {num(median(g["D"] for g in c["ga"]),1)}, respectivamente.')
    d.texto(f'<b>Tiempo.</b> Las medianas de una corrida de GA fueron {lista_num([median(g["segundos"] for g in r["ga"]) for r in resultados],2)} s, en el orden de la tabla. Los tiempos correspondientes del modelo entero fueron {lista_num([r["lp"]["segundos"] for r in resultados],2)} s. Probar ocho semillas consume la suma de sus tiempos, por lo que una sola línea de la tabla expresa el costo de su corrida de origen.')
    d.texto(f'<b>Diversidad.</b> En gr229, la semilla {corrida_ilustrada(b)["semilla"]} pasó de {num(corrida_ilustrada(b)["historial"][0]["diversidad"], 3)} al inicio a {num(corrida_ilustrada(b)["historial"][-1]["diversidad"], 3)} en G240. El umbral de 0,18 activa perturbaciones más fuertes y la diversidad puede permanecer por debajo de él.')
    d.texto("<b>Límites y sugerencias.</b> La comparación cubre tres instancias y una configuración principal. Para atribuir las mejoras a 2-opt o al mecanismo de diversidad, conviene repetir las mismas semillas con y sin cada operador. También conviene medir más tamaños de población y reportar el tiempo hasta una brecha objetivo. Para resolver instancias mayores con el modelo exacto, conviene reutilizar el árbol de búsqueda con cortes dentro del solver.")
    d.sub("Referencias")
    d.nota(f'G. Reinelt (1991). {enlace("TSPLIB: A Traveling Salesman Problem Library", "https://doi.org/10.1287/ijoc.3.4.376")}. Datos y {enlace("convención de distancia GEO", FAQ)} del catálogo de Heidelberg.')
    d.nota(f'G. Dantzig, R. Fulkerson y S. Johnson (1954). {enlace("Solution of a Large-Scale Traveling-Salesman Problem", "https://doi.org/10.1287/opre.2.4.393")}. Operations Research, 2(4), 393–410.')
    d.nota(f'L. Davis (1985). {enlace("Applying Adaptive Algorithms to Epistatic Domains", "https://ijcai.org/proceedings/1985/29")}. IJCAI, 162–163. Documentación de la {enlace("interfaz de solvers de PuLP", "https://coin-or.github.io/pulp/technical/solvers.html")}.')
    d.guardar()


def pagina_resultado(d, r):
    n, lp, g = len(r["ids"]), r["lp"], corrida_ilustrada(r)
    nombre = NOMBRES[r["nombre"]]
    unidad = "km de TSPLIB" if r["metrica"] == "GEO" else "unidades de la instancia"
    d.pagina("Resultados por escenario", nombre, tam=34)
    d.nota(f'{n} ciudades · {r["metrica"]} · Población GA 84 · 240 generaciones · LP {num(lp["variables"])} variables y {num(lp["restricciones"])} restricciones')
    filas = [["LP · óptimo" if f["metodo"] == "LP" else f'GA · {f["puesto"]}',
              num(f["semilla"]), num(f["segundos"], 3), num(f["optimo"]), num(f["distancia"]),
              num(f["error_pct"], 3)] for f in r["comparacion"]]
    d.tabla(["Tipo y puesto", "Semilla", "Tiempo (s)", "Óptimo teórico", "Ruta obtenida", "Error (%)"],
            filas, [105, 60, 86, 97, 91, 81], tam=9, espacio=6)
    d.nota(f'Distancias en {unidad}. Error = 100 × (D − D*) / D*. Se muestran tres ciclos GA distintos. Puede haber empates en distancia.')
    d.imagen(f'{r["nombre"]}_rutas.png', 145)
    d.nota("Figura de rutas. Izquierda, óptimo certificado. Derecha, mejor ruta GA. El punto de color indica el nodo inicial, que también cierra el ciclo.")
    d.imagen(f'{r["nombre"]}_evolucion.png', 172)
    primera = next(x["generacion"] for x in g["historial"] if x["mejor"] == g["D"])
    escala = " El eje superior usa escala simétrica logarítmica y conserva el cero." if max(
        100 * (corrida["historial"][0]["mejor"] - lp["D"]) / lp["D"] for corrida in r["ga"]
    ) > 3 else ""
    d.nota(f'Figura de evolución. La semilla {g["semilla"]} aparece en color. Pasó de {num(g["historial"][0]["mejor"])} en G0 a {num(g["D"])} en G{primera}. La línea discontinua inferior marca el umbral de diversidad de 0,18.{escala}')


def guia(resultados):
    d = Documento("Guia_exposicion_TSP.pdf", "Guía de exposición y demostración · TSP")
    d.pagina("Guion para la sesión virtual", "Cómo explicar el proyecto")
    d.texto("Duración sugerida de 5 a 6 minutos. Ten abiertos el PDF de presentación y el archivo resultados/visor.html. Deja disponible el código para las preguntas.", tam=12, despues=17)
    d.sub("0:00–0:40 · Problema")
    d.texto('«Buscamos un circuito que visite cada ciudad exactamente una vez y regrese a la primera. Usamos dos instancias de TSPLIB y diseñamos un volcán ficticio con miradores y senderos. Los dos métodos usaron la misma matriz de distancias».')
    d.sub("0:40–1:40 · Implementación")
    d.texto('«El GA guarda cada ruta como una permutación. Elegimos padres por ranking o torneo, cruzamos su orden y mutamos segmentos. 2-opt cambia dos aristas cuando reduce la distancia. Registramos diversidad para reforzar la mutación si muchas rutas comparten aristas».')
    d.texto('«En el modelo entero, cada arista tiene una variable binaria y cada ciudad necesita grado dos. Detectamos ciclos separados y agregamos restricciones DFJ. Cuando el óptimo del modelo es un solo ciclo, su objetivo es a la vez cota inferior y distancia alcanzable».')
    d.sub("1:40–3:30 · Resultados")
    tabla_principal(d, resultados)
    d.texto(f'«En eil101 y Volcán 72, el GA igualó los óptimos de {num(ga1(resultados[0])["distancia"])} y {num(ga1(resultados[2])["distancia"])}. En gr229, quedó a {num(ga1(resultados[1])["error_pct"],3)} % del óptimo. Las tablas reportan las tres mejores rutas GA distintas y el tiempo completo de la semilla que produjo cada una».')
    d.sub("3:30–5:30 · Demostración y cierre")
    d.texto("Reproduce la evolución de gr229 en el visor y pasa a su ruta LP. Muestra el cambio de distancia, los primeros saltos de la curva y el tramo final. Cierra con la diferencia entre hallar una ruta barata y demostrar que ninguna otra puede ser más barata.")

    d.pagina("Demostración", "Visor, terminal y código")
    d.sub("Ruta para mostrar en pantalla")
    d.texto("Abre resultados/visor.html en el navegador. Elige gr229, mantén «Evolución del GA» y pulsa «Reproducir». El control de generación también permite detenerte en G0, G40 o G240. Usa la vista «LP · óptimo certificado» y las tres vistas GA para comparar geometrías.")
    d.sub("Corrida corta")
    d.texto("Abre PowerShell en la carpeta del proyecto con las dependencias instaladas. Ejecuta este ejemplo, que escribe en una carpeta de demostración:")
    d.codigo(["python -m modsim --escenario eil101 --metodo ga --N 30 `",
              "  --maxIter 45 --seleccion torneo --sobrevivientes 6 `",
              "  --cruce 16 --mutacion 8 --semillas 42 --salida demo"])
    d.texto("La terminal imprime la semilla, D y el tiempo. Abre demo/visor.html para ver las 45 generaciones de esa corrida. Para enseñar el modelo entero, ejecuta <font name='Codigo'>python -m modsim --escenario eil101 --metodo lp --detalle-lp --salida demo_lp</font>.")
    d.sub("Símbolos que conviene ubicar en el código")
    d.texto("<b>resolver_ga</b> en genetico.py es el ciclo principal. Muestra <b>cruce_ox</b> para explicar la permutación, <b>dos_opt</b> para el cambio de aristas y <b>diversidad_aristas</b> para la métrica de variedad.")
    d.texto("<b>resolver_exacto</b> en exacto.py declara xᵢⱼ y las n restricciones de grado. La función interna <b>agregar</b> construye los cortes DFJ. <b>reconstruir</b> recupera el recorrido de las aristas elegidas.")
    d.texto("<b>distancia</b> en instancias.py valida la permutación y vuelve a sumar el recorrido. <b>comparar</b> en __main__.py reúne las mejores rutas y calcula la brecha.")
    d.nota("El README contiene la instalación, el significado de los argumentos y la relación entre los CSV y los JSON.")

    d.pagina("Preguntas frecuentes", "Qué defender en la revisión")
    d.sub("¿Qué es una solución factible?")
    d.texto("Una permutación de todas las ciudades con regreso al primer nodo. El GA produce permutaciones y el modelo entero las obtiene al exigir grado dos y conectividad mediante cortes DFJ.")
    d.sub("¿Cómo se seleccionaron las tres soluciones?")
    d.texto("Se unieron los archivos de tres rutas distintas de cada semilla. Se eliminaron rotaciones e inversiones equivalentes, se ordenaron los ciclos por distancia y se tomaron los tres mejores. Varias rutas pueden compartir distancia o semilla.")
    d.sub("¿Qué significa que la brecha sea 0 %?")
    d.texto("La distancia coincide con el óptimo certificado. Puede haber varias permutaciones con el mismo costo mínimo. Los mapas de dos rutas empatadas pueden mostrar tramos distintos.")
    d.sub("¿Qué tiempo se compara?")
    d.texto("El tiempo de una corrida completa de GA frente al tiempo de armar y resolver el modelo entero. Encontrar por primera vez su mejor solución puede ocurrir antes de que el GA cumpla maxIter. El costo del experimento de ocho semillas es la suma de sus corridas.")
    d.sub("¿Por qué usar varios cortes si se conoce la distancia de TSPLIB?")
    d.texto("La distancia publicada sirve para comprobar los resultados después de resolver. La función exacta recibe la matriz de costos y obtiene una ruta y una prueba de optimalidad. El escenario inventado obtiene su referencia del mismo procedimiento.")
    d.sub("¿Qué explica mejor las diferencias entre escenarios?")
    d.texto("El número de nodos, la distribución de puntos, el costo métrico y el trabajo de separación cambian entre casos. Con tres escenarios, se pueden describir las diferencias observadas. Para medir el aporte causal de cada operador del GA se necesita una comparación controlada con las mismas semillas.")
    d.guardar()


def presentacion(resultados):
    d = Documento("Presentacion_TSP.pdf", "Presentación · El problema del viajante",
                  ancho=960, alto=540, margen=48, pie="Modelación y Simulación 2026 · Resultados del experimento")
    d.pagina("Opción 1 · Tres escenarios")
    d.y -= 71
    d.texto("El problema<br/>del viajante", tam=58, fuente="Negrita", interlineado=64, despues=24)
    d.texto("Algoritmo genético y programación lineal entera", tam=24, color=TEAL, despues=18)
    d.texto("eil101 · gr229 · Volcán 72", tam=18, color=SECUNDARIO)

    d.pagina("Comparación", "Distancias y brechas", tam=39)
    d.texto("Óptimo certificado y mejor ruta del GA en cada escenario.", tam=19, despues=22)
    tabla_principal(d, resultados, grande=True)
    d.texto("Ocho semillas por caso, 84 individuos y 240 generaciones por corrida. Cada porcentaje usa como referencia el óptimo de su escenario.", tam=17, color=SECUNDARIO)

    d.pagina("Implementación", "Cómo se construye y verifica una ruta", tam=36)
    d.texto("Algoritmo genético", fuente="Negrita", color=TEAL, tam=21, despues=5)
    d.texto("Una permutación representa cada ciclo. Ranking y torneo seleccionan los candidatos. OX y mutación generan rutas nuevas. La mejora local 2-opt cambia dos aristas para reducir la distancia.", tam=19, despues=27)
    d.texto("Programación lineal entera", fuente="Negrita", color=COBRE, tam=21, despues=5)
    d.texto("Cada arista tiene una variable binaria y cada ciudad debe tener grado dos. Los cortes DFJ excluyen los recorridos con varios ciclos hasta obtener un único recorrido óptimo.", tam=19, despues=28)
    d.texto("PuLP formula el problema. HiGHS resuelve el modelo.", tam=16, color=SECUNDARIO)

    d.pagina("Rutas finales", "gr229 · 229 ciudades", tam=37)
    d.imagen("gr229_rutas.png", 280, 830)
    d.texto(f'Brecha de la mejor ruta GA <b>{num(ga1(resultados[1])["error_pct"],3)} %</b>. Las distancias se calcularon con la métrica GEO de TSPLIB.', tam=16, color=SECUNDARIO)

    d.pagina("Evolución del GA", "Convergencia en gr229", tam=37)
    d.imagen("gr229_evolucion.png", 300, 800)
    d.texto("La semilla de la mejor ruta aparece en color. La diversidad baja al converger y activa una mutación más intensa al cruzar el umbral de 0,18.", tam=16, color=SECUNDARIO)

    d.pagina("Cierre", "Qué muestran los resultados", tam=37)
    d.imagen("brechas_semillas.png", 240, 810)
    d.texto("Las corridas del GA tienen un costo acotado por su número de generaciones. La programación entera certificó las tres referencias de la comparación.", tam=17, color=SECUNDARIO)
    d.guardar()


def main():
    fuentes()
    SALIDA.mkdir(parents=True, exist_ok=True)
    resultados = [json.loads((RESULTADOS / f"{nombre}.json").read_text(encoding="utf-8")) for nombre in NOMBRES]
    informe(resultados)
    guia(resultados)
    presentacion(resultados)


if __name__ == "__main__":
    main()
