"""API sözleşmesinin testleri — ham veri olmadan, sentetik küçük tabloyla."""

from __future__ import annotations

import h3
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from urbangeoai import api

LAT, LON = 40.3777, 49.8520
GROUPS = ["təhsil", "nəqliyyat"]


@pytest.fixture(scope="module")
def client():
    centre = h3.latlng_to_cell(LAT, LON, 10)
    cells = [centre, *[c for c in h3.grid_disk(centre, 1) if c != centre]]
    rows = []
    for i, c in enumerate(cells):
        lat, lon = h3.cell_to_latlng(c)
        rows.append(
            {
                "h3_index": c,
                "h3_res6": h3.cell_to_parent(c, 6),
                "h3_res7": h3.cell_to_parent(c, 7),
                "h3_res8": h3.cell_to_parent(c, 8),
                "latitude": lat,
                "longitude": lon,
                "təhsil_score": 10 if i == 0 else 4,
                "nəqliyyat_score": 3,
                "təhsil_index": 1.5,
                "nəqliyyat_index": -0.2,
                "distance_to_metro_m": float("nan") if i else 250.0,
            }
        )
    pool = {
        "coffee": pd.DataFrame(
            {
                "lat": [LAT, LAT + 0.02],
                "lon": [LON, LON],
                "name": ["A", "Uzaq"],
                "source": ["yerli", "osm"],
            }
        )
    }
    store = api.Store.build(pd.DataFrame(rows), GROUPS, {"model": {"fitted_on": "previous"}}, pool)
    with TestClient(api.create_app(lambda: store)) as test_client:
        yield test_client, centre


def test_health(client):
    c, _ = client
    assert c.get("/health").json() == {"status": "ok", "cells": 7}


def test_point_returns_its_h10_cell(client):
    c, centre = client
    body = c.get("/v1/point", params={"lat": LAT, "lon": LON}).json()
    assert body["h3_index"] == centre
    assert body["resolution"] == 10
    assert body["scores"] == {"təhsil": 10, "nəqliyyat": 3}
    assert body["distances_m"]["metro"] == 250.0


def test_missing_distance_is_null_not_nan(client):
    c, centre = client
    neighbour = next(x for x in h3.grid_disk(centre, 1) if x != centre)
    body = c.get(f"/v1/cells/{neighbour}").json()
    assert body["distances_m"]["metro"] is None


def test_coarser_cell_is_the_mean_of_its_children(client):
    c, centre = client
    parent = h3.cell_to_parent(centre, 7)
    body = c.get(f"/v1/cells/{parent}").json()
    assert body["resolution"] == 7
    assert body["cells"] == 7
    assert body["scores"]["təhsil"] == pytest.approx((10 + 4 * 6) / 7, abs=1e-4)


def test_invalid_and_outside_cells(client):
    c, _ = client
    assert c.get("/v1/cells/not-a-cell").status_code == 400
    far = h3.latlng_to_cell(41.5, 48.0, 10)
    assert c.get(f"/v1/cells/{far}").status_code == 404
    assert c.get("/v1/point", params={"lat": 41.5, "lon": 48.0}).status_code == 404


def test_batch_marks_points_outside_the_area(client):
    c, _ = client
    body = c.post(
        "/v1/points",
        json={
            "points": [{"id": "a", "lat": LAT, "lon": LON}, {"id": "b", "lat": 41.5, "lon": 48.0}]
        },
    ).json()
    assert (body["count"], body["found"]) == (2, 1)
    assert [i["found"] for i in body["items"]] == [True, False]


def test_nearby_is_sorted_and_carries_the_source(client):
    c, _ = client
    body = c.get("/v1/poi/nearby", params={"lat": LAT, "lon": LON, "radius_m": 500}).json()
    assert [i["name"] for i in body["items"]] == ["A"]
    assert body["items"][0]["source"] == "yerli"
    wide = c.get("/v1/poi/nearby", params={"lat": LAT, "lon": LON, "radius_m": 5000}).json()
    assert [i["name"] for i in wide["items"]] == ["A", "Uzaq"]
    assert (
        c.get("/v1/poi/nearby", params={"lat": LAT, "lon": LON, "category": "yox"}).status_code
        == 404
    )


def test_bundle_round_trip_needs_no_raw_data(tmp_path):
    """Bulut sunucusu paketten başlar: ham dosya ve Overpass gerekmez."""
    from urbangeoai import indices

    centre = h3.latlng_to_cell(LAT, LON, 10)
    lat, lon = h3.cell_to_latlng(centre)
    pd.DataFrame(
        [
            {
                "h3_index": centre,
                "latitude": lat,
                "longitude": lon,
                "təhsil_score": 7,
                "təhsil_index": 0.4,
            }
        ]
    ).to_csv(tmp_path / api.BUNDLE_TABLE, index=False)
    model = indices.GroupModel(["kdgr"], [0.0], [1.0], [1.0], 1.0, 0.0, [])
    indices.save_model({"təhsil": model}, tmp_path / api.BUNDLE_MODEL, {"fitted_on": "current"})
    pd.DataFrame(
        [
            {
                "category": "kdgr",
                "name": "Bağça",
                "name_std": "Bağça",
                "lat": LAT,
                "lon": LON,
                "source": "yerli",
            }
        ]
    ).to_csv(tmp_path / api.BUNDLE_POOL, index=False)

    store = api.load_bundle(tmp_path)
    with TestClient(api.create_app(lambda: store)) as c:
        assert c.get("/health").json()["cells"] == 1
        nearby = c.get("/v1/poi/nearby", params={"lat": LAT, "lon": LON, "category": "kdgr"})
        assert nearby.status_code == 200
