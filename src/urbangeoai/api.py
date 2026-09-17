"""Əlçatanlıq indekslərini başqa sistemlərə açan HTTP API.

Platform, qiymətləndirmə modeli ya da bir bankın sistemi bu uçlarla bir
nöqtənin, bir H3 hüceyrəsinin ya da bir ünvan siyahısının ballarını ala
bilir. Veri teslim cədvəlindən gəlir; API heç nə yenidən hesablamır, yalnız
oxuyur. Beləliklə API-nin qaytardığı rəqəm ilə cədvəldəki rəqəm ayrışa
bilməz.

Səviyyələr: hesablama H10-da aparılır. H6–H9 üçün sorğu gələndə o hüceyrənin
içindəki H10 hüceyrələrinin ortalaması qaytarılır və neçə hüceyrədən
ortalandığı da yazılır.

İşə salmaq:
    python scripts/serve_api.py
    → http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import math
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import h3
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0
BASE_RESOLUTION = 10
PARENT_RESOLUTIONS = (6, 7, 8, 9)
MAX_BATCH = 1000
MAX_RADIUS_M = 5000


@dataclass
class Store:
    """API-nin oxuduğu hər şey, yaddaşda."""

    table: pd.DataFrame
    groups: list[str]
    meta: dict = field(default_factory=dict)
    pool: dict[str, pd.DataFrame] = field(default_factory=dict)
    trees: dict[str, BallTree] = field(default_factory=dict)
    parents: dict[int, pd.Series] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        table: pd.DataFrame,
        groups: list[str],
        meta: dict | None = None,
        pool: dict[str, pd.DataFrame] | None = None,
    ) -> Store:
        table = table.set_index("h3_index", drop=False)
        parents = {}
        for r in PARENT_RESOLUTIONS:
            column = f"h3_res{r}"
            parents[r] = (
                table[column]
                if column in table.columns
                else table["h3_index"].map(lambda c, r=r: h3.cell_to_parent(c, r))
            )
        pool = {k: v.reset_index(drop=True) for k, v in (pool or {}).items() if len(v)}
        trees = {
            k: BallTree(np.radians(v[["lat", "lon"]].to_numpy()), metric="haversine")
            for k, v in pool.items()
        }
        return cls(table, list(groups), meta or {}, pool, trees, parents)

    @property
    def distance_columns(self) -> list[str]:
        return [c for c in self.table.columns if c.startswith("distance_to_")]


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float | np.floating):
        return None if math.isnan(value) else round(float(value), 4)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _row_payload(store: Store, row: pd.Series) -> dict:
    return {
        "h3_index": row["h3_index"],
        "resolution": BASE_RESOLUTION,
        "cells": 1,
        "center": {"lat": _clean(row["latitude"]), "lon": _clean(row["longitude"])},
        "scores": {g: _clean(row[f"{g}_score"]) for g in store.groups},
        "indices": {g: _clean(row[f"{g}_index"]) for g in store.groups},
        "distances_m": {
            c.removeprefix("distance_to_").removesuffix("_m"): _clean(row[c])
            for c in store.distance_columns
        },
        "parents": {
            f"h3_res{r}": store.parents[r].loc[row["h3_index"]] for r in PARENT_RESOLUTIONS
        },
    }


def _aggregate_payload(store: Store, cell: str, resolution: int) -> dict:
    rows = store.table[store.parents[resolution] == cell]
    if rows.empty:
        raise HTTPException(404, f"{cell} analiz sahəsindən kənardadır")
    lat, lon = h3.cell_to_latlng(cell)
    return {
        "h3_index": cell,
        "resolution": resolution,
        "cells": int(len(rows)),
        "aggregation": "H10 hüceyrələrinin ortalaması",
        "center": {"lat": round(lat, 6), "lon": round(lon, 6)},
        "scores": {g: _clean(rows[f"{g}_score"].mean()) for g in store.groups},
        "indices": {g: _clean(rows[f"{g}_index"].mean()) for g in store.groups},
        "distances_m": {
            c.removeprefix("distance_to_").removesuffix("_m"): _clean(rows[c].mean())
            for c in store.distance_columns
        },
    }


def _cell_payload(store: Store, cell: str) -> dict:
    if not h3.is_valid_cell(cell):
        raise HTTPException(400, f"'{cell}' etibarlı H3 indeksi deyil")
    resolution = h3.get_resolution(cell)
    if resolution == BASE_RESOLUTION:
        if cell not in store.table.index:
            raise HTTPException(404, f"{cell} analiz sahəsindən kənardadır")
        return _row_payload(store, store.table.loc[cell])
    if resolution in PARENT_RESOLUTIONS:
        return _aggregate_payload(store, cell, resolution)
    raise HTTPException(
        400, f"H{resolution} dəstəklənmir; H{min(PARENT_RESOLUTIONS)}–H{BASE_RESOLUTION} olmalıdır"
    )


class Point(BaseModel):
    id: str | None = Field(default=None, description="Çağıranın öz identifikatoru")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class PointBatch(BaseModel):
    points: list[Point] = Field(min_length=1, max_length=MAX_BATCH)


DEFAULT_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def create_app(
    load: Callable[[], Store], allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
) -> FastAPI:
    """Tətbiqi qurur. ``load`` başlanğıcda bir dəfə çağırılır."""
    state: dict[str, Store] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["store"] = load()
        yield
        state.clear()

    app = FastAPI(
        title="UrbanGeoAI API",
        version="1.0.0",
        description=(
            "Bakı və Abşeron üçün H3 əlçatanlıq indeksləri. Hesablama H10-da aparılır; "
            "H6–H9 sorğuları H10 ballarının ortalamasını qaytarır."
        ),
        lifespan=lifespan,
    )
    # Panel başqa portdan (3000) çağırır; yalnız oxuma icazəsi verilir.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def store() -> Store:
        return state["store"]

    @app.get("/health", tags=["sistem"])
    def health() -> dict:
        """Xidmətin işlədiyini və neçə hüceyrə yüklədiyini göstərir."""
        return {"status": "ok", "cells": int(len(store().table))}

    @app.get("/v1/meta", tags=["sistem"])
    def meta() -> dict:
        """Model, veri sürümü və mövcud indekslər."""
        s = store()
        return {
            "resolution": BASE_RESOLUTION,
            "supported_resolutions": [BASE_RESOLUTION, *sorted(PARENT_RESOLUTIONS, reverse=True)],
            "cells": int(len(s.table)),
            "indices": s.groups,
            "score_range": [1, 10],
            "poi_categories": {k: int(len(v)) for k, v in s.pool.items()},
            **s.meta,
        }

    @app.get("/v1/cells/{h3_index}", tags=["indekslər"])
    def cell(h3_index: str) -> dict:
        """Bir H3 hüceyrəsinin balları. H10 birbaşa, H6–H9 ortalama."""
        return _cell_payload(store(), h3_index)

    @app.get("/v1/point", tags=["indekslər"])
    def point(
        lat: float = Query(ge=-90, le=90, description="Enlik"),
        lon: float = Query(ge=-180, le=180, description="Uzunluq"),
    ) -> dict:
        """Koordinatın düşdüyü H10 hüceyrəsinin balları."""
        cell_id = h3.latlng_to_cell(lat, lon, BASE_RESOLUTION)
        return {"query": {"lat": lat, "lon": lon}, **_cell_payload(store(), cell_id)}

    @app.post("/v1/points", tags=["indekslər"])
    def points(batch: PointBatch) -> dict:
        """Bir neçə nöqtə birdən (ən çox 1000). Sahədən kənar nöqtə xəta vermir."""
        s = store()
        items = []
        for p in batch.points:
            cell_id = h3.latlng_to_cell(p.lat, p.lon, BASE_RESOLUTION)
            if cell_id in s.table.index:
                items.append({"id": p.id, "found": True, **_row_payload(s, s.table.loc[cell_id])})
            else:
                items.append({"id": p.id, "found": False, "h3_index": cell_id})
        return {"count": len(items), "found": sum(i["found"] for i in items), "items": items}

    @app.get("/v1/poi/nearby", tags=["obyektlər"])
    def nearby(
        lat: float = Query(ge=-90, le=90),
        lon: float = Query(ge=-180, le=180),
        radius_m: float = Query(1000, gt=0, le=MAX_RADIUS_M),
        category: str | None = Query(None, description="Boş qalsa bütün kateqoriyalar"),
        limit: int = Query(50, ge=1, le=500),
    ) -> dict:
        """Nöqtənin ətrafındakı obyektlər, məsafəyə görə sıralı. Mənbə də yazılır."""
        s = store()
        if category is not None and category not in s.trees:
            raise HTTPException(404, f"'{category}' kateqoriyası yoxdur")
        names = [category] if category else list(s.trees)
        origin = np.radians([[lat, lon]])
        found = []
        for name in names:
            idx, dist = s.trees[name].query_radius(
                origin, r=radius_m / EARTH_RADIUS_M, return_distance=True
            )
            frame = s.pool[name]
            for i, d in zip(idx[0], dist[0], strict=True):
                row = frame.iloc[int(i)]
                found.append(
                    {
                        "category": name,
                        "name": str(row.get("name", "") or ""),
                        "lat": round(float(row["lat"]), 6),
                        "lon": round(float(row["lon"]), 6),
                        "distance_m": round(float(d) * EARTH_RADIUS_M, 1),
                        "source": str(row.get("source", "yerli")),
                    }
                )
        found.sort(key=lambda x: x["distance_m"])
        return {"count": len(found), "items": found[:limit]}

    return app


def load_store(settings) -> Store:
    """Teslim cədvəlini, modeli və POI hovuzunu diskdən oxuyur."""
    import json  # noqa: PLC0415

    from urbangeoai import catalogue, indices, pipeline  # noqa: PLC0415

    output = settings.paths.output
    table = pd.read_csv(output / "accessibility_indices.csv", encoding="utf-8")
    model_path = output / "index_model.json"
    groups = list(indices.load_model(model_path))
    meta = json.loads(model_path.read_text(encoding="utf-8")).get("metadata", {})
    pool = pipeline.load_pool(
        settings.paths.raw_current,
        catalogue.SOURCES,
        pipeline.load_metro(settings).frame(),
        pipeline.load_additions(settings),
        quiet=True,
    )
    return Store.build(table, groups, {"model": meta}, pool)
