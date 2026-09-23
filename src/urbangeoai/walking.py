"""Yol ağı üzerinden yürüme mesafesiyle erişilebilirlik skoru.

Kuş uçuşu skorla aynı formül — ``Σ exp(−β × dakika)``, 80 m/dk, 3 km sınırı —
ama mesafe düz çizgi değil, OpenStreetMap'teki yürünebilir yollar üzerinden
en kısa yol. Böylece dəmiryolunun, çevrə yolunun ya da dənizin öbür
tarafındaki bir okul, kuş uçuşu yakın olsa bile uzak sayılır.

Yöntem:

1. Yürünebilir yollar (otoyol ve özel yollar hariç) bir çizgeye çevrilir;
   kenar uzunluğu iki düğüm arasındaki gerçek mesafedir. Yalnız en büyük
   bağlı parça tutulur — ada gibi kopuk parçalara hiçbir yerden gidilemez.
2. Her hücre merkezi ve her obje en yakın yol düğümüne bağlanır; bu bağlantı
   mesafesi de yürüyüşe eklenir.
3. Her obje düğümünden 3 km sınırlı Dijkstra çalıştırılır; her hücre düğümüne
   varış mesafesi ağırlığa çevrilip toplanır.

Aynı düğüme bağlanan objeler tek Dijkstra paylaşır; ağırlıkları kendi
bağlantı mesafeleriyle toplanır. Bu, 3 km sınırını obje bazında değil düğüm
bazında uygular — fark birkaç metrelik bağlantı payıdır.

Veri OpenStreetMap katkıcılarına aittir ve ODbL ile lisanslanmıştır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

METERS_PER_MINUTE = 80.0
CUTOFF_M = 3000.0

#: Yürünemeyen yol tipleri. Overpass sorgusu da bunları dışarıda bırakır.
EXCLUDED_HIGHWAYS = (
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "construction",
    "proposed",
    "raceway",
    "bus_guideway",
)

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32639", always_xy=True)


def walk_query(south: float, west: float, north: float, east: float, timeout_s: int = 300) -> str:
    """Bir kutudaki yürünebilir yolları çeken Overpass sorgusu."""
    excluded = "|".join(EXCLUDED_HIGHWAYS)
    return (
        f"[out:json][timeout:{timeout_s}];"
        f'way["highway"]["highway"!~"^({excluded})$"]'
        '["foot"!~"^(no)$"]["access"!~"^(private|no)$"]["area"!="yes"]'
        f"({south},{west},{north},{east});(._;>;);out skel qt;"
    )


def utm(lat, lon) -> np.ndarray:
    x, y = _TO_UTM.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.column_stack([x, y])


@dataclass
class WalkGraph:
    """Yürüme ağı: düğüm koordinatları (UTM, metre) ve kenar matrisi."""

    xy: np.ndarray
    matrix: object  # scipy.sparse.csr_matrix
    tree: cKDTree

    @property
    def nodes(self) -> int:
        return len(self.xy)

    def snap(self, lat, lon) -> tuple[np.ndarray, np.ndarray]:
        """Noktaları en yakın düğüme bağlar: (düğüm sırası, bağlantı metresi)."""
        dist, node = self.tree.query(utm(lat, lon), k=1)
        return node, dist


def build_graph(payloads: list[dict]) -> WalkGraph:
    """Overpass yanıtlarından (parçalar halinde olabilir) yürüme ağı kurar."""
    coords: dict[int, tuple[float, float]] = {}
    ways: dict[int, list[int]] = {}
    for payload in payloads:
        for e in payload.get("elements", []):
            if e["type"] == "node":
                coords[e["id"]] = (e["lat"], e["lon"])
            elif e["type"] == "way":
                ways[e["id"]] = e.get("nodes", [])

    ids = np.fromiter(coords.keys(), dtype=np.int64)
    position = {osm_id: i for i, osm_id in enumerate(ids)}
    latlon = np.array([coords[i] for i in ids])
    xy = utm(latlon[:, 0], latlon[:, 1])

    a, b = [], []
    for refs in ways.values():
        idx = [position[r] for r in refs if r in position]
        a.extend(idx[:-1])
        b.extend(idx[1:])
    a, b = np.asarray(a), np.asarray(b)
    length = np.hypot(*(xy[a] - xy[b]).T)
    n = len(xy)
    matrix = coo_matrix(
        (np.concatenate([length, length]), (np.concatenate([a, b]), np.concatenate([b, a]))),
        shape=(n, n),
    ).tocsr()

    # Yalnız en büyük bağlı parça: kopuk parçalara hiçbir yerden gidilemez.
    _, labels = connected_components(matrix, directed=False)
    keep = labels == np.bincount(labels).argmax()
    matrix = matrix[keep][:, keep]
    xy = xy[keep]
    return WalkGraph(xy=xy, matrix=matrix, tree=cKDTree(xy))


def load_graph(tile_dir: Path) -> WalkGraph:
    payloads = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(tile_dir).glob("*.json"))
    ]
    return build_graph(payloads)


def walking_score(
    graph: WalkGraph,
    cell_node: np.ndarray,
    cell_snap: np.ndarray,
    poi: pd.DataFrame,
    beta: float,
    cutoff_m: float = CUTOFF_M,
    chunk: int = 64,
) -> np.ndarray:
    """Her hücre için yol ağı üzerinden ``Σ exp(−β × dakika)``."""
    scores = np.zeros(len(cell_node))
    if poi.empty:
        return scores
    factor = beta / METERS_PER_MINUTE
    node, snap = graph.snap(poi["lat"], poi["lon"])
    # Aynı düğümdeki objelerin bağlantı ağırlıkları toplanır.
    weights = pd.Series(np.exp(-factor * snap)).groupby(node).sum()
    sources = weights.index.to_numpy()
    source_weight = weights.to_numpy()

    for start in range(0, len(sources), chunk):
        block = sources[start : start + chunk]
        dist = dijkstra(graph.matrix, directed=False, indices=block, limit=cutoff_m)
        total = dist[:, cell_node] + cell_snap[None, :]
        reach = np.isfinite(total) & (total <= cutoff_m)
        contrib = np.where(reach, np.exp(-factor * np.where(reach, total, 0.0)), 0.0)
        scores += (contrib * source_weight[start : start + chunk, None]).sum(axis=0)
    return scores
