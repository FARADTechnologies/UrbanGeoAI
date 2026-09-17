"""Betiklerin paylaştığı yükleme adımları.

Her betik havuzu aynı şekilde kursun diye tek yerde: yerel dosyalar, metro ve
— varsa — OpenStreetMap eklemeleri. Bir betik eklemeleri unutursa panelde
görünen sayı ile teslim edilen tablo ayrışırdı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from urbangeoai import catalogue, enrich, io, metro, osm, scoring

#: ``scripts/enrich_osm.py``'nin yazdığı ek dosyanın adı (çıktı dizininde).
ADDITIONS_FILE = "osm_additions.csv"


def additions_path(settings) -> Path:
    return settings.paths.output / ADDITIONS_FILE


def load_additions(settings) -> pd.DataFrame | None:
    """OSM eklemelerini okur; dosya yoksa None."""
    path = additions_path(settings)
    if not path.exists():
        return None
    return pd.read_csv(path, encoding="utf-8", keep_default_na=False)


def load_local(base: Path, sources: dict, quiet: bool = False) -> dict[str, pd.DataFrame]:
    """Kaynak tablosundaki kategorileri yükler (metro hariç)."""
    out: dict[str, pd.DataFrame] = {}
    for name, (fname, typ) in sources.items():
        path = base / fname
        if not path.exists():
            if not quiet:
                print(f"  atlandı (dosya yok): {fname}", file=sys.stderr)
            continue
        frame = io.read_poi(path).frame
        out[name] = io.filter_type(frame, typ) if typ else frame
    return out


def load_metro(settings) -> metro.MetroReport:
    """Metro istasyonlarını OSM'den çeker ve ekip listeleriyle ayıklar."""
    client = osm.OverpassClient(
        cache_dir=settings.paths.cache,
        mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
    )
    payload = client.query(osm.metro_query(settings.bbox), "metro_raw")
    return metro.deduplicate_with_config(osm.nodes_to_records(payload), settings.metro)


def load_pool(
    base: Path,
    sources: dict,
    metro_frame: pd.DataFrame,
    additions: pd.DataFrame | None = None,
    quiet: bool = False,
) -> dict[str, pd.DataFrame]:
    """Bir veri sürümünün tam havuzu: yerel + metro (+ OSM eklemeleri).

    Her satır ``source`` sütunu taşır: ``yerli``, ``osm`` ya da ``metro``.
    """
    pool = load_local(base, sources, quiet=quiet)
    if additions is not None:
        pool = enrich.merge(pool, additions)
    else:
        pool = {k: v.assign(source="yerli") for k, v in pool.items()}
    pool["metro"] = metro_frame.assign(source="metro")
    return pool


def category_scores(cells: pd.DataFrame, pool: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Her kategori için mesafeye göre azalan skor sütunları."""
    return pd.DataFrame(
        {
            f"{name}_score": scoring.decay_score(cells, frame, catalogue.DECAY[name])
            for name, frame in pool.items()
        },
        index=cells.index,
    )


def original_loadings(model) -> list[float]:
    """Yükleri ekibin notebook'undaki tanımla verir.

    Notebook ``pca.components_.T * np.sqrt(pca.explained_variance_)`` yazdırır:
    bileşen ağırlığı × özdeğerin karekökü. Standartlaştırılmış veride bu değer,
    kategori skoru ile indeks arasındaki korelasyona eşittir. Model ise ham
    ağırlığı (birim vektör) saklar; puanlama onunla yapılır.
    """
    members = len(model.members)
    eigenvalue = model.explained_variance_ratio * members
    return [round(float(c) * float(np.sqrt(eigenvalue)), 3) for c in model.components]
