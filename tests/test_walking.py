"""Yol ağı üzerinden yürüme skorunun testleri — sentetik küçük ağla."""

from __future__ import annotations

import numpy as np
import pandas as pd

from urbangeoai import walking

LAT0, LON0 = 40.40, 49.85
M_LAT = 1 / 111_320  # enlemde bir metre


def node(i, lat, lon):
    return {"type": "node", "id": i, "lat": lat, "lon": lon}


def street(n=31, step_m=100.0):
    """Kuzeye giden 3 km'lik düz bir sokak: 31 düğüm, 100 m arayla."""
    nodes = [node(i, LAT0 + i * step_m * M_LAT, LON0) for i in range(n)]
    way = {"type": "way", "id": 1, "nodes": list(range(n))}
    return {"elements": [*nodes, way]}


def test_graph_keeps_only_the_largest_component():
    payload = street()
    payload["elements"] += [
        node(100, LAT0, LON0 + 0.05),
        node(101, LAT0 + 0.001, LON0 + 0.05),
        {"type": "way", "id": 2, "nodes": [100, 101]},
    ]
    graph = walking.build_graph([payload])
    assert graph.nodes == 31


def test_edge_length_is_real_distance():
    graph = walking.build_graph([street()])
    assert np.allclose(graph.matrix.data, 100.0, atol=1.0)


def test_score_uses_path_length_plus_snap():
    graph = walking.build_graph([street()])
    cell_node, cell_snap = graph.snap([LAT0], [LON0])
    poi = pd.DataFrame({"lat": [LAT0 + 1000 * M_LAT], "lon": [LON0], "name": ["okul"]})
    score = walking.walking_score(graph, cell_node, cell_snap, poi, beta=0.2)
    assert np.isclose(score[0], np.exp(-0.2 * 1000 / 80), rtol=0.02)


def test_detour_makes_score_lower_than_crow_flies():
    """Obje kuş uçuşu 200 m ötede ama yol 3 km dolaşıyor → skor çok düşük."""
    payload = street()
    # Sokağın başından 200 m doğuya, yalnız sokağın ucuna bağlı bir yan yol.
    east = LON0 + 200 / (111_320 * np.cos(np.radians(LAT0)))
    payload["elements"] += [
        node(200, LAT0, east),
        node(201, LAT0 + 3000 * M_LAT, east),
        {"type": "way", "id": 3, "nodes": [30, 201, 200]},
    ]
    graph = walking.build_graph([payload])
    cell_node, cell_snap = graph.snap([LAT0], [LON0])
    poi = pd.DataFrame({"lat": [LAT0], "lon": [east], "name": ["okul"]})
    walk = walking.walking_score(graph, cell_node, cell_snap, poi, beta=0.2)[0]
    crow = np.exp(-0.2 * 200 / 80)
    assert walk < crow / 100


def test_objects_beyond_the_cutoff_do_not_count():
    graph = walking.build_graph([street()])
    cell_node, cell_snap = graph.snap([LAT0], [LON0])
    far = pd.DataFrame({"lat": [LAT0 + 3000 * M_LAT], "lon": [LON0], "name": ["x"]})
    assert walking.walking_score(graph, cell_node, cell_snap, far, beta=0.1, cutoff_m=2000)[0] == 0


def test_query_excludes_motorways():
    q = walking.walk_query(40.2, 49.5, 40.6, 50.4)
    assert "motorway" in q and '["highway"!~' in q
