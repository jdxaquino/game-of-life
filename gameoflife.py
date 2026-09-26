#!/usr/bin/env python3
# Jose D'Aquino
# National Institute of Astrophysics, Optics and Electronics
# jdxaquino@gmail.com
"""El Juego de la Vida de Conway con pygame.

Ejecuta ./gameoflife.py --help para ver las opciones y pulsa F1 en la
ventana para ver los controles.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pygame

import patrones
import vida

# colores
FONDO = (25, 25, 25)
VIVA = (255, 255, 255)
REJILLA = (50, 50, 50)
FANTASMA = (90, 170, 255, 150)
HUD_FONDO = (0, 0, 0, 170)
HUD_TEXTO = (230, 230, 230)
HUD_AVISO = (255, 200, 60)

FPS_DIBUJO = 60
VELOCIDADES = (1, 2, 5, 10, 20, 30, 60, 120, 240)  # generaciones por segundo
MAX_PASOS_POR_FRAME = 8
DENSIDAD = 0.25


def crear_paleta() -> np.ndarray:
    """Color para cada edad (0-255): recien nacidas en blanco, despues amarillo,
    naranja, rojo y violeta a medida que envejecen. La edad 0 es el fondo."""
    edades = [1, 4, 12, 30, 80, 255]
    colores = [(255, 255, 255), (255, 235, 120), (255, 160, 50),
               (230, 60, 70), (150, 50, 170), (70, 70, 200)]
    indices = np.arange(256)
    paleta = np.stack(
        [np.interp(indices, edades, [c[i] for c in colores]) for i in range(3)], axis=1
    ).astype(np.uint8)
    paleta[0] = FONDO
    return paleta


PALETA = crear_paleta()


def linea(inicio, fin):
    """Celdas entre dos celdas (Bresenham), para pintar arrastrando sin huecos."""
    f0, c0 = inicio
    f1, c1 = fin
    df, dc = abs(f1 - f0), -abs(c1 - c0)
    sf = 1 if f0 < f1 else -1
    sc = 1 if c0 < c1 else -1
    err = df + dc
    while True:
        yield f0, c0
        if (f0, c0) == (f1, c1):
            return
        e2 = 2 * err
        if e2 >= dc:
            err += dc
            f0 += sf
        if e2 <= df:
            err += df
            c0 += sc


class App:
    def __init__(self, args: argparse.Namespace, patron_inicial: patrones.Patron | None = None):
        self.filas, self.cols, self.celda = args.filas, args.columnas, args.celda
        self.regla = args.regla
        self.toroidal = args.bordes == "toroidal"
        self.velocidad = args.velocidad
        self.densidad = args.aleatorio or DENSIDAD
        self.color_edad = args.color_edad
        self.pausado = args.pausado
        self.mostrar_rejilla = True
        self.mostrar_hud = True
        self.mostrar_ayuda = False

        self.biblioteca = patrones.listar_patrones()
        self._cache_patrones: dict[str, patrones.Patron] = {}
        self.indice_patron = -1
        self.patron: patrones.Patron | None = None  # patron a colocar con el raton
        self.trazo: bool | None = None  # True pinta, False borra, None sin arrastre
        self.ultima_celda = None
        self.cursor = None

        # estado inicial
        self.grid = np.zeros((self.filas, self.cols), dtype=bool)
        if args.aleatorio:
            self.grid = vida.aleatoria(self.filas, self.cols, self.densidad)
        if patron_inicial is not None:
            patrones.centrar(self.grid, patron_inicial.celdas, self.toroidal)
        if not args.aleatorio and patron_inicial is None:
            # el palo y el glider del juego original
            patrones.colocar(self.grid, np.ones((3, 1), dtype=bool), 3, 5)
            patrones.colocar(self.grid, self._cargar("glider").celdas, 21, 20)
        self.edad = self.grid.astype(np.int32)
        self.generacion = 0
        self.acumulado = 0.0
        self.corriendo = True

        pygame.display.init()  # sin audio: el juego no lo usa
        pygame.font.init()
        self.pantalla = pygame.display.set_mode((self.cols * self.celda, self.filas * self.celda))
        pygame.display.set_caption("Juego de la Vida")
        self.fuente = pygame.font.Font(None, 22)
        self.capa_rejilla = self._crear_capa_rejilla()
        self.fantasma = None
        self.reloj = pygame.time.Clock()

    def _cargar(self, nombre):
        if nombre not in self._cache_patrones:
            self._cache_patrones[nombre] = patrones.cargar_patron(nombre)
        return self._cache_patrones[nombre]

    # --- simulacion ---------------------------------------------------------

    def avanzar(self):
        self.grid = vida.paso(self.grid, self.regla, self.toroidal)
        self.edad = vida.actualizar_edad(self.edad, self.grid)
        self.generacion += 1

    def actualizar(self, dt: float):
        """Avanza tantas generaciones como correspondan al tiempo transcurrido."""
        if self.pausado:
            self.acumulado = 0.0
            return
        self.acumulado += dt
        intervalo = 1 / self.velocidad
        pasos = 0
        while self.acumulado >= intervalo and pasos < MAX_PASOS_POR_FRAME:
            self.avanzar()
            self.acumulado -= intervalo
            pasos += 1
        if pasos == MAX_PASOS_POR_FRAME:
            self.acumulado = 0.0  # el equipo no da abasto: no acumular retraso

    def limpiar(self):
        self.grid[:] = False
        self.edad[:] = 0
        self.generacion = 0

    def aleatorizar(self):
        self.grid = vida.aleatoria(self.filas, self.cols, self.densidad)
        self.edad = self.grid.astype(np.int32)
        self.generacion = 0

    def cambiar_velocidad(self, sentido: int):
        if sentido > 0:
            self.velocidad = next((v for v in VELOCIDADES if v > self.velocidad), VELOCIDADES[-1])
        else:
            self.velocidad = next(
                (v for v in reversed(VELOCIDADES) if v < self.velocidad), VELOCIDADES[0]
            )

    # --- edicion con el raton -----------------------------------------------

    def celda_en(self, pos, ajustar=False):
        """Celda (fila, columna) bajo un punto de la ventana, o None si cae fuera."""
        f, c = pos[1] // self.celda, pos[0] // self.celda
        if ajustar:
            return min(max(f, 0), self.filas - 1), min(max(c, 0), self.cols - 1)
        if 0 <= f < self.filas and 0 <= c < self.cols:
            return f, c
        return None

    def pintar(self, celda):
        f, c = celda
        if self.grid[f, c] != self.trazo:
            self.grid[f, c] = self.trazo
            self.edad[f, c] = int(self.trazo)

    def seleccionar_patron(self, indice: int):
        """Activa el patron `indice` de la biblioteca; fuera de rango vuelve al pincel."""
        if not 0 <= indice < len(self.biblioteca):
            self.indice_patron, self.patron, self.fantasma = -1, None, None
            return
        self.indice_patron = indice
        self.patron = self._cargar(self.biblioteca[indice])
        self.fantasma = self._crear_fantasma(self.patron.celdas)

    def siguiente_patron(self):
        """P recorre los patrones y, tras el ultimo, vuelve al pincel."""
        self.seleccionar_patron(self.indice_patron + 1)

    def estampar(self, celda):
        """Coloca el patron activo centrado en la celda."""
        alto, ancho = self.patron.celdas.shape
        antes = self.grid.copy()
        patrones.colocar(self.grid, self.patron.celdas,
                         celda[0] - alto // 2, celda[1] - ancho // 2, self.toroidal)
        self.edad[self.grid & ~antes] = 1

    # --- eventos ------------------------------------------------------------

    def manejar_evento(self, e):
        if e.type == pygame.QUIT:
            self.corriendo = False
        elif e.type == pygame.KEYDOWN:
            self._tecla(e)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.cursor = e.pos
            celda = self.celda_en(e.pos)
            if celda is None:
                return
            if self.patron is not None:
                if e.button == 1:
                    self.estampar(celda)
                elif e.button == 3:
                    self.seleccionar_patron(-1)
            elif e.button in (1, 3):
                self.trazo = e.button == 1
                self.ultima_celda = celda
                self.pintar(celda)
        elif e.type == pygame.MOUSEMOTION:
            self.cursor = e.pos
            if self.trazo is not None:
                celda = self.celda_en(e.pos, ajustar=True)
                for c in linea(self.ultima_celda, celda):
                    self.pintar(c)
                self.ultima_celda = celda
        elif e.type == pygame.MOUSEBUTTONUP and e.button in (1, 3):
            self.trazo = None

    def _tecla(self, e):
        k, u = e.key, getattr(e, "unicode", "")
        if k == pygame.K_ESCAPE:
            if self.patron is not None:
                self.seleccionar_patron(-1)
            elif self.mostrar_ayuda:
                self.mostrar_ayuda = False
            else:
                self.corriendo = False
        elif k == pygame.K_q:
            self.corriendo = False
        elif k == pygame.K_SPACE:
            self.pausado = not self.pausado
        elif k == pygame.K_n:
            self.avanzar()
        elif k == pygame.K_c:
            self.limpiar()
        elif k == pygame.K_r:
            self.aleatorizar()
        elif u == "+" or k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.cambiar_velocidad(+1)
        elif u == "-" or k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cambiar_velocidad(-1)
        elif k == pygame.K_a:
            self.color_edad = not self.color_edad
        elif k == pygame.K_g:
            self.mostrar_rejilla = not self.mostrar_rejilla
        elif k == pygame.K_h:
            self.mostrar_hud = not self.mostrar_hud
        elif k == pygame.K_F1 or u == "?":
            self.mostrar_ayuda = not self.mostrar_ayuda
        elif k == pygame.K_p:
            self.siguiente_patron()
        elif u and u in "123456789":
            self.seleccionar_patron(int(u) - 1)

    # --- dibujo -------------------------------------------------------------

    def _crear_capa_rejilla(self):
        if self.celda < 4:
            return None
        ancho, alto = self.pantalla.get_size()
        capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        for x in range(0, ancho, self.celda):
            pygame.draw.line(capa, REJILLA, (x, 0), (x, alto))
        for y in range(0, alto, self.celda):
            pygame.draw.line(capa, REJILLA, (0, y), (ancho, y))
        return capa

    def _crear_fantasma(self, celdas):
        alto, ancho = celdas.shape
        sup = pygame.Surface((ancho * self.celda, alto * self.celda), pygame.SRCALPHA)
        for f, c in np.argwhere(celdas):
            sup.fill(FANTASMA, (c * self.celda, f * self.celda, self.celda, self.celda))
        return sup

    def dibujar(self):
        if self.color_edad:
            rgb = PALETA[np.minimum(self.edad, 255)]
        else:
            rgb = np.where(self.grid[..., None], VIVA, FONDO).astype(np.uint8)
        # surfarray usa [x, y]: transponemos filas y columnas
        pequena = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        pygame.transform.scale(pequena, self.pantalla.get_size(), self.pantalla)

        if self.mostrar_rejilla and self.capa_rejilla is not None:
            self.pantalla.blit(self.capa_rejilla, (0, 0))
        if self.fantasma is not None and self.cursor is not None:
            celda = self.celda_en(self.cursor, ajustar=True)
            alto, ancho = self.patron.celdas.shape
            x = (celda[1] - ancho // 2) * self.celda
            y = (celda[0] - alto // 2) * self.celda
            self.pantalla.blit(self.fantasma, (x, y))
        if self.mostrar_hud:
            self._dibujar_hud()
        if self.mostrar_ayuda:
            self._dibujar_ayuda()

    def _texto(self, texto, color=HUD_TEXTO):
        return self.fuente.render(texto, True, color)

    def _dibujar_hud(self):
        bordes = "toroidal" if self.toroidal else "bordes fijos"
        estado = (f"Gen {self.generacion}    Población {int(self.grid.sum())}    "
                  f"{self.velocidad:g} gen/s    {self.regla}    {bordes}")
        if self.pausado:
            estado += "    EN PAUSA"
        if self.patron is not None:
            modo = f"Patrón: {self.patron.nombre}  (clic: colocar · clic der./Esc: salir)"
        else:
            modo = "Pincel  (clic izq.: pintar · clic der.: borrar)    F1: ayuda"
        lineas = [self._texto(estado, HUD_AVISO if self.pausado else HUD_TEXTO),
                  self._texto(modo)]

        alto = sum(s.get_height() for s in lineas) + 12
        barra = pygame.Surface((self.pantalla.get_width(), alto), pygame.SRCALPHA)
        barra.fill(HUD_FONDO)
        y = 6
        for s in lineas:
            barra.blit(s, (8, y))
            y += s.get_height()
        self.pantalla.blit(barra, (0, 0))

    def _dibujar_ayuda(self):
        n = min(len(self.biblioteca), 9)
        controles = [
            ("Espacio", "pausar / reanudar"),
            ("N", "avanzar una generación"),
            ("C", "limpiar"),
            ("R", "rellenar al azar"),
            ("+ / -", "más / menos velocidad"),
            ("Clic izq.", "pintar (se puede arrastrar)"),
            ("Clic der.", "borrar (se puede arrastrar)"),
            (f"1-{n} / P", "elegir patrón; clic para colocarlo"),
            ("A", "color según la edad"),
            ("G", "líneas de la rejilla"),
            ("H", "mostrar / ocultar la barra"),
            ("F1 / ?", "mostrar / ocultar esta ayuda"),
            ("Esc / Q", "salir (Esc primero suelta el patrón)"),
        ]
        filas = [(self._texto(t, HUD_AVISO), self._texto(d)) for t, d in controles]
        nombres = [self._texto(f"{i + 1}   {self._cargar(self.biblioteca[i]).nombre}")
                   for i in range(n)]
        alto_linea = self.fuente.get_linesize()
        ancho_tecla = max(t.get_width() for t, _ in filas) + 16
        ancho = ancho_tecla + max(d.get_width() for _, d in filas) + 32
        alto = (len(filas) + len(nombres) + 2) * alto_linea + 24

        panel = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 215))
        y = 12
        for tecla, desc in filas:
            panel.blit(tecla, (16, y))
            panel.blit(desc, (16 + ancho_tecla, y))
            y += alto_linea
        y += alto_linea
        panel.blit(self._texto("Patrones", HUD_AVISO), (16, y))
        y += alto_linea
        for s in nombres:
            panel.blit(s, (16, y))
            y += alto_linea
        self.pantalla.blit(panel, panel.get_rect(center=self.pantalla.get_rect().center))

    # --- bucle principal ----------------------------------------------------

    def ejecutar(self):
        while self.corriendo:
            dt = self.reloj.tick(FPS_DIBUJO) / 1000
            for e in pygame.event.get():
                self.manejar_evento(e)
            self.actualizar(dt)
            self.dibujar()
            pygame.display.flip()


# --- linea de comandos ------------------------------------------------------

def _entero(minimo):
    def convertir(texto):
        valor = int(texto)
        if valor < minimo:
            raise argparse.ArgumentTypeError(f"debe ser un entero >= {minimo}")
        return valor
    return convertir


def _positivo(texto):
    valor = float(texto)
    if valor <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que 0")
    return valor


def _densidad(texto):
    valor = float(texto)
    if not 0 < valor <= 1:
        raise argparse.ArgumentTypeError("debe estar entre 0 y 1")
    return valor


def _regla(texto):
    try:
        return vida.parse_regla(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="El Juego de la Vida de Conway. Pulsa F1 en la ventana para ver los controles.",
        epilog="ejemplos:\n"
               "  ./gameoflife.py --patron canon-gosper --columnas 120 --celda 8\n"
               "  ./gameoflife.py --aleatorio 0.3 --regla highlife --color-edad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    p = parser.add_argument_group("opciones")
    p.add_argument("-h", "--help", action="help", help="mostrar esta ayuda y salir")
    p.add_argument("--columnas", type=_entero(5), default=80, help="ancho de la rejilla (80)")
    p.add_argument("--filas", type=_entero(5), default=60, help="alto de la rejilla (60)")
    p.add_argument("--celda", type=_entero(1), default=12, help="tamaño de cada celda en px (12)")
    p.add_argument("--velocidad", type=_positivo, default=10, help="generaciones por segundo (10)")
    p.add_argument("--regla", type=_regla, default=vida.CONWAY,
                   help="regla B/S, p. ej. B36/S23, o un preset: "
                        f"{', '.join(vida.PRESETS)} (conway)")
    p.add_argument("--bordes", choices=("toroidal", "fijos"), default="toroidal",
                   help="toroidal: los lados se conectan; fijos: fuera todo está muerto (toroidal)")
    p.add_argument("--patron", metavar="NOMBRE|RUTA",
                   help="patrón inicial centrado: nombre de la biblioteca o ruta a un .rle")
    p.add_argument("--aleatorio", type=_densidad, nargs="?", const=DENSIDAD, metavar="DENSIDAD",
                   help=f"empezar con celdas al azar (densidad {DENSIDAD} si no se indica)")
    p.add_argument("--color-edad", action="store_true", help="colorear las células según su edad")
    p.add_argument("--pausado", action="store_true", help="empezar en pausa para dibujar")
    p.add_argument("--listar-patrones", action="store_true",
                   help="mostrar los patrones incluidos y salir")
    return parser


def main(argv=None) -> int:
    parser = crear_parser()
    args = parser.parse_args(argv)

    if args.listar_patrones:
        for nombre in patrones.listar_patrones():
            p = patrones.cargar_patron(nombre)
            print(f"{nombre:15} {p.descripcion}")
        return 0

    patron_inicial = None
    if args.patron:
        try:
            patron_inicial = patrones.cargar_patron(args.patron)
        except ValueError as e:
            parser.error(str(e))

    try:
        App(args, patron_inicial).ejecutar()
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
