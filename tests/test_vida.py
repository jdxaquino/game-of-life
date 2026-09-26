import numpy as np
import pytest

from vida import (
    CONWAY,
    PRESETS,
    Regla,
    actualizar_edad,
    aleatoria,
    contar_vecinos,
    parse_regla,
    paso,
)


def rejilla(filas, cols, vivas):
    g = np.zeros((filas, cols), dtype=bool)
    for f, c in vivas:
        g[f, c] = True
    return g


def paso_ingenuo(grid, regla, toroidal):
    """Implementacion celda a celda, como el script original, para comparar."""
    filas, cols = grid.shape
    nuevo = np.zeros_like(grid)
    for f in range(filas):
        for c in range(cols):
            n = 0
            for df in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if df == 0 and dc == 0:
                        continue
                    ff, cc = f + df, c + dc
                    if toroidal:
                        n += grid[ff % filas, cc % cols]
                    elif 0 <= ff < filas and 0 <= cc < cols:
                        n += grid[ff, cc]
            nuevo[f, c] = n in (regla.sobrevivir if grid[f, c] else regla.nacer)
    return nuevo


def test_parse_regla_conway():
    assert parse_regla("B3/S23") == CONWAY
    assert parse_regla("b3/s23") == CONWAY
    assert parse_regla("conway") == CONWAY


def test_parse_regla_presets_y_str():
    for nombre, texto in PRESETS.items():
        regla = parse_regla(nombre)
        assert str(regla) == texto.upper()
    assert parse_regla("B2/S") == Regla(frozenset({2}), frozenset())


@pytest.mark.parametrize("texto", ["", "23/3", "B9/S23", "B3S23", "hola"])
def test_parse_regla_invalida(texto):
    with pytest.raises(ValueError):
        parse_regla(texto)


def test_blinker_oscila_con_periodo_2():
    g0 = rejilla(5, 5, [(2, 1), (2, 2), (2, 3)])
    g1 = paso(g0)
    assert np.array_equal(g1, rejilla(5, 5, [(1, 2), (2, 2), (3, 2)]))
    assert np.array_equal(paso(g1), g0)


def test_bloque_es_estable():
    g = rejilla(4, 4, [(1, 1), (1, 2), (2, 1), (2, 2)])
    assert np.array_equal(paso(g), g)


def test_glider_se_desplaza_cada_4_generaciones():
    g = rejilla(10, 10, [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)])
    g4 = g
    for _ in range(4):
        g4 = paso(g4)
    assert np.array_equal(g4, np.roll(g, (1, 1), axis=(0, 1)))


def test_glider_da_la_vuelta_en_rejilla_toroidal():
    g = rejilla(8, 8, [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)])
    h = g
    for _ in range(4 * 8):
        h = paso(h, toroidal=True)
    assert np.array_equal(h, g)


def test_bordes_fijos_no_conectan_lados_opuestos():
    # palo vertical pegado al borde izquierdo
    g = rejilla(5, 5, [(1, 0), (2, 0), (3, 0)])
    assert contar_vecinos(g, toroidal=True)[2, 4] == 3
    assert contar_vecinos(g, toroidal=False)[2, 4] == 0
    assert paso(g, toroidal=True)[2, 4]
    assert not paso(g, toroidal=False)[2, 4]


@pytest.mark.parametrize("texto", ["B3/S23", "B36/S23", "B2/S", "B3678/S34678"])
@pytest.mark.parametrize("toroidal", [True, False])
def test_equivale_a_la_implementacion_ingenua(texto, toroidal):
    regla = parse_regla(texto)
    rng = np.random.default_rng(1234)
    g = aleatoria(17, 23, 0.35, rng)
    for _ in range(5):
        esperado = paso_ingenuo(g, regla, toroidal)
        g = paso(g, regla, toroidal)
        assert np.array_equal(g, esperado)


def test_actualizar_edad():
    edad = np.array([[0, 3], [5, 0]])
    grid = np.array([[True, True], [False, False]])
    assert np.array_equal(actualizar_edad(edad, grid), [[1, 4], [0, 0]])


def test_aleatoria_respeta_la_densidad():
    g = aleatoria(200, 200, 0.3, np.random.default_rng(0))
    assert g.dtype == bool and g.shape == (200, 200)
    assert 0.28 < g.mean() < 0.32
