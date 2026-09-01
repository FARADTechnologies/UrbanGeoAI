"""Mesafeye göre azalan skorlamanın davranışını sabitleyen testler."""

from __future__ import annotations

import numpy as np
import pandas as pd

from urbangeoai import scoring


def _cell(lat: float = 40.3775, lon: float = 49.8500) -> pd.DataFrame:
    return pd.DataFrame({"latitude": [lat], "longitude": [lon]})


def _poi(offsets_m: list[float], lat: float = 40.3775, lon: float = 49.8500) -> pd.DataFrame:
    """POI'leri hücrenin kuzeyine verilen metre kadar uzağa yerleştirir."""
    deg_per_m = 1.0 / 111_320.0
    return pd.DataFrame(
        {
            "lat": [lat + d * deg_per_m for d in offsets_m],
            "lon": [lon] * len(offsets_m),
            "name": [f"poi_{i}" for i in range(len(offsets_m))],
        }
    )


def test_closer_poi_scores_higher():
    near = scoring.decay_score(_cell(), _poi([50.0]), beta=0.3)
    far = scoring.decay_score(_cell(), _poi([2000.0]), beta=0.3)
    assert near[0] > far[0]


def test_distance_within_band_changes_the_score():
    """Halka yöntemi 10 m ile 490 m'yi eşit sayıyordu; sürekli azalım saymaz."""
    close = scoring.decay_score(_cell(), _poi([10.0]), beta=0.3)
    edge = scoring.decay_score(_cell(), _poi([490.0]), beta=0.3)
    assert close[0] > edge[0] * 1.5


def test_larger_beta_decays_faster():
    poi = _poi([800.0])
    gentle = scoring.decay_score(_cell(), poi, beta=0.05)
    steep = scoring.decay_score(_cell(), poi, beta=0.7)
    assert gentle[0] > steep[0]


def test_score_is_additive_over_poi():
    one = scoring.decay_score(_cell(), _poi([100.0]), beta=0.2)
    two = scoring.decay_score(_cell(), _poi([100.0, 100.0]), beta=0.2)
    np.testing.assert_allclose(two[0], one[0] * 2, rtol=1e-9)


def test_poi_beyond_cutoff_is_excluded():
    inside = scoring.decay_score(_cell(), _poi([2900.0]), beta=0.05, cutoff_m=3000)
    outside = scoring.decay_score(_cell(), _poi([3100.0]), beta=0.05, cutoff_m=3000)
    assert inside[0] > 0.0
    assert outside[0] == 0.0


def test_empty_poi_table_scores_zero():
    empty = pd.DataFrame({"lat": [], "lon": [], "name": []})
    assert scoring.decay_score(_cell(), empty, beta=0.2).tolist() == [0.0]


def test_count_within_is_cumulative():
    counts = scoring.count_within(_cell(), _poi([100.0, 700.0, 2500.0]), [500, 1000, 3000])
    assert counts[500][0] == 1
    assert counts[1000][0] == 2
    assert counts[3000][0] == 3


def test_nearest_returns_distance_and_name():
    distance, name = scoring.nearest(_cell(), _poi([250.0]))
    assert 200 < distance[0] < 300
    assert name[0] == "poi_0"


def test_nearest_beyond_service_radius_is_null():
    """Kapsız bırakılırsa 'en yakın metro 39 km' gibi anlamsız değerler üretilir."""
    distance, name = scoring.nearest(_cell(), _poi([9000.0]), cap_m=3000)
    assert np.isnan(distance[0])
    assert name[0] is None


def test_nearest_within_service_radius_is_kept():
    distance, name = scoring.nearest(_cell(), _poi([1200.0]), cap_m=3000)
    assert not np.isnan(distance[0])
    assert name[0] == "poi_0"


def test_nearest_on_empty_table_is_null():
    empty = pd.DataFrame({"lat": [], "lon": [], "name": []})
    distance, name = scoring.nearest(_cell(), empty)
    assert np.isnan(distance[0])
    assert name[0] is None


def test_haversine_distance_is_accurate():
    """Bilinen mesafe: 1 000 m kuzey."""
    distance, _ = scoring.nearest(_cell(), _poi([1000.0]))
    assert abs(distance[0] - 1000.0) < 5.0
