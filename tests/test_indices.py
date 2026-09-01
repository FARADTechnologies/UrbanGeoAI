"""İndeks bantlama ve işaret sabitlemesinin davranışını sabitleyen testler."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from urbangeoai import indices


def _skewed_index(n: int = 1000, floor_share: float = 0.4, seed: int = 0) -> np.ndarray:
    """Gerçek veriye benzeyen dağılım: büyük bir taban kütlesi ve sağa çarpık kuyruk."""
    rng = np.random.default_rng(seed)
    n_floor = int(n * floor_share)
    return np.concatenate([np.zeros(n_floor), rng.exponential(scale=2.0, size=n - n_floor) + 1e-6])


def test_bands_span_full_range_despite_tied_floor():
    """Asıl kusur: pd.qcut beraberlikler yüzünden ona ulaşamıyordu."""
    index = _skewed_index(floor_share=0.5)
    floor, edges = indices.fit_bands(index)
    bands = indices.apply_bands(index, floor, edges)

    assert bands.min() == 1
    assert bands.max() == indices.N_BANDS
    assert len(np.unique(bands)) == indices.N_BANDS


def test_qcut_would_lose_bands_on_the_same_input():
    """Önceki yöntemin neden yetersiz olduğunu belgeler."""
    index = pd.Series(_skewed_index(floor_share=0.5))
    legacy = pd.qcut(index, 10, labels=False, duplicates="drop") + 1
    assert legacy.max() < indices.N_BANDS


def test_floor_mass_lands_in_band_one():
    index = _skewed_index(floor_share=0.3)
    floor, edges = indices.fit_bands(index)
    bands = indices.apply_bands(index, floor, edges)
    assert (bands[index == 0.0] == 1).all()


def test_constant_input_collapses_to_band_one():
    """Bütün değerler eşitse taban dışında bant yoktur."""
    index = np.zeros(50)
    floor, edges = indices.fit_bands(index)
    assert edges == []
    assert (indices.apply_bands(index, floor, edges) == 1).all()


def _frame(seed: int = 0, n: int = 400) -> pd.DataFrame:
    """Birlikte artan iki kategori skoru."""
    rng = np.random.default_rng(seed)
    base = rng.exponential(scale=1.0, size=n)
    return pd.DataFrame(
        {"a_score": base + rng.normal(0, 0.1, n), "b_score": base + rng.normal(0, 0.1, n)}
    )


def test_loadings_are_positive_after_sign_pinning():
    """Yüksek indeks daima 'daha erişilebilir' anlamına gelmeli."""
    model = indices.fit_group(_frame(), ["a", "b"])
    assert all(c > 0 for c in model.components)


def test_sign_pinning_is_stable_across_seeds():
    """İşaret veriye göre değişmemeli."""
    for seed in range(8):
        model = indices.fit_group(_frame(seed=seed), ["a", "b"])
        assert sum(model.components) > 0


def test_higher_input_yields_higher_index():
    frame = _frame()
    model = indices.fit_group(frame, ["a", "b"])
    index, _ = indices.score_group(frame, model)
    ranked = frame["a_score"].to_numpy()
    assert np.corrcoef(index, ranked)[0, 1] > 0.8


def test_score_group_reuses_saved_model(tmp_path):
    """Kaydedilen modelle puanlama, uydurma sırasındaki sonucu tekrar üretmeli."""
    frame = _frame()
    model = indices.fit_group(frame, ["a", "b"])
    indices.save_model({"g": model}, tmp_path / "m.json")
    restored = indices.load_model(tmp_path / "m.json")["g"]

    a, _ = indices.score_group(frame, model)
    b, _ = indices.score_group(frame, restored)
    np.testing.assert_allclose(a, b)


def test_frozen_model_does_not_shift_when_new_data_arrives():
    """Dondurulmuş model, referans çerçevesinin kaymasını engellemeli.

    Aynı satırlar yeni bir veri kümesinin içinde de aynı bandı almalı.
    """
    baseline = _frame(seed=1, n=400)
    model = indices.fit_group(baseline, ["a", "b"])
    _, bands_before = indices.score_group(baseline, model)

    extended = pd.concat([baseline, _frame(seed=2, n=200)], ignore_index=True)
    _, bands_after = indices.score_group(extended, model)

    np.testing.assert_array_equal(bands_before, bands_after[: len(baseline)])


def test_refitting_does_shift_bands():
    """Karşıt durum: yeniden uydurma aynı satırların bandını değiştirebilir."""
    baseline = _frame(seed=1, n=400)
    before = indices.score_group(baseline, indices.fit_group(baseline, ["a", "b"]))[1]

    extended = pd.concat([baseline, _frame(seed=3, n=400)], ignore_index=True)
    refit = indices.fit_group(extended, ["a", "b"])
    after = indices.score_group(extended, refit)[1][: len(baseline)]

    assert not np.array_equal(before, after)


def test_explained_variance_is_reported():
    model = indices.fit_group(_frame(), ["a", "b"])
    assert 0.0 < model.explained_variance_ratio <= 1.0


def test_bands_are_clipped_for_out_of_range_input():
    """Modelin görmediği uç değerler bandı taşırmamalı."""
    model_index = _skewed_index()
    floor, edges = indices.fit_bands(model_index)
    extreme = np.array([-1e6, 1e6])
    bands = indices.apply_bands(extreme, floor, edges)
    assert bands.tolist() == [1, indices.N_BANDS]


@pytest.mark.parametrize("n_bands", [4, 10, 20])
def test_band_count_is_configurable(n_bands):
    index = _skewed_index(floor_share=0.2)
    floor, edges = indices.fit_bands(index, n_bands=n_bands)
    assert len(edges) <= n_bands - 1
