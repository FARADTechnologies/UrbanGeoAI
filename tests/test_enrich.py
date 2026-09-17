"""OpenStreetMap zenginleştirmesinin kurallarını sabitler.

Asıl risk sessiz şişmedir: yerelde zaten olan bir yerin OSM kopyası "yeni"
sayılırsa havuz iki kez sayar ve indeks haksız yere yükselir.
"""

from __future__ import annotations

import pandas as pd
from shapely.geometry import box

from urbangeoai import enrich

LAT, LON = 40.3777, 49.8520
METRE = 1 / 111_320  # enlemde yaklaşık bir metre


def local(*rows):
    return pd.DataFrame(rows, columns=["lat", "lon", "name"])


def osm_rows(*rows):
    frame = pd.DataFrame(rows, columns=["category", "name", "lat", "lon"])
    return frame.assign(area_m2=0, osm_type="node", osm_id=range(len(frame)), osm_value="")


def test_classify_uses_the_narrow_tag_mapping():
    assert enrich.classify({"amenity": "cafe"}) == "coffee"
    assert enrich.classify({"shop": "mall"}) == "shopping"
    assert enrich.classify({"shop": "supermarket"}) is None, "market ticarət mərkəzi deyil"
    assert enrich.classify({"amenity": "parking"}) is None


def test_existing_place_is_not_added_again():
    """28 May: A yerlidə var, OSM-də də var → əlavə olunmur."""
    pool = {"coffee": local((LAT, LON, "A"))}
    osm = osm_rows(("coffee", "A", LAT + 10 * METRE, LON))
    added, results = enrich.compare(pool, osm)
    assert added.empty
    row = next(r for r in results if r.category == "coffee")
    assert (row.matched, row.added) == (1, 0)


def test_missing_place_is_added_with_its_source():
    pool = {"coffee": local((LAT, LON, "A"))}
    osm = osm_rows(("coffee", "D", LAT + 500 * METRE, LON))
    added, _ = enrich.compare(pool, osm)
    assert list(added["name"]) == ["D"]
    assert (added["source"] == "osm").all()
    assert added["nearest_local_m"].iloc[0] > enrich.MATCH_RADIUS_M["coffee"]


def test_food_categories_match_each_other():
    """OSM-də kafe olan yer yerli veridə restoran kimi yazılıbsa, iki dəfə sayılmır."""
    pool = {"restaurant": local((LAT, LON, "X"))}
    osm = osm_rows(("coffee", "X", LAT + 5 * METRE, LON))
    added, _ = enrich.compare(pool, osm)
    assert added.empty


def test_osm_duplicates_collapse_to_one():
    osm = osm_rows(("schl", "", LAT, LON), ("schl", "5 saylı məktəb", LAT + 20 * METRE, LON))
    deduped = enrich.dedupe_osm(osm)
    assert len(deduped) == 1
    assert deduped["name"].iloc[0] == "5 saylı məktəb", "adlı olan saxlanmalı"


def test_rules_drop_what_the_local_category_does_not_mean():
    osm = osm_rows(
        ("theatre", "Park Cinema", LAT, LON),
        ("theatre", "Azərbaycan Dövlət Musiqili Teatrı", LAT, LON),
        ("hotel", "", LAT, LON),
        ("parks", "Kiçik bağ", LAT, LON),
    )
    osm.loc[3, "area_m2"] = 500
    kept, rejected = enrich.apply_rules(osm)
    assert list(kept["name"]) == ["Azərbaycan Dövlət Musiqili Teatrı"]
    assert set(rejected["reason"]) == {"adı kateqoriyaya uymur", "adsız", "çox kiçik sahə"}


def test_college_counts_only_when_it_is_higher_education():
    osm = osm_rows(("univ", "Sürücülük Məktəbi", LAT, LON), ("univ", "Tibb Akademiyası", LAT, LON))
    osm["osm_value"] = "college"
    kept, _ = enrich.apply_rules(osm)
    assert list(kept["name"]) == ["Tibb Akademiyası"]


def test_candidates_outside_the_boundary_are_dropped():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": LAT, "lon": LON, "tags": {"amenity": "cafe"}},
            {"type": "node", "id": 2, "lat": 41.5, "lon": 48.0, "tags": {"amenity": "cafe"}},
        ]
    }
    frame = enrich.osm_candidates(payload, box(49.5, 40.2, 50.4, 40.6))
    assert list(frame["osm_id"]) == [1]


def test_area_objects_use_their_bounds():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 7,
                "bounds": {"minlat": 40.0, "minlon": 49.0, "maxlat": 40.001, "maxlon": 49.001},
                "tags": {"leisure": "park", "name": "Bağ"},
            }
        ]
    }
    frame = enrich.osm_candidates(payload)
    assert abs(frame["lat"].iloc[0] - 40.0005) < 1e-9
    assert 7000 < frame["area_m2"].iloc[0] < 10000


def test_merge_keeps_local_rows_and_marks_sources():
    pool = {"coffee": local((LAT, LON, "A")), "bus": local((LAT, LON, "d"))}
    additions = osm_rows(("coffee", "D", LAT + 1, LON)).assign(source="osm")
    merged = enrich.merge(pool, additions)
    assert list(merged["coffee"]["source"]) == ["yerli", "osm"]
    assert list(merged["bus"]["source"]) == ["yerli"]
