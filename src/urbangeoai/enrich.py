"""İş ortağının POI havuzunu OpenStreetMap ile tamamlar.

Amaç yerel veriyi değiştirmek değil, **eksiğini kapatmak**. 28 May'da yerel
veri A, B, C kafelerini biliyor, OpenStreetMap ek olarak D ve E'yi de
biliyorsa; D ve E ayrılıp havuza eklenir, A, B, C'nin OSM kopyaları atılır.

Üç karar:

**Etiket eşlemesi dar tutuldu.** OSM ile yerel veri aynı şeyi ölçmüyor:
ticarət mərkəzi için ``shop=*`` alınsaydı marketler ve depolar da gelirdi.
Her kategori yalnız kendi karşılığı olan etiketlerle çekilir.

**Eşleştirme mesafeye dayanıyor.** Yerel dosyaların çoğunda gerçek isim yok,
isim karşılaştırması güvenilmez. Bir OSM nesnesinin yakınında (kategoriye
özgü yarıçap) yerel bir kayıt varsa "zaten var" sayılır. Yarıçaplar nesnenin
fiziksel büyüklüğünü izler: kafe için 30 m, park için 250 m.

**Şüphede eklenmez.** Yiyecek kategorileri birbirine karşı eşleşir — OSM'de
kafe olan bir yer yerel veride restoran diye kayıtlıysa yine "var" sayılır.
Bağça ile məktəb de ortak havuzda. Böylece aynı yer iki kez sayılmaz; bedeli,
gerçekten yeni olan birkaç nesnenin kaçabilmesi.

Veri OpenStreetMap katkıcılarına aittir ve ODbL ile lisanslanmıştır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import shapely
from sklearn.neighbors import BallTree

from urbangeoai import dedupe
from urbangeoai.metro import normalise_name

EARTH_RADIUS_M = 6_371_000.0

#: Kategori → (OSM anahtarı, kabul edilen değerler). Sıra önemli: bir nesne
#: birden fazla etikete uyuyorsa ilk eşleşen kazanır.
OSM_TAGS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("kdgr", "amenity", frozenset({"kindergarten"})),
    ("schl", "amenity", frozenset({"school"})),
    ("univ", "amenity", frozenset({"university", "college"})),
    ("theatre", "amenity", frozenset({"theatre"})),
    ("coffee", "amenity", frozenset({"cafe"})),
    ("restaurant", "amenity", frozenset({"restaurant"})),
    ("fast_food", "amenity", frozenset({"fast_food"})),
    ("bars", "amenity", frozenset({"bar", "pub"})),
    ("fire", "amenity", frozenset({"fire_station"})),
    ("bus", "highway", frozenset({"bus_stop"})),
    ("shopping", "shop", frozenset({"mall", "department_store"})),
    ("parks", "leisure", frozenset({"park"})),
    ("sport", "leisure", frozenset({"fitness_centre", "sports_centre"})),
    ("museum", "tourism", frozenset({"museum"})),
    ("hotel", "tourism", frozenset({"hotel", "hostel", "guest_house", "motel"})),
    (
        "monuments",
        "historic",
        frozenset({"monument", "castle", "fort", "archaeological_site", "ruins", "tomb"}),
    ),
    ("camera", "man_made", frozenset({"surveillance"})),
)

#: Bir OSM nesnesinin yerel bir kayıtla "aynı yer" sayılacağı mesafe (metre).
MATCH_RADIUS_M: dict[str, float] = {
    "kdgr": 100,
    "schl": 120,
    "univ": 200,
    "theatre": 80,
    "coffee": 30,
    "restaurant": 30,
    "fast_food": 30,
    "bars": 30,
    "fire": 150,
    "bus": 25,
    "shopping": 150,
    "parks": 250,
    "sport": 60,
    "museum": 80,
    "hotel": 50,
    "monuments": 60,
    "camera": 15,
}

#: Bir kategori hangi yerel kategorilere karşı eşleşir. Belirtilmeyen kategori
#: yalnız kendisine karşı eşleşir.
MATCH_POOL: dict[str, tuple[str, ...]] = {
    "coffee": ("coffee", "restaurant", "fast_food", "bars"),
    "restaurant": ("coffee", "restaurant", "fast_food", "bars"),
    "fast_food": ("coffee", "restaurant", "fast_food", "bars"),
    "bars": ("coffee", "restaurant", "fast_food", "bars"),
    "kdgr": ("kdgr", "schl"),
    "schl": ("kdgr", "schl"),
}

FOOD: tuple[str, ...] = ("coffee", "restaurant", "fast_food", "bars")

#: OSM içinde aynı nesnenin nokta ve alan olarak iki kez çizilmesine karşı.
INTERNAL_RADIUS_FACTOR = 0.6
INTERNAL_RADIUS_CAP_M = 80.0

CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(c for c, _, _ in OSM_TAGS))

#: Yerel veriyle aynı şeyi ölçmek için ek süzgeçler. Örnek kayıtlara bakılarak
#: kondu: ``amenity=college`` sürücülük kurslarını, ``amenity=theatre`` ise
#: kinoları ve mədəniyyət evlərini de getiriyordu.
MIN_AREA_M2: dict[str, float] = {
    # Yerelde karşılığı bulunan OSM parklarının en küçük %10'u ~1 700 m².
    # Bunun altı meydan ya da ağaçlıklı köşe; alanı bilinmeyen nokta parklar
    # da bu yüzden dışarıda kalır.
    "parks": 2000,
}
NAME_REQUIRED: frozenset[str] = frozenset(
    {"univ", "theatre", "museum", "shopping", "hotel", "sport"}
)
NAME_MUST_CONTAIN: dict[str, tuple[str, ...]] = {
    "theatre": ("teatr", "theatre", "театр"),
}
NAME_EXCLUDES: dict[str, tuple[str, ...]] = {
    "univ": ("kurs", "tədris", "sürücü", "driving", "english", "peşə", "school"),
    "theatre": ("kino", "cinema"),
    "shopping": ("mini", "market"),
    "hotel": ("yataqxana",),
}
#: ``amenity=college`` yalnız ali təhsil adı taşıyorsa kabul edilir.
COLLEGE_ALLOWED: tuple[str, ...] = ("universitet", "university", "akademiya", "academy", "institut")


def enrichment_query(bbox: tuple[float, float, float, float], timeout_s: int = 180) -> str:
    """Bütün kategorileri tek istekte çeken Overpass sorgusu.

    Alan ve yol tipindeki nesneler sınır kutusuyla gelir (``out bb``); merkez ve
    yaklaşık alan bu kutudan hesaplanır.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    box = f"({min_lat},{min_lon},{max_lat},{max_lon})"
    by_key: dict[str, set[str]] = {}
    for _, key, values in OSM_TAGS:
        by_key.setdefault(key, set()).update(values)
    parts = []
    for key, values in by_key.items():
        pattern = "|".join(sorted(values))
        parts.append(f'nwr["{key}"~"^({pattern})$"]{box};')
    return f"[out:json][timeout:{timeout_s}];(" + "".join(parts) + ");out tags bb;"


def classify(tags: dict) -> str | None:
    """OSM etiketlerinden kategoriyi çıkarır; hiçbirine uymuyorsa None."""
    for category, key, values in OSM_TAGS:
        if tags.get(key) in values:
            return category
    return None


def osm_candidates(payload: dict, boundary=None) -> pd.DataFrame:
    """Overpass yanıtını kategorili düz tabloya çevirir.

    Args:
        payload: Overpass JSON yanıtı.
        boundary: Verilirse yalnız bu geometrinin içindeki nesneler kalır.
    """
    rows = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        category = classify(tags)
        if category is None:
            continue
        lat, lon, area = element.get("lat"), element.get("lon"), 0.0
        bounds = element.get("bounds")
        if (lat is None or lon is None) and bounds:
            lat = (bounds["minlat"] + bounds["maxlat"]) / 2
            lon = (bounds["minlon"] + bounds["maxlon"]) / 2
            area = _bounds_area_m2(bounds)
        if lat is None or lon is None:
            centre = element.get("center") or {}
            lat, lon = centre.get("lat"), centre.get("lon")
        if lat is None or lon is None:
            continue
        rows.append(
            {
                "category": category,
                "name": tags.get("name:az") or tags.get("name") or "",
                "alt_names": _alt_names(tags),
                "lat": float(lat),
                "lon": float(lon),
                "area_m2": round(area),
                "osm_type": element.get("type", ""),
                "osm_id": int(element.get("id", -1)),
                "osm_value": _tag_value(category, tags),
            }
        )
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if boundary is not None and not frame.empty:
        inside = shapely.contains_xy(boundary, frame["lon"].to_numpy(), frame["lat"].to_numpy())
        frame = frame[inside].reset_index(drop=True)
    return frame


CANDIDATE_COLUMNS = [
    "category", "name", "alt_names", "lat", "lon", "area_m2", "osm_type", "osm_id", "osm_value",
]  # fmt: skip

#: Aynı nesnenin başka dillerdeki ya da resmi adları. Yerel veri Azərbaycanca
#: yazar, OSM'de ad bazen yalnız rusca ya da ingilizcedir.
NAME_TAGS = ("name", "name:az", "name:en", "name:ru", "official_name", "alt_name", "short_name")


def _alt_names(tags: dict) -> str:
    return "|".join(dict.fromkeys(str(tags[k]) for k in NAME_TAGS if tags.get(k)))


def names_of(row) -> list[str]:
    """Bir adayın bütün adları: asıl ad önce."""
    extra = str(row.get("alt_names", "") or "").split("|")
    return [n for n in dict.fromkeys([str(row.get("name", "") or ""), *extra]) if n.strip()]


def _tag_value(category: str, tags: dict) -> str:
    for cat, key, _ in OSM_TAGS:
        if cat == category:
            return str(tags.get(key, ""))
    return ""


def rejection_reason(row) -> str | None:
    """Bir OSM nesnesi yerel kategorinin tanımına uymuyorsa nedenini döndürür."""
    category = row["category"]
    name = normalise_name(row["name"]) if row["name"] else ""
    if category in MIN_AREA_M2 and row["area_m2"] < MIN_AREA_M2[category]:
        return "çox kiçik sahə"
    if category in NAME_REQUIRED and not name:
        return "adsız"
    if category in NAME_MUST_CONTAIN and not any(w in name for w in NAME_MUST_CONTAIN[category]):
        return "adı kateqoriyaya uymur"
    if any(w in name for w in NAME_EXCLUDES.get(category, ())):
        return "adı kateqoriyaya uymur"
    if category == "univ" and row["osm_value"] == "college":
        if not any(w in name for w in COLLEGE_ALLOWED):
            return "ali təhsil deyil (college)"
    return None


def apply_rules(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kurallara uymayanları ayırır.

    Returns:
        (kalanlar, atılanlar — ``reason`` sütunuyla)
    """
    if frame.empty:
        return frame, frame.assign(reason=pd.Series(dtype=str))
    reasons = frame.apply(rejection_reason, axis=1)
    rejected = frame[reasons.notna()].assign(reason=reasons[reasons.notna()])
    return frame[reasons.isna()].reset_index(drop=True), rejected.reset_index(drop=True)


def _bounds_area_m2(bounds: dict) -> float:
    """Sınır kutusunun yaklaşık alanı. Çapraz şekillerde fazla çıkar."""
    mid = np.radians((bounds["minlat"] + bounds["maxlat"]) / 2)
    height = np.radians(bounds["maxlat"] - bounds["minlat"]) * EARTH_RADIUS_M
    width = np.radians(bounds["maxlon"] - bounds["minlon"]) * EARTH_RADIUS_M * np.cos(mid)
    return float(height * width)


def _tree(lat: np.ndarray, lon: np.ndarray) -> BallTree:
    return BallTree(np.radians(np.column_stack([lat, lon])), metric="haversine")


def dedupe_osm(frame: pd.DataFrame, report: list | None = None) -> pd.DataFrame:
    """Aynı nesnenin OSM'de birden fazla çizimini teke indirir.

    Üç adım:

    1. **Nokta + alan.** Aynı nesne hem nokta hem bina olarak çizilmiş olabilir.
       İç yarıçapta (kafe 18 m, park 80 m) duran iki kayıt, biri adsızsa ya da
       adları tutuyorsa birdir. Adları gerçekten farklıysa ikisi de kalır —
       aynı binadaki iki kafe iki kafedir.
    2. **Benzer ad.** ``dedupe.dedupe`` kuralları: yazılış farkı, kiril/latin,
       numara, kategoriye özgü yarıçap.
    3. **Yemək çaprazı.** Aynı yer bir kez ``cafe``, bir kez ``restaurant``
       diye çizilmişse yemək kategorileri arasında da teke inilir.

    ``report`` verilirse atılanlar (neden ve katıldığı adla) ona eklenir.
    """
    parts = []
    for category, group in frame.groupby("category", sort=False):
        group = group.assign(_named=group["name"].str.len() > 0)
        group = group.sort_values("_named", ascending=False).reset_index(drop=True)
        radius = min(MATCH_RADIUS_M[category] * INTERNAL_RADIUS_FACTOR, INTERNAL_RADIUS_CAP_M)
        tree = _tree(group["lat"].to_numpy(), group["lon"].to_numpy())
        coords = np.radians(group[["lat", "lon"]].to_numpy())
        near, dist = tree.query_radius(coords, r=radius / EARTH_RADIUS_M, return_distance=True)
        keys = [dedupe.name_key(n) for n in group["name"]]

        dropped: dict[int, tuple[int, float]] = {}
        keep = []
        for i in range(len(group)):
            if i in dropped:
                continue
            keep.append(i)
            for j, d in zip(near[i], dist[i], strict=True):
                j = int(j)
                if j <= i or j in dropped:
                    continue
                if (
                    not keys[j].informative
                    or not keys[i].informative
                    or dedupe.same_name(keys[i], keys[j])
                ):
                    dropped[j] = (i, round(float(d) * EARTH_RADIUS_M, 1))
        if report is not None and dropped:
            report.append(
                group.iloc[list(dropped)].assign(
                    kept_name=[group.at[i, "name"] for i, _ in dropped.values()],
                    distance_m=[d for _, d in dropped.values()],
                    reason="nöqtə + sahə",
                )
            )
        result = dedupe.dedupe(group.iloc[keep].drop(columns="_named"), category)
        if report is not None and len(result.dropped):
            report.append(result.dropped)
        parts.append(result.kept)
    if not parts:
        return frame.iloc[0:0]
    merged = pd.concat(parts, ignore_index=True)

    # Yemək kategorileri arası: aynı yer iki ayrı etiketle.
    food = merged["category"].isin(FOOD)
    if food.sum() > 1:
        result = dedupe.dedupe(merged[food], "coffee")
        if report is not None and len(result.dropped):
            report.append(result.dropped.assign(reason="yemək növləri arası"))
        merged = pd.concat([merged[~food], result.kept], ignore_index=True)
    return merged


@dataclass
class CategoryResult:
    """Bir kategori için karşılaştırma sonucu."""

    category: str
    local: int
    osm: int
    matched: int
    added: int
    filtered: int = 0
    #: ``matched`` içinden, mesafe yetmeyip adı tuttuğu için eşleşenler.
    matched_by_name: int = 0

    @property
    def total(self) -> int:
        return self.local + self.added

    @property
    def growth_pct(self) -> float:
        return round(self.added / self.local * 100, 1) if self.local else 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "total": self.total, "growth_pct": self.growth_pct}


def compare(
    local: dict[str, pd.DataFrame], osm: pd.DataFrame
) -> tuple[pd.DataFrame, list[CategoryResult]]:
    """OSM nesnelerini yerel havuzla karşılaştırır.

    Returns:
        (yerelde karşılığı olmayan OSM nesneleri, kategori başına sayımlar)
    """
    if "alt_names" not in osm.columns:
        osm = osm.assign(alt_names="")
    additions = []
    results = []
    for category in CATEGORIES:
        candidates = osm[osm["category"] == category].reset_index(drop=True)
        own = local.get(category)
        local_count = 0 if own is None else len(own)
        if candidates.empty:
            results.append(CategoryResult(category, local_count, 0, 0, 0))
            continue

        pool = [
            local[c][["name", "lat", "lon"]]
            for c in MATCH_POOL.get(category, (category,))
            if c in local and not local[c].empty
        ]
        if pool:
            reference = pd.concat(pool, ignore_index=True)
            tree = _tree(reference["lat"].to_numpy(), reference["lon"].to_numpy())
            distance, _ = tree.query(np.radians(candidates[["lat", "lon"]].to_numpy()), k=1)
            nearest_m = distance.ravel() * EARTH_RADIUS_M
        else:
            reference = None
            nearest_m = np.full(len(candidates), np.inf)

        is_new = nearest_m > MATCH_RADIUS_M[category]

        # İkinci geçiş: mesafe yetmedi ama yakında aynı adla bir yerel kayıt
        # var ("Cafe Nargiz" 60 m, yerelde "Nərgiz kafe"). Koordinatlar iki
        # kaynakta bina girişi / bina ortası kadar ayrışabiliyor.
        by_name = np.zeros(len(candidates), dtype=bool)
        if reference is not None and is_new.any():
            index = dedupe.NameIndex(reference)
            radius = dedupe.NAME_RADIUS_M.get(category, dedupe.DEFAULT_NAME_RADIUS_M)
            for i in np.flatnonzero(is_new):
                row = candidates.iloc[i]
                if index.find(row["lat"], row["lon"], names_of(row), radius):
                    by_name[i] = True
            is_new &= ~by_name

        fresh = candidates[is_new].assign(
            nearest_local_m=np.round(nearest_m[is_new], 1), source="osm"
        )
        additions.append(fresh)
        results.append(
            CategoryResult(
                category=category,
                local=local_count,
                osm=len(candidates),
                matched=int((~is_new).sum()),
                added=int(is_new.sum()),
                matched_by_name=int(by_name.sum()),
            )
        )

    columns = [
        "category",
        "name",
        "alt_names",
        "lat",
        "lon",
        "area_m2",
        "osm_type",
        "osm_id",
        "nearest_local_m",
        "source",
    ]
    added = pd.concat(additions, ignore_index=True) if additions else pd.DataFrame(columns=columns)
    return added[columns], results


def merge(local: dict[str, pd.DataFrame], additions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Yerel havuza OSM eklemelerini katar; her satır kaynağını taşır."""
    merged: dict[str, pd.DataFrame] = {}
    for category, frame in local.items():
        base = frame.assign(source=frame.get("source", "yerli"))
        extra = additions[additions["category"] == category]
        if extra.empty:
            merged[category] = base
            continue
        merged[category] = pd.concat(
            [base, extra[["name", "lat", "lon", "source"]]], ignore_index=True
        )
    return merged
