"""Izgara kurulumu ve kara maskesi seçimini sabitleyen testler."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
import shapely

from urbangeoai import grid

BBOX = (49.5, 40.2, 50.4, 40.6)


def _square(minlon, minlat, maxlon, maxlat) -> gpd.GeoDataFrame:
    poly = shapely.geometry.box(minlon, minlat, maxlon, maxlat)
    return gpd.GeoDataFrame({"name": ["test"]}, geometry=[poly], crs="EPSG:4326")


def test_bbox_cells_cover_the_requested_box():
    cells = grid.bbox_cells((49.8, 40.35, 49.9, 40.42), 8)
    assert len(cells) > 0
    assert cells["latitude"].between(40.3, 40.47).all()
    assert cells["longitude"].between(49.75, 49.95).all()


def test_resolution_changes_cell_count():
    """Her çözünürlük seviyesi yaklaşık yedi kat daha fazla hücre üretir."""
    coarse = grid.bbox_cells((49.8, 40.35, 49.9, 40.42), 7)
    fine = grid.bbox_cells((49.8, 40.35, 49.9, 40.42), 8)
    assert len(fine) > len(coarse) * 4


def test_land_cells_drops_everything_outside_the_mask():
    box = (49.8, 40.35, 49.9, 40.42)
    full = grid.bbox_cells(box, 9)
    half = grid.land_cells(box, 9, _square(49.8, 40.35, 49.85, 40.42))
    assert 0 < len(half) < len(full)


def test_repair_fixes_self_intersecting_ring():
    """Kendisiyle kesişen halkalar birleştirmede GEOS hatası veriyordu."""
    bowtie = shapely.wkt.loads("POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))")
    frame = gpd.GeoDataFrame({"name": ["x"]}, geometry=[bowtie], crs="EPSG:4326")
    assert not frame.geometry.is_valid.all()
    assert grid.repair(frame).geometry.is_valid.all()


def test_repair_leaves_valid_geometry_untouched():
    frame = _square(49.8, 40.3, 49.9, 40.4)
    assert grid.repair(frame).geometry.iloc[0].equals(frame.geometry.iloc[0])


# ── maske seçimi ────────────────────────────────────────────────────────────


def _write_mask(directory: Path) -> Path:
    """Küçük ama geçerli bir maske dosyası yazar."""
    path = directory / grid.PARTNER_MASK_FILE
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [49.8, 40.35],
                                    [49.9, 40.35],
                                    [49.9, 40.42],
                                    [49.8, 40.42],
                                    [49.8, 40.35],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_partner_mask_is_preferred_when_present(tmp_path):
    """Özgün maske varsa ağa çıkılmamalı ve o kullanılmalı."""
    _write_mask(tmp_path)
    boundary = grid.load_boundary(tmp_path, download=False)
    assert len(boundary) == 1
    assert boundary.total_bounds[0] == pytest.approx(49.8)


def test_wrong_mask_fingerprint_is_reported(tmp_path, capsys):
    """Maske sonucu tek başına belirler; sessizce değişmemeli."""
    _write_mask(tmp_path)
    grid.load_boundary(tmp_path, download=False)
    assert "parmak izini taşımıyor" in capsys.readouterr().err


def test_missing_mask_is_reported_before_falling_back(tmp_path):
    """Yedek sınır farklı bir ızgara üretir; bu sessizce olmamalı."""
    with pytest.raises(FileNotFoundError):
        grid.load_boundary(tmp_path, download=False)


def test_fingerprint_is_stable(tmp_path):
    path = _write_mask(tmp_path)
    assert grid.mask_fingerprint(path) == grid.mask_fingerprint(path)
    assert len(grid.mask_fingerprint(path)) == 64
