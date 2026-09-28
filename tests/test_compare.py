"""Sürüm karşılaştırma mantığını sabitleyen testler."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "compare_versions", REPO / "scripts" / "compare_versions.py"
)
compare_versions = importlib.util.module_from_spec(_spec)
sys.modules["compare_versions"] = compare_versions
_spec.loader.exec_module(compare_versions)


def _cell(lat=40.3775, lon=49.85):
    return pd.DataFrame({"latitude": [lat], "longitude": [lon]})


def _poi(offsets_m, lat=40.3775, lon=49.85):
    deg = 1.0 / 111_320.0
    return pd.DataFrame(
        {
            "lat": [lat + d * deg for d in offsets_m],
            "lon": [lon] * len(offsets_m),
            "name": [f"p{i}" for i in range(len(offsets_m))],
        }
    )


def test_legacy_score_ignores_distance_inside_a_ring():
    """Önceki yöntemin kusuru: halka içinde mesafe fark etmiyordu."""
    near = compare_versions.legacy_score(_cell(), _poi([10.0]), beta=0.3)
    far = compare_versions.legacy_score(_cell(), _poi([490.0]), beta=0.3)
    assert near[0] == far[0]


def test_current_scoring_does_distinguish_inside_a_ring():
    """Karşıt durum: yeni yöntem ayırıyor. Karşılaştırmanın anlamı buradan geliyor."""
    from urbangeoai import scoring

    near = scoring.decay_score(_cell(), _poi([10.0]), beta=0.3)
    far = scoring.decay_score(_cell(), _poi([490.0]), beta=0.3)
    assert near[0] > far[0]


def test_legacy_bands_lose_bands_on_tied_data():
    """Karşılaştırmanın ölçtüğü asıl fark."""
    rng = np.random.default_rng(0)
    index = np.concatenate([np.zeros(500), rng.exponential(1.0, 500)])
    assert compare_versions.legacy_bands(index).max() < 10


def test_compare_reports_no_movement_for_identical_input():
    idx = np.linspace(0, 1, 100)
    band = np.arange(1, 101) % 10 + 1
    r = compare_versions.compare(idx, band, idx, band)
    assert r["spearman"] == 1.0
    assert r["moved_pct"] == 0.0
    assert r["mean_shift"] == 0.0


def test_compare_detects_direction_of_movement():
    idx = np.linspace(0, 1, 100)
    before = np.full(100, 3)
    after = np.full(100, 5)
    r = compare_versions.compare(idx, before, idx, after)
    assert r["up_pct"] == 100.0
    assert r["down_pct"] == 0.0
    assert r["mean_shift"] == 2.0


def test_legacy_score_is_zero_without_poi():
    empty = pd.DataFrame({"lat": [], "lon": [], "name": []})
    assert compare_versions.legacy_score(_cell(), empty, beta=0.2)[0] == 0.0


def test_legacy_sources_cover_every_comparable_member():
    """Eski sürümde bulunmayan kategori karşılaştırmaya girmemeli."""
    from urbangeoai import catalogue

    comparable = {
        g: m
        for g, m in catalogue.GROUPS.items()
        if all(x == "metro" or x in compare_versions.LEGACY_SOURCES for x in m)
    }
    for members in comparable.values():
        for name in members:
            assert name == "metro" or name in compare_versions.LEGACY_SOURCES


def test_safety_group_is_excluded_from_comparison():
    """Kamera ve yanğından mühafizə yalnızca 2026'da var."""
    from urbangeoai import catalogue

    members = catalogue.GROUPS["təhlükəsizlik"]
    assert not all(x in compare_versions.LEGACY_SOURCES for x in members)


def test_frozen_ruler_shows_improvement_that_refitting_hides():
    """Her hücrede hizmet artarsa dondurulmuş cetvel yukarı, yeniden uydurma sıfır gösterir."""
    from urbangeoai import indices

    rng = np.random.default_rng(0)
    # Gerçek veride olduğu gibi iki kategori birlikte artar (merkeze yakınlık).
    centre = rng.gamma(2.0, 1.0, 5000)
    before = pd.DataFrame(
        {
            "a_score": centre + rng.gamma(1.0, 0.3, 5000),
            "b_score": centre + rng.gamma(1.0, 0.3, 5000),
        }
    )
    after = before * 1.5 + 0.5

    ruler = indices.fit_group(before, ["a", "b"])
    _, band_before = indices.score_group(before, ruler)
    _, band_after = indices.score_group(after, ruler)
    frozen = compare_versions.compare(before["a_score"], band_before, after["a_score"], band_after)

    refit = indices.fit_group(after, ["a", "b"])
    _, band_refit = indices.score_group(after, refit)
    relative = compare_versions.compare(
        before["a_score"], band_before, after["a_score"], band_refit
    )

    assert frozen["mean_shift"] > 0.5
    assert abs(relative["mean_shift"]) < 0.05
