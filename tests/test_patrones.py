import numpy as np
import pytest

from patrones import cargar_patron, centrar, colocar, listar_patrones, parse_rle
from vida import paso


def evolucionar(grid, generaciones, toroidal=False):
    for _ in range(generaciones):
        grid = paso(grid, toroidal=toroidal)
    return grid


def en_rejilla(nombre, filas, cols):
    return centrar(np.zeros((filas, cols), dtype=bool), cargar_patron(nombre).celdas)


def test_parse_rle_basico():
    p = parse_rle("#N Glider\n#C comentario\nx = 3, y = 3, rule = B3/S23\nbo$2bo$3o!")
    assert p.nombre == "Glider"
    assert p.regla == "B3/S23"
    assert p.descripcion == "comentario"
    assert p.celdas.tolist() == [
        [False, True, False],
        [False, False, True],
        [True, True, True],
    ]


def test_parse_rle_filas_vacias_y_saltos_de_linea():
    # "2$" salta dos filas; el cuerpo puede partirse en varias lineas
    p = parse_rle("x = 2, y = 3\no\nb2$\no!")
    assert p.celdas.tolist() == [[True, False], [False, False], [True, False]]


def test_parse_rle_sin_cabecera_usa_el_tamano_minimo():
    p = parse_rle("3o$bo!")
    assert p.celdas.shape == (2, 3)
    assert p.celdas.sum() == 4


def test_listar_patrones_incluye_la_biblioteca():
    assert set(listar_patrones()) >= {
        "bellota", "canon-gosper", "diehard", "glider",
        "nave-ligera", "pentadecatlon", "pulsar", "r-pentomino",
    }


@pytest.mark.parametrize("nombre,forma,poblacion", [
    ("bellota", (3, 7), 7),
    ("canon-gosper", (9, 36), 36),
    ("diehard", (3, 8), 7),
    ("glider", (3, 3), 5),
    ("nave-ligera", (4, 5), 9),
    ("pentadecatlon", (3, 10), 12),
    ("pulsar", (13, 13), 48),
    ("r-pentomino", (3, 3), 5),
])
def test_forma_y_poblacion(nombre, forma, poblacion):
    p = cargar_patron(nombre)
    assert p.celdas.shape == forma
    assert p.celdas.sum() == poblacion
    assert p.regla == "B3/S23"


def test_cargar_patron_por_ruta(tmp_path):
    ruta = tmp_path / "mio.rle"
    ruta.write_text("x = 2, y = 2\n2o$2o!")
    p = cargar_patron(str(ruta))
    assert p.nombre == "mio"
    assert p.celdas.all()


def test_cargar_patron_inexistente():
    with pytest.raises(ValueError, match="disponibles"):
        cargar_patron("no-existe")


@pytest.mark.parametrize("nombre,periodo", [("pulsar", 3), ("pentadecatlon", 15)])
def test_osciladores(nombre, periodo):
    g = en_rejilla(nombre, 30, 30)
    for i in range(1, periodo):
        assert not np.array_equal(evolucionar(g, i), g)
    assert np.array_equal(evolucionar(g, periodo), g)


def test_nave_ligera_avanza_dos_celdas_cada_4_generaciones():
    g = en_rejilla("nave-ligera", 20, 20)
    assert np.array_equal(evolucionar(g, 4), np.roll(g, -2, axis=1))


def test_canon_de_gosper_dispara_un_glider_cada_30_generaciones():
    g = colocar(np.zeros((100, 100), dtype=bool), cargar_patron("canon-gosper").celdas, 2, 2)
    poblaciones = []
    for _ in range(5):
        g = evolucionar(g, 30)
        poblaciones.append(int(g.sum()))
    assert poblaciones == [41, 46, 51, 56, 61]


def test_diehard_desaparece_en_la_generacion_130():
    g = en_rejilla("diehard", 100, 100)
    assert evolucionar(g, 129).any()
    assert not evolucionar(g, 130).any()


def test_colocar_toroidal_envuelve_y_fijo_recorta():
    celdas = np.ones((2, 2), dtype=bool)
    t = colocar(np.zeros((4, 4), dtype=bool), celdas, 3, 3, toroidal=True)
    assert t[3, 3] and t[0, 0] and t[3, 0] and t[0, 3]
    f = colocar(np.zeros((4, 4), dtype=bool), celdas, 3, 3, toroidal=False)
    assert f.sum() == 1 and f[3, 3]
