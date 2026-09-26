"""Tests de la interfaz. Corren sin ventana gracias al driver de video "dummy" de SDL."""

import os
from itertools import pairwise

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pygame = pytest.importorskip("pygame")

import gameoflife  # noqa: E402
from gameoflife import App, crear_parser, linea, main  # noqa: E402
from vida import parse_regla  # noqa: E402


def crear_app(*argv):
    return App(crear_parser().parse_args(list(argv)))


def tecla(app, key, unicode=""):
    app.manejar_evento(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=0))


def raton(app, tipo, pos, **extra):
    app.manejar_evento(pygame.event.Event(tipo, pos=pos, **extra))


def centro(app, fila, col):
    return (col * app.celda + app.celda // 2, fila * app.celda + app.celda // 2)


@pytest.fixture(autouse=True)
def cerrar_pygame():
    yield
    pygame.quit()


def test_argumentos_por_defecto():
    args = crear_parser().parse_args([])
    assert (args.columnas, args.filas, args.celda) == (80, 60, 12)
    assert args.regla == parse_regla("B3/S23")
    assert args.bordes == "toroidal"
    assert args.aleatorio is None


def test_argumentos_personalizados():
    args = crear_parser().parse_args(["--regla", "highlife", "--aleatorio", "--bordes", "fijos"])
    assert str(args.regla) == "B36/S23"
    assert args.aleatorio == gameoflife.DENSIDAD
    assert args.bordes == "fijos"


@pytest.mark.parametrize("argv", [
    ["--regla", "B9/S1"], ["--columnas", "2"], ["--aleatorio", "1.5"], ["--velocidad", "0"],
    ["--patron", "no-existe"],
])
def test_argumentos_invalidos(argv):
    with pytest.raises(SystemExit):
        main(argv)


def test_listar_patrones(capsys):
    assert main(["--listar-patrones"]) == 0
    assert "canon-gosper" in capsys.readouterr().out


def test_estado_inicial_original_palo_y_glider():
    app = crear_app()
    assert app.grid.sum() == 8
    assert app.grid[3:6, 5].all()
    assert app.pantalla.get_size() == (80 * 12, 60 * 12)


def test_estado_inicial_con_patron_centrado():
    from patrones import cargar_patron
    app = App(crear_parser().parse_args(["--columnas", "40", "--filas", "20"]),
              cargar_patron("pulsar"))
    assert app.grid.sum() == 48
    assert app.grid[3:16, 13:26].sum() == 48


def test_pausa_paso_limpiar_y_aleatorio():
    app = crear_app()
    tecla(app, pygame.K_SPACE, " ")
    assert app.pausado
    app.actualizar(1.0)
    assert app.generacion == 0

    tecla(app, pygame.K_n, "n")
    assert app.generacion == 1
    assert app.grid[4, 4:7].all()  # el palo ahora es horizontal

    tecla(app, pygame.K_c, "c")
    assert not app.grid.any() and app.generacion == 0

    tecla(app, pygame.K_r, "r")
    assert 0.15 < app.grid.mean() < 0.35


def test_actualizar_avanza_segun_la_velocidad():
    app = crear_app("--velocidad", "10")
    app.actualizar(0.35)
    assert app.generacion == 3
    tecla(app, pygame.K_PLUS, "+")
    assert app.velocidad == 20
    tecla(app, pygame.K_MINUS, "-")
    tecla(app, pygame.K_MINUS, "-")
    assert app.velocidad == 5


def test_pintar_arrastrando_sin_huecos_y_borrar():
    app = crear_app("--pausado")
    tecla(app, pygame.K_c, "c")
    raton(app, pygame.MOUSEBUTTONDOWN, centro(app, 10, 10), button=1)
    raton(app, pygame.MOUSEMOTION, centro(app, 10, 20), rel=(0, 0), buttons=(1, 0, 0))
    raton(app, pygame.MOUSEBUTTONUP, centro(app, 10, 20), button=1)
    assert app.grid[10, 10:21].all() and app.grid.sum() == 11

    raton(app, pygame.MOUSEBUTTONDOWN, centro(app, 10, 15), button=3)
    raton(app, pygame.MOUSEBUTTONUP, centro(app, 10, 15), button=3)
    assert not app.grid[10, 15] and app.grid.sum() == 10

    # sin boton pulsado, mover el raton no pinta
    raton(app, pygame.MOUSEMOTION, centro(app, 30, 30), rel=(0, 0), buttons=(0, 0, 0))
    assert app.grid.sum() == 10


def test_colocar_patron_con_el_raton():
    app = crear_app("--pausado")
    tecla(app, pygame.K_c, "c")
    indice = app.biblioteca.index("canon-gosper")
    tecla(app, pygame.K_1 + indice, str(indice + 1))
    assert app.patron.nombre == "Cañón de Gosper"
    raton(app, pygame.MOUSEBUTTONDOWN, centro(app, 30, 40), button=1)
    assert app.grid.sum() == 36
    tecla(app, pygame.K_ESCAPE)
    assert app.patron is None and app.corriendo


def test_p_recorre_los_patrones_y_vuelve_al_pincel():
    app = crear_app()
    for nombre in app.biblioteca:
        tecla(app, pygame.K_p, "p")
        assert app.biblioteca[app.indice_patron] == nombre
    tecla(app, pygame.K_p, "p")
    assert app.patron is None


def test_salir_con_esc_q_y_cerrar_ventana():
    for evento in (
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0),
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q, unicode="q", mod=0),
        pygame.event.Event(pygame.QUIT),
    ):
        app = crear_app()
        app.manejar_evento(evento)
        assert not app.corriendo


def test_dibujar_pinta_las_celulas_vivas():
    app = crear_app("--pausado")
    app.mostrar_hud = False
    app.dibujar()
    assert app.pantalla.get_at(centro(app, 4, 5))[:3] == gameoflife.VIVA
    assert app.pantalla.get_at(centro(app, 40, 40))[:3] == gameoflife.FONDO

    # con color por edad, una celula vieja ya no es blanca
    app.color_edad = True
    app.edad[4, 5] = 50
    app.dibujar()
    assert app.pantalla.get_at(centro(app, 4, 5))[:3] == tuple(gameoflife.PALETA[50])
    assert tuple(gameoflife.PALETA[50]) != gameoflife.VIVA


def test_dibujar_hud_ayuda_y_fantasma_no_falla():
    app = crear_app()
    app.mostrar_ayuda = True
    tecla(app, pygame.K_p, "p")
    raton(app, pygame.MOUSEMOTION, centro(app, 1, 1), rel=(0, 0), buttons=(0, 0, 0))
    app.dibujar()


def test_linea_bresenham():
    assert list(linea((0, 0), (0, 3))) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert list(linea((2, 2), (0, 0))) == [(2, 2), (1, 1), (0, 0)]
    celdas = list(linea((0, 0), (3, 7)))
    assert celdas[0] == (0, 0) and celdas[-1] == (3, 7)
    # celdas consecutivas siempre adyacentes: no hay huecos
    for (f0, c0), (f1, c1) in pairwise(celdas):
        assert max(abs(f1 - f0), abs(c1 - c0)) == 1


def test_edad_de_celdas_pintadas_y_estampadas():
    app = crear_app("--pausado")
    tecla(app, pygame.K_c, "c")
    raton(app, pygame.MOUSEBUTTONDOWN, centro(app, 5, 5), button=1)
    assert app.edad[5, 5] == 1
    assert np.count_nonzero(app.edad) == 1


def test_bucle_principal_procesa_eventos_y_termina():
    app = crear_app("--velocidad", "240")
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, unicode="c", mod=0))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.ejecutar()
    assert not app.corriendo
    assert not app.grid.any()
