"""Bileşik indekslerin üretilmesi ve 1-10 ölçeğine taşınması.

Üç tasarım kararı:

**İşaret sabitlemesi.** Birinci temel bileşenin işareti keyfîdir; kütüphane
onu veriye göre seçer. Yükler negatif çıkarsa indeks tersine döner ve en
erişilebilir hücre en düşük puanı alır. Bu sessizce olur. Burada yüklerin
toplamı negatifse bileşen ters çevrilir.

**Taban kütlesi.** Hücrelerin önemli bir bölümü çevresinde hiç POI bulunmadığı
için aynı en düşük değeri taşır. Eşit değerler aynı dilime düşmek zorunda
olduğundan ``pd.qcut`` fazla dilimleri sessizce siler; on dilim istenirken beş
dilim üretilebilir. Burada taban kütlesi doğrudan birinci banda verilir,
kalan hücreler dokuz dilime bölünür.

**Dondurulmuş model.** Ölçekleyici, yükler ve bant sınırları her çalıştırmada
yeniden öğrenilirse referans çerçevesi kayar: çevresi değişmeyen bir hücrenin
puanı, başka hücreler değiştiği için oynar. Model bir kez uydurulup saklanır,
sonraki veri sürümleri ``score`` ile puanlanır.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

N_BANDS = 10


@dataclass
class GroupModel:
    """Tek bir indeks grubu için uydurulmuş dönüşüm."""

    members: list[str]
    mean: list[float]
    scale: list[float]
    components: list[float]
    explained_variance_ratio: float
    floor: float
    edges: list[float]


def fit_group(frame: pd.DataFrame, members: list[str]) -> GroupModel:
    """Bir grubun skorlarından tek bileşenli indeks modelini uydurur.

    Args:
        frame: ``<üye>_score`` sütunlarını içeren tablo.
        members: Gruba giren kategori adları.

    Returns:
        Ölçekleyici, bileşen ve bant sınırlarını taşıyan model.
    """
    columns = [f"{m}_score" for m in members]
    values = frame[columns].to_numpy()

    scaler = StandardScaler().fit(values)
    pca = PCA(n_components=1).fit(scaler.transform(values))

    component = pca.components_[0]
    # Yüklerin çoğunluğu negatifse bileşeni çevir; yüksek değer daima
    # "daha erişilebilir" anlamına gelsin.
    flip = -1.0 if component.sum() < 0 else 1.0
    component = component * flip

    index = (pca.transform(scaler.transform(values)).ravel()) * flip
    floor, edges = fit_bands(index)

    return GroupModel(
        members=list(members),
        mean=scaler.mean_.tolist(),
        scale=scaler.scale_.tolist(),
        components=component.tolist(),
        explained_variance_ratio=float(pca.explained_variance_ratio_[0]),
        floor=floor,
        edges=edges,
    )


def fit_bands(index: np.ndarray, n_bands: int = N_BANDS) -> tuple[float, list[float]]:
    """Beraberliklere dayanıklı bant sınırları.

    Taban değerindeki hücreler birinci banda ayrılır; geri kalan
    ``n_bands - 1`` eşit dilime bölünür. Böylece bütün bantlar dolar ve en
    yüksek bant gerçekten ``n_bands`` olur.
    """
    series = pd.Series(index, dtype=float)
    floor = float(series.min())
    above = series[series > floor]
    if above.empty:
        return floor, []
    quantiles = np.linspace(0.0, 1.0, n_bands)[1:-1]
    edges = np.unique(np.quantile(above, quantiles))
    return floor, [float(e) for e in edges]


def apply_bands(index: np.ndarray, floor: float, edges: list[float]) -> np.ndarray:
    """Sürekli indeksi 1-10 arası tam sayı banda çevirir."""
    values = np.asarray(index, dtype=float)
    bands = np.searchsorted(np.asarray(edges), values, side="right") + 2
    bands = np.where(values <= floor, 1, bands)
    return np.clip(bands, 1, N_BANDS).astype(np.int8)


def score_group(frame: pd.DataFrame, model: GroupModel) -> tuple[np.ndarray, np.ndarray]:
    """Saklanmış modelle puanlar. Yeniden uydurma yapılmaz.

    Returns:
        (sürekli indeks, 1-10 bandı)
    """
    columns = [f"{m}_score" for m in model.members]
    values = frame[columns].to_numpy()
    standardised = (values - np.asarray(model.mean)) / np.asarray(model.scale)
    index = standardised @ np.asarray(model.components)
    return index, apply_bands(index, model.floor, model.edges)


def save_model(models: dict[str, GroupModel], path: Path, metadata: dict | None = None) -> None:
    """Modeli okunabilir JSON olarak yazar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata or {},
        "groups": {name: asdict(m) for name, m in models.items()},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_model(path: Path) -> dict[str, GroupModel]:
    """Saklanmış modeli okur."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {name: GroupModel(**spec) for name, spec in payload["groups"].items()}
