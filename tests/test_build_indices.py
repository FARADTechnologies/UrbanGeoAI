"""Teslimat hattının sözleşmesini sabitleyen testler."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import h3
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "build_indices", REPO / "scripts" / "build_indices.py"
)
build_indices = importlib.util.module_from_spec(_spec)
sys.modules["build_indices"] = build_indices
_spec.loader.exec_module(build_indices)

from urbangeoai import catalogue, scoring  # noqa: E402


def test_parent_resolutions_are_coarser_than_the_grid():
    """Üst hücreler ana ızgaradan kaba olmalı, yoksa toplama anlamsız."""
    assert all(r < 10 for r in build_indices.PARENT_RESOLUTIONS)


def test_parent_cell_contains_the_child():
    """Platform hangi seviyede birleştirirse birleştirsin doğru hücreye düşmeli."""
    cell = h3.latlng_to_cell(40.3775, 49.85, 10)
    for resolution in build_indices.PARENT_RESOLUTIONS:
        parent = h3.cell_to_parent(cell, resolution)
        assert h3.get_resolution(parent) == resolution
        assert h3.cell_to_parent(cell, resolution) == parent


def test_category_scores_cover_every_supplied_poi_set():
    cells = pd.DataFrame({"latitude": [40.3775], "longitude": [49.85]})
    pois = {
        "coffee": pd.DataFrame({"lat": [40.378], "lon": [49.85], "name": ["a"]}),
        "metro": pd.DataFrame({"lat": [40.379], "lon": [49.85], "name": ["b"]}),
    }
    frame = build_indices.category_scores(cells, pois)
    assert set(frame.columns) == {"coffee_score", "metro_score"}
    assert (frame > 0).all().all()


def test_category_scores_use_the_catalogue_coefficients():
    """Katsayı katalogdan gelmeli; betik kendi kopyasını taşımamalı."""
    cells = pd.DataFrame({"latitude": [40.3775], "longitude": [49.85]})
    poi = pd.DataFrame({"lat": [40.382], "lon": [49.85], "name": ["x"]})
    produced = build_indices.category_scores(cells, {"coffee": poi})["coffee_score"].iloc[0]
    expected = scoring.decay_score(cells, poi, catalogue.DECAY["coffee"])[0]
    assert produced == expected


def test_every_catalogue_group_would_be_emitted():
    """Bir grup sessizce çıktıdan düşmemeli."""
    for group, members in catalogue.GROUPS.items():
        assert members, group
        for member in members:
            assert member in catalogue.DECAY, f"{group}/{member}"
