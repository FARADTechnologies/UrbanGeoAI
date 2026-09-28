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


#: İndeks bantlanmadan önce bu kadar ondalığa yuvarlanır.
INDEX_DECIMALS = 10


def compute_index(values, mean, scale, components) -> np.ndarray:
    """Standartlaştırılmış skorların bileşen ağırlıklı toplamı.

    Sonuç ``INDEX_DECIMALS`` ondalığa yuvarlanır. Matris çarpımı özdeş iki
    satıra son basamakta farklı sonuç verebiliyor (satırın bellekteki yerine
    göre ~1e-16). Bant tabanı eşitlikle karşılaştırıldığı için bu gürültü
    "3 km'de hiç nesne yok" hücrelerinin bir kısmını tabandan kaçırıyor, bant
    1'i boşaltıp ara bantları kaydırıyordu (turizmdə 32 924 hücrenin yalnız
    5'i tabanda kalmıştı). Yuvarlama anlamlı farkların çok altında; eşit
    erişilebilirlik yeniden eşit indeks verir.
    """
    standardised = (np.asarray(values, float) - np.asarray(mean)) / np.asarray(scale)
    return np.round(standardised @ np.asarray(components), INDEX_DECIMALS)


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

    # Bant sınırları score_group'la birebir aynı hesaptan çıkarılmalı (bkz.
    # compute_index).
    index = compute_index(values, scaler.mean_, scaler.scale_, component)
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

    İki kural birbiriyle çelişir ve ikisi birden garanti edilemez:

    1. Eşit indeks eşit bal almalı. Aynı erişilebilirliğe sahip iki nöqtəyə
       farklı puan vermek savunulamaz.
    2. On bandın hepsi dolmalı.

    Bir değerin kütlesi ``1/n_bands``'ten büyükse ikisi aynı anda mümkün
    değildir: o kütle bölünemez. Birinci kural korunur, ikincisinden ödün
    verilir. Sonuçta bazı bantlar boş kalabilir; boş bant, altındaki değerde
    büyük bir yığılma olduğunu gösteren gerçek bir bilgidir.

    Uç noktalar her durumda garantilidir: en düşük değer 1, en yüksek değer
    ``n_bands`` alır. ``apply_bands`` ara bantları buna göre gerer.

    Returns:
        (taban değeri, kesim noktaları)
    """
    series = pd.Series(index, dtype=float)
    floor = float(series.min())
    above = series[series > floor]
    if above.empty:
        return floor, []
    quantiles = np.linspace(0.0, 1.0, n_bands)[1:-1]
    # Beraberlikler bazı kesim noktalarını üst üste düşürür; tekrarları
    # atmak zorundayız, yoksa aynı değer iki farklı banda düşerdi.
    edges = np.unique(np.quantile(above, quantiles))
    return floor, [float(e) for e in edges]


def apply_bands(index: np.ndarray, floor: float, edges: list[float]) -> np.ndarray:
    """Sürekli indeksi 1..``N_BANDS`` arası tam sayı banda çevirir.

    Beraberlikler yüzünden kesim noktası sayısı beklenenden az olabilir. Bu
    durumda bantlar gerilerek en yüksek değerin daima ``N_BANDS`` almasını
    sağlar; aradaki bazı bantlar boş kalır.
    """
    values = np.asarray(index, dtype=float)
    cuts = np.asarray(edges, dtype=float)

    if cuts.size == 0:
        return np.where(values <= floor, 1, N_BANDS).astype(np.int8)

    raw = np.searchsorted(cuts, values, side="right")  # 0 .. cuts.size
    if cuts.size == N_BANDS - 2:
        # Beklenen sayıda kesim: taban bandı ayrı, kalanlar sırayla.
        bands = raw + 2
    else:
        # Kesim noktası eksik. Uç noktalar korunacak biçimde ger.
        bands = 2 + np.rint(raw / cuts.size * (N_BANDS - 2))
    bands = np.where(values <= floor, 1, bands)
    return np.clip(bands, 1, N_BANDS).astype(np.int8)


def band_coverage(bands: np.ndarray, n_bands: int = N_BANDS) -> dict[int, int]:
    """Bant başına hücre sayısı. Boş bantlar sıfır olarak görünür.

    Boş bant bir hata değil ama gözden kaçmamalı: altındaki değerde büyük bir
    yığılma olduğunu, yani bal ölçeğinin o aralıkta ayrım yapamadığını söyler.
    """
    counts = pd.Series(bands).value_counts()
    return {b: int(counts.get(b, 0)) for b in range(1, n_bands + 1)}


def score_group(frame: pd.DataFrame, model: GroupModel) -> tuple[np.ndarray, np.ndarray]:
    """Saklanmış modelle puanlar. Yeniden uydurma yapılmaz.

    Returns:
        (sürekli indeks, 1-10 bandı)
    """
    columns = [f"{m}_score" for m in model.members]
    values = frame[columns].to_numpy()
    index = compute_index(values, model.mean, model.scale, model.components)
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
