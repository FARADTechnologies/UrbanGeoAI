"""Ortak yükleme adımlarının testleri."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from urbangeoai import indices, pipeline


def test_original_loadings_match_the_team_notebook():
    """Panelde görünen yük, ekibin notebook'undaki tanımla aynı olmalı."""
    rng = np.random.default_rng(0)
    base = rng.normal(size=5000)
    frame = pd.DataFrame(
        {
            "a_score": base + rng.normal(scale=0.3, size=5000),
            "b_score": base + rng.normal(scale=0.5, size=5000),
            "c_score": base + rng.normal(scale=0.8, size=5000),
        }
    )
    model = indices.fit_group(frame, ["a", "b", "c"])

    # Notebook'taki satırlar birebir:
    scaled = StandardScaler().fit_transform(frame)
    pca = PCA(n_components=1).fit(scaled)
    notebook = (pca.components_.T * np.sqrt(pca.explained_variance_)).ravel()
    notebook = notebook * np.sign(notebook.sum())

    assert np.allclose(pipeline.original_loadings(model), notebook, atol=1e-3)


def test_pool_marks_the_source_of_every_row(tmp_path):
    (tmp_path / "kafe.csv").write_text("id,name,lat,lon\n1,A,40.1,49.1\n", encoding="utf-8")
    metro_frame = pd.DataFrame({"name": ["M"], "lat": [40.2], "lon": [49.2]})
    additions = pd.DataFrame(
        {"category": ["coffee"], "name": ["D"], "lat": [40.3], "lon": [49.3], "source": ["osm"]}
    )
    pool = pipeline.load_pool(tmp_path, {"coffee": ("kafe.csv", None)}, metro_frame, additions)
    assert list(pool["coffee"]["source"]) == ["yerli", "osm"]
    assert list(pool["metro"]["source"]) == ["metro"]
