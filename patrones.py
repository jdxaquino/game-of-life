"""Patrones en formato RLE, el estandar para compartir patrones del Juego de la Vida.

Ejemplo (un glider):

    #N Glider
    x = 3, y = 3, rule = B3/S23
    bo$2bo$3o!

Cada numero repite el simbolo siguiente: `b` es una celula muerta, `o` una
viva, `$` salta a la fila siguiente y `!` termina el patron.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DIRECTORIO = Path(__file__).resolve().parent / "patrones"

_TOKEN = re.compile(r"(\d*)([^\d\s])")


@dataclass
class Patron:
    nombre: str
    celdas: np.ndarray  # bool, [fila, columna]
    regla: str | None = None
    descripcion: str = ""


def parse_rle(texto: str, nombre: str = "") -> Patron:
    """Lee un patron en formato RLE."""
    ancho = alto = None
    regla = None
    descripcion = []
    cuerpo = []

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("#"):
            tipo, contenido = linea[1:2], linea[2:].strip()
            if tipo == "N":
                nombre = contenido
            elif tipo in ("C", "c"):
                descripcion.append(contenido)
            continue
        if ancho is None and not cuerpo and linea.lower().startswith("x"):
            campos = dict(
                (k.strip().lower(), v.strip())
                for k, v in (c.split("=", 1) for c in linea.split(",") if "=" in c)
            )
            ancho, alto = int(campos["x"]), int(campos["y"])
            regla = campos.get("rule")
            continue
        cuerpo.append(linea)
        if "!" in linea:
            break

    datos = "".join(cuerpo).split("!", 1)[0]
    vivas = []
    fila = col = 0
    for cuenta, simbolo in _TOKEN.findall(datos):
        n = int(cuenta) if cuenta else 1
        if simbolo == "$":
            fila += n
            col = 0
        elif simbolo in ("b", "."):
            col += n
        else:  # `o` (o cualquier otro estado, en RLE multiestado) = viva
            vivas.extend((fila, col + i) for i in range(n))
            col += n

    alto_min = max((f for f, _ in vivas), default=-1) + 1
    ancho_min = max((c for _, c in vivas), default=-1) + 1
    alto = max(alto or 0, alto_min)
    ancho = max(ancho or 0, ancho_min)

    celdas = np.zeros((alto, ancho), dtype=bool)
    for f, c in vivas:
        celdas[f, c] = True
    return Patron(nombre, celdas, regla, " ".join(descripcion))


def listar_patrones() -> list[str]:
    """Nombres de los patrones incluidos en la carpeta patrones/."""
    return sorted(p.stem for p in DIRECTORIO.glob("*.rle"))


def cargar_patron(nombre_o_ruta: str) -> Patron:
    """Carga un patron incluido (por nombre) o cualquier archivo .rle (por ruta)."""
    ruta = Path(nombre_o_ruta)
    if not ruta.is_file():
        ruta = DIRECTORIO / f"{nombre_o_ruta}.rle"
    if not ruta.is_file():
        raise ValueError(
            f"no existe el patron {nombre_o_ruta!r}; "
            f"disponibles: {', '.join(listar_patrones())} (o la ruta a un .rle)"
        )
    return parse_rle(ruta.read_text(encoding="utf-8"), nombre=ruta.stem)


def colocar(grid: np.ndarray, celdas: np.ndarray, fila: int, col: int,
            toroidal: bool = True) -> np.ndarray:
    """Anade las celdas vivas del patron a la rejilla, con su esquina superior
    izquierda en (fila, col). Modifica y devuelve `grid`.

    En una rejilla toroidal lo que sobresale aparece por el lado opuesto; con
    bordes fijos se recorta.
    """
    filas, cols = grid.shape
    fs, cs = np.nonzero(celdas)
    fs = fs + fila
    cs = cs + col
    if toroidal:
        fs %= filas
        cs %= cols
    else:
        dentro = (fs >= 0) & (fs < filas) & (cs >= 0) & (cs < cols)
        fs, cs = fs[dentro], cs[dentro]
    grid[fs, cs] = True
    return grid


def centrar(grid: np.ndarray, celdas: np.ndarray, toroidal: bool = True) -> np.ndarray:
    """Coloca el patron en el centro de la rejilla."""
    fila = (grid.shape[0] - celdas.shape[0]) // 2
    col = (grid.shape[1] - celdas.shape[1]) // 2
    return colocar(grid, celdas, fila, col, toroidal)
