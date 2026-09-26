"""La version web (docs/index.html) lleva copias de los patrones: deben coincidir."""

import re
from pathlib import Path

from patrones import DIRECTORIO, listar_patrones

HTML = Path(__file__).resolve().parent.parent / "docs" / "index.html"


def test_patrones_de_la_web_coinciden_con_patrones_rle():
    html = HTML.read_text(encoding="utf-8")
    web = dict(re.findall(
        r'<script type="text/plain" data-patron="([^"]+)">\n(.*?)</script>', html, re.S
    ))
    assert sorted(web) == listar_patrones()
    for nombre, texto in web.items():
        assert texto == (DIRECTORIO / f"{nombre}.rle").read_text(encoding="utf-8"), nombre
