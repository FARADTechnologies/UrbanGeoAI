"""Panelin üretiminde sessizce bozulabilecek yerleri sabitler.

Panelin kendisi ham veriye ihtiyaç duyar ve burada üretilemez. Test edilen
şey ham veri gerektirmeyen ve yanlış olduğunda gözle fark edilmeyen kısımlar:
koordinat eşlemesi ve şablonun birleştirilmesi.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "build_dashboard", REPO / "scripts" / "build_dashboard.py"
)
build_dashboard = importlib.util.module_from_spec(_spec)
sys.modules["build_dashboard"] = build_dashboard
_spec.loader.exec_module(build_dashboard)

Projection = build_dashboard.Projection

#: Abşeron'u kabaca çevreleyen dört köşe.
CORNERS = [
    [Projection.flatten(40.2, 49.6), Projection.flatten(40.2, 50.2), Projection.flatten(40.6, 50.2)]
]


def test_projection_fills_the_canvas():
    """Veri sınırları tuvalin kenarlarına oturmalı; boşluk bırakırsa harita küçülür."""
    proj = Projection(CORNERS)
    left, bottom = proj.to_px(proj.x0, proj.y0)
    right, top = proj.to_px(proj.x1, proj.y1)
    assert (round(left), round(top)) == (0, 0)
    assert round(right) == round(proj.w)
    assert round(bottom) == round(proj.h)


def test_projection_keeps_the_aspect_ratio():
    """En/boy bozulursa altıgenler ekranda yamuk görünür."""
    proj = Projection(CORNERS)
    data_ratio = (proj.y1 - proj.y0) / (proj.x1 - proj.x0)
    assert abs(proj.h / proj.w - data_ratio) < 1e-9


def test_north_is_up():
    """Ekran koordinatı yukarıdan aşağı artar; enlem tersine dönmeli."""
    proj = Projection(CORNERS)
    _, north = proj.to_px(*Projection.flatten(40.6, 49.9))
    _, south = proj.to_px(*Projection.flatten(40.2, 49.9))
    assert north < south


def test_longitude_is_narrowed_by_latitude():
    """Boylam daraltılmazsa şehir doğu-batı yönünde gerilmiş çıkar."""
    x_wide, _ = Projection.flatten(40.4, 49.9)
    assert x_wide < 49.9


def test_assemble_produces_a_self_contained_file(tmp_path):
    """Şablondaki yer tutucular dolmazsa panel boş açılır."""
    payload = {"meta": {"cells": 7}}
    destination = tmp_path / "panel.html"
    build_dashboard.assemble(payload, destination)
    html = destination.read_text(encoding="utf-8")
    assert "__TABLER__" not in html
    assert "__DATA__" not in html
    assert "--tblr-blue" in html


def test_assemble_escapes_closing_tags(tmp_path):
    """Veride </script> geçerse tarayıcı bloğu erken kapatır ve panel çöker."""
    payload = {"note": "</script><b>x</b>"}
    destination = tmp_path / "panel.html"
    build_dashboard.assemble(payload, destination)
    html = destination.read_text(encoding="utf-8")
    assert "</script><b>" not in html

    start = html.index('<script id="D"')
    body = html[html.index(">", start) + 1 : html.index("</script>", start)]
    assert json.loads(body) == payload


def test_map_resolution_is_coarser_than_the_grid():
    """Haritada res-10 çizilirse tarayıcı yüz binlerce yol düğümüyle boğulur."""
    assert build_dashboard.MAP_RESOLUTION < 10
