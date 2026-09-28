"""OSRM istemcisinin hesabını sunucusuz sabitler."""

from __future__ import annotations

import numpy as np
import pandas as pd

from urbangeoai import osrm

LAT, LON = 40.3777, 49.8520
METRE = 1 / 111_320


def test_polyline_matches_reference_example():
    # Google'ın belgelerindeki örnek (5 basamak).
    lat = np.array([38.5, 40.7, 43.252])
    lon = np.array([-120.2, -120.95, -126.453])
    assert osrm.encode_polyline(lat, lon, precision=5) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


class FakeClient:
    """Yol mesafesi = kuş uçuşu × ``detour``; ``blocked`` hücrelere ulaşılamaz."""

    def __init__(self, detour=1.0, blocked=()):
        self.detour = detour
        self.blocked = set(blocked)
        self.calls = 0

    def table_from(self, lat, lon, dest_lat, dest_lon):
        self.calls += 1
        dist = np.hypot(
            (dest_lat - lat) / METRE, (dest_lon - lon) * np.cos(np.radians(lat)) / METRE
        )
        dist = dist * self.detour
        for i in range(len(dest_lat)):
            if (round(dest_lat[i], 6), round(dest_lon[i], 6)) in self.blocked:
                dist[i] = np.inf
        return dist


def cells(*north_m):
    return pd.DataFrame(
        {"latitude": [LAT + m * METRE for m in north_m], "longitude": [LON] * len(north_m)}
    )


def test_score_uses_road_distance_and_cutoff():
    grid = cells(0, 800, 2500)
    poi = pd.DataFrame({"lat": [LAT], "lon": [LON]})
    score = osrm.walking_score(FakeClient(detour=1.5), grid, poi, beta=0.1)
    expected_800 = np.exp(-0.1 * 800 * 1.5 / 80)
    assert np.isclose(score[1], expected_800, rtol=1e-3)
    assert score[2] == 0, "2500 m × 1.5 = 3750 m > 3 km"


def test_unreachable_cell_gets_nothing():
    grid = cells(0, 500)
    target = (round(grid.latitude[1], 6), round(grid.longitude[1], 6))
    poi = pd.DataFrame({"lat": [LAT], "lon": [LON]})
    score = osrm.walking_score(FakeClient(blocked=[target]), grid, poi, beta=0.1)
    assert score[1] == 0


def test_same_point_objects_share_one_request_but_both_count():
    grid = cells(0, 300)
    poi = pd.DataFrame({"lat": [LAT, LAT], "lon": [LON, LON]})
    client = FakeClient()
    two = osrm.walking_score(client, grid, poi, beta=0.2)
    one = osrm.walking_score(FakeClient(), grid, poi.iloc[:1], beta=0.2)
    assert client.calls == 1
    assert np.allclose(two, 2 * one)
