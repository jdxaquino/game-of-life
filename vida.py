"""Motor del Juego de la Vida con NumPy.

La rejilla es un array booleano indexado como grid[fila, columna].
Este modulo no depende de pygame, asi que se puede probar y reutilizar
por separado de la interfaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

# reglas conocidas en notacion B/S (nacer/sobrevivir)
PRESETS = {
    "conway": "B3/S23",
    "highlife": "B36/S23",
    "seeds": "B2/S",
    "dia-y-noche": "B3678/S34678",
    "sin-muerte": "B3/S012345678",
    "laberinto": "B3/S12345",
}

_PATRON_REGLA = re.compile(r"^B([0-8]*)/S([0-8]*)$", re.IGNORECASE)


@dataclass(frozen=True)
class Regla:
    """Numeros de vecinos con los que una celula nace o sobrevive."""

    nacer: frozenset[int]
    sobrevivir: frozenset[int]

    def __str__(self) -> str:
        b = "".join(str(n) for n in sorted(self.nacer))
        s = "".join(str(n) for n in sorted(self.sobrevivir))
        return f"B{b}/S{s}"


CONWAY = Regla(frozenset({3}), frozenset({2, 3}))


def parse_regla(texto: str) -> Regla:
    """Convierte "B3/S23" (o el nombre de un preset) en una Regla."""
    texto = texto.strip()
    texto = PRESETS.get(texto.lower(), texto)
    m = _PATRON_REGLA.match(texto)
    if not m:
        raise ValueError(
            f"regla no válida: {texto!r}; usa la notación B/S (p. ej. B3/S23) "
            f"o uno de: {', '.join(PRESETS)}"
        )
    return Regla(
        frozenset(int(c) for c in m.group(1)),
        frozenset(int(c) for c in m.group(2)),
    )


def contar_vecinos(grid: np.ndarray, toroidal: bool = True) -> np.ndarray:
    """Numero de vecinas vivas (0-8) de cada celda.

    Con toroidal=True los bordes se conectan (lo que sale por un lado entra
    por el opuesto); con False, fuera de la rejilla todo esta muerto.
    """
    g = grid.astype(np.uint8)
    if toroidal:
        n = np.zeros_like(g)
        for df in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if df or dc:
                    n += np.roll(g, (df, dc), axis=(0, 1))
        return n

    p = np.pad(g, 1)
    filas, cols = g.shape
    n = np.zeros_like(g)
    for df in (0, 1, 2):
        for dc in (0, 1, 2):
            if df != 1 or dc != 1:
                n += p[df:df + filas, dc:dc + cols]
    return n


def paso(grid: np.ndarray, regla: Regla = CONWAY, toroidal: bool = True) -> np.ndarray:
    """Calcula la siguiente generacion."""
    n = contar_vecinos(grid, toroidal)
    nace = np.zeros(9, dtype=bool)
    nace[list(regla.nacer)] = True
    sobrevive = np.zeros(9, dtype=bool)
    sobrevive[list(regla.sobrevivir)] = True
    return np.where(grid, sobrevive[n], nace[n])


def actualizar_edad(edad: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Generaciones seguidas que lleva viva cada celula (0 si esta muerta)."""
    return np.where(grid, edad + 1, 0)


def aleatoria(filas: int, cols: int, densidad: float = 0.25, rng=None) -> np.ndarray:
    """Rejilla aleatoria con la proporcion de celulas vivas indicada."""
    rng = np.random.default_rng() if rng is None else rng
    return rng.random((filas, cols)) < densidad
