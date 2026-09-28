"""Aynı yerin birden fazla kaydını bulur ve teke indirir.

İki kayıt üç durumda aynı yer sayılır:

1. **Aynı nokta.** Aralarında 2 m'den az mesafe var ve adları çelişmiyor
   (biri adsız, ya da adlar aynı). Adı olmayan dosyalarda (dayanacaq, kamera)
   tek kural budur; yolun iki yönündeki iki durak birkaç metre ayrı durduğu
   için ikisi de kalır.
2. **Aynı ad, yakın konum.** Adlar aynı ya da yalnızca yazılışta farklı, ve
   kategoriye özgü yarıçapın içindeler. Yarıçap bir zincirin iki şubesini
   birleştirmeyecek kadar dar tutuldu: kafe için 80 m, park için 400 m.
3. **Aynı numara.** "27 saylı Uşaq Bağçası" ile "27 saylı Uşaq Bağması" —
   numaralı okul ve bağçalarda numara adın kendisinden güvenilirdir. Numaralar
   farklıysa ("Uşaq bağçası 317" / "Uşaq bağçası 212") adlar ne kadar
   benzerse benzesin iki ayrı yerdir.

"Yalnızca yazılışta farklı" şu demek: büyük/küçük harf, Azərbaycan hərfləri
(ə → a, ş → s), kiril yazılış (Наргиз → nargiz), noktalama ve kategoriyi
tekrar eden genel sözcükler (kafe, restoran, uşaq bağçası, parkı) atıldıktan
sonra adlar ya %85 benzer, ya da birinin bütün sözcükleri ötekinde var.

Şüphede birleştirilmez. Adları gerçekten farklı iki kayıt aynı binada olsa da
kalır — bir ticarət mərkəzindəki iki kafe iki ayrı kafedir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0

#: Bu mesafenin altındaki iki kayıt aynı noktada sayılır.
SAME_POINT_M = 2.0

#: Aynı adlı iki kaydın aynı yer sayılacağı en büyük mesafe (metre). Adsız
#: kategorilerde (dayanacaq, kamera) yalnız aynı nokta kuralı işler.
NAME_RADIUS_M: dict[str, float] = {
    "kdgr": 300,
    "schl": 300,
    "univ": 400,
    "theatre": 200,
    "coffee": 80,
    "restaurant": 80,
    "fast_food": 80,
    "bars": 80,
    "fire": 300,
    "shopping": 300,
    "parks": 400,
    "sport": 150,
    "museum": 200,
    "hotel": 150,
    "monuments": 150,
}
DEFAULT_NAME_RADIUS_M = 100.0

#: Yalnız konuma göre temizlenen kategoriler. Yolun iki yanındaki iki durak
#: aynı adı taşır ("Gənclik m/st", 26 m) ama iki ayrı duraktır; yerel veri de
#: iki yönü ayrı tutar.
POSITION_ONLY: frozenset[str] = frozenset({"bus", "camera"})

#: İki adın aynı sayılması için gereken en düşük benzerlik.
SIMILARITY = 0.9

#: Adı yalnız genel sözcüklerden oluşan ("Çay evi", "Dönər") iki kayıt ancak bu
#: kadar yakınsa aynı yer sayılır; daha uzakta iki ayrı çay evi olabilir.
GENERIC_SAME_M = 25.0

_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "c", "ш": "s", "щ": "s", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ә": "a", "ғ": "g", "ҹ": "c", "ҝ": "k", "ө": "o", "ү": "u", "һ": "h",
    "ј": "y",
}  # fmt: skip
_AZERBAIJANI = {"ə": "a", "ı": "i", "ş": "s", "ç": "c", "ğ": "g", "ö": "o", "ü": "u", "q": "k"}
_TRANSLIT = str.maketrans({**_CYRILLIC, **_AZERBAIJANI, "w": "v"})
_DIGRAPHS = (("sh", "s"), ("ch", "c"), ("kh", "x"), ("zh", "j"))

#: Kategoriyi tekrar eden, yeri ayırt etmeyen sözcükler (harf çevirisinden sonra).
GENERIC_WORDS: frozenset[str] = frozenset(
    """
    kafe kafesi cafe caffe coffee kofe kofeynya restoran restorani restaurant bar bari
    pub lounge fast food fastfood cayxana
    usak usag bagca bagcasi bagcas sayli nomreli mekteb mektebi orta tam umumtehsil
    school kindergarten lisey liseyi gimnaziya gimnaziyasi detskiy sad skola
    universitet universiteti university akademiya akademiyasi academy institut
    institutu dovlet
    park parki bag bagi garden skver adina
    hotel hoteli otel oteli hostel inn
    muzey muzeyi museum ev evi
    teatr teatri theatre theater
    mall ticaret merkez merkezi tm center centre
    idman zal zali fitness gym klub club sport sports
    abide abidesi heykel heykeli monument
    yangin yanginsondurme hisse hissesi muhafize idare idaresi fire station depo
    mmc llc ltd ooo ve and the no
    maktab maktabi nomrali umumtahsil dovlat ticarat markaz markazi heykal heykali
    abida abidasi yanginsondurma hissa hissasi muhafiza idara idarasi va
    """.split()
)

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class NameKey:
    """Bir adın karşılaştırmaya hazır hâli."""

    core: frozenset[str]
    numbers: frozenset[str]

    @property
    def informative(self) -> bool:
        return bool(self.core or self.numbers)


def fold(name: str) -> str:
    """Harf farklarını siler: küçük harf, Latin, noktalamasız."""
    text = str(name).strip().replace("İ", "i").replace("I", "ı").lower().translate(_TRANSLIT)
    for a, b in _DIGRAPHS:
        text = text.replace(a, b)
    return " ".join(_WORD.findall(text))


def name_key(name) -> NameKey:
    if name is None or (isinstance(name, float) and np.isnan(name)) or not str(name).strip():
        return NameKey(frozenset(), frozenset())
    words = fold(name).split()
    numbers = frozenset(w for w in words if w.isdigit())
    core = frozenset(w for w in words if not w.isdigit() and w not in GENERIC_WORDS and len(w) > 1)
    return NameKey(core, numbers)


def _close(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= SIMILARITY


def common_words(
    keys: list[NameKey], min_count: int = 8, min_share: float = 0.01
) -> frozenset[str]:
    """Bir kategoride çok sık geçen, bu yüzden yer ayırt etmeyen sözcükler.

    Yemək dosyasında "dönər", universitetlərdə "korpus", "azərbaycan" gibi.
    Sabit listeye yazılamayacak kadar kategoriye özgüdürler; sayılarak bulunur.
    """
    counts: dict[str, int] = {}
    for key in keys:
        for word in key.core:
            counts[word] = counts.get(word, 0) + 1
    limit = max(min_count, min_share * len(keys))
    return frozenset(w for w, c in counts.items() if c >= limit)


def without(key: NameKey, words: frozenset[str]) -> NameKey:
    return NameKey(key.core - words, key.numbers) if words else key


def same_name(a: NameKey, b: NameKey) -> bool:
    """İki ad aynı yeri mi anlatıyor.

    Numara ayırıcıdır: iki tarafta farklı numara ya da yalnız bir tarafta
    numara ("Maya bağçası 2" / "Maya bağçası") iki ayrı şube demektir.
    Numaralar aynıysa ve bir tarafın adı yalnız genel sözcüklerden oluşuyorsa
    ("Körpələr evi 91" / "Uşaq bağçası 91") aynı yerdir.
    """
    if a.numbers != b.numbers:
        return False
    if a.numbers and (not a.core or not b.core):
        return True
    if not a.core or not b.core:
        return False
    if _close(" ".join(sorted(a.core)), " ".join(sorted(b.core))):
        return True
    # Bir adın bütün sözcükleri ötekinde var: "Gənclik City" / "Gənclik City
    # bowling". Tek sözcüklü adlar bu yoldan eşleşmez — "Arzu" ile "Arzu
    # şadlıq sarayı" iki ayrı yer olabilir.
    small, large = sorted((a.core, b.core), key=len)
    if len(small) < 2:
        return False
    return all(any(_close(w, v) for v in large) for w in small)


def _tree(frame: pd.DataFrame) -> tuple[BallTree, np.ndarray]:
    coords = np.radians(frame[["lat", "lon"]].to_numpy(dtype=float))
    return BallTree(coords, metric="haversine"), coords


REASON_POINT = "eyni nöqtə"
REASON_NAME = "eyni ad, yaxın"
REASON_NUMBER = "eyni nömrə, yaxın"


def match_reason(
    raw_a: NameKey,
    raw_b: NameKey,
    a: NameKey,
    b: NameKey,
    fold_a: str,
    fold_b: str,
    metres: float,
    named: bool,
    radius: float = DEFAULT_NAME_RADIUS_M,
    common: frozenset[str] = frozenset(),
) -> str | None:
    """İki komşu kayıt aynı yer mi; öyleyse nedeni.

    ``a``/``b`` kategoride sık geçen sözcükleri atılmış adlar, ``raw_*`` ise
    atılmamış hâlleri. Sık sözcük atılınca kaybolan fark ("musiqi məktəbi" /
    "orta məktəb", "İqtisad korpus 4" / "Tibb korpus 4") ham adla yakalanır.
    """
    if metres <= SAME_POINT_M and (
        not raw_a.informative or not raw_b.informative or same_name(raw_a, raw_b)
    ):
        return REASON_POINT
    if not named:
        return None
    if not same_name(a, b):
        # Adı yalnız genel sözcüklerden oluşan iki kayıt ("Çay evi" / "Çay evi").
        if (
            fold_a
            and fold_a == fold_b
            and not a.core
            and not a.numbers
            and metres <= GENERIC_SAME_M
        ):
            return REASON_NAME
        return None
    if a.numbers:
        # Numara aynı; ama iki tarafta da ad varsa adlar çelişmemeli.
        plain_a, plain_b = NameKey(raw_a.core, frozenset()), NameKey(raw_b.core, frozenset())
        if (
            raw_a.core
            and raw_b.core
            and raw_a.core != raw_b.core
            and not same_name(plain_a, plain_b)
        ):
            return None
        return REASON_NUMBER
    # Birinde olup ötekinde olmayan sık sözcük yer tipini ayırır: "musiqi",
    # "təndir", "korpus".
    if (raw_a.core ^ raw_b.core) & common:
        return None
    # Tek sözcüklü ad zayıf kanıttır; yalnız yarıçapın yarısında kabul edilir.
    if min(len(a.core), len(b.core)) == 1 and metres > radius / 2:
        return None
    return REASON_NAME


@dataclass
class DedupeResult:
    """Bir kategorinin temizlik sonucu."""

    category: str
    before: int
    kept: pd.DataFrame
    dropped: pd.DataFrame

    @property
    def after(self) -> int:
        return len(self.kept)

    def summary(self) -> dict:
        reasons = self.dropped["reason"].value_counts().to_dict() if len(self.dropped) else {}
        return {
            "category": self.category,
            "before": self.before,
            "after": self.after,
            "dropped": len(self.dropped),
            "by_reason": {k: int(v) for k, v in reasons.items()},
        }


def dedupe(
    frame: pd.DataFrame,
    category: str,
    named: bool = True,
    radius_m: float | None = None,
) -> DedupeResult:
    """Bir kategorinin tekrar eden kayıtlarını teke indirir.

    Args:
        frame: ``lat``, ``lon`` ve ``name`` sütunlu tablo.
        category: Yarıçap bu addan seçilir.
        named: Dosyada gerçek ad yoksa (ad dosya adından türetildiyse) False —
            o zaman yalnız aynı nokta kuralı işler.
        radius_m: Aynı ad yarıçapını elle vermek için.

    Kayıtlar adı en uzun olandan başlayarak gezilir; bir kayıt yalnız daha önce
    tutulmuş bir kayıtla **doğrudan** eşleşirse atılır. Zincirleme birleşme
    yoktur: "Korpus 4" ≈ "Tibb Universiteti" ≈ "Korpus 5" üçünü tek kayda
    indirmez. Atılanlar hangi kayda katıldığını ve nedenini taşır.
    """
    frame = frame.reset_index(drop=True)
    n = len(frame)
    empty = frame.iloc[0:0].assign(kept_name="", distance_m=0.0, reason="")
    if n < 2:
        return DedupeResult(category, n, frame, empty)
    named = named and category not in POSITION_ONLY

    radius = (
        radius_m if radius_m is not None else NAME_RADIUS_M.get(category, DEFAULT_NAME_RADIUS_M)
    )
    names = frame["name"].fillna("").astype(str).tolist() if named else [""] * n
    raw_keys = [name_key(x) for x in names]
    common = common_words(raw_keys)
    keys = [without(k, common) for k in raw_keys]
    folded = [fold(x) for x in names]
    tree, coords = _tree(frame)
    search = max(radius, SAME_POINT_M) if named else SAME_POINT_M
    neighbours, distances = tree.query_radius(
        coords, r=search / EARTH_RADIUS_M, return_distance=True
    )

    order = sorted(range(n), key=lambda k: (-len(names[k].strip()), k))
    kept_set: set[int] = set()
    drops = []
    for i in order:
        match = None
        for j, d in sorted(zip(neighbours[i], distances[i], strict=True), key=lambda t: t[1]):
            j = int(j)
            if j not in kept_set:
                continue
            reason = match_reason(raw_keys[i], raw_keys[j], keys[i], keys[j], folded[i], folded[j],
                            float(d) * EARTH_RADIUS_M, named, radius, common)  # fmt: skip
            if reason:
                match = (j, round(float(d) * EARTH_RADIUS_M, 1), reason)
                break
        if match is None:
            kept_set.add(i)
        else:
            drops.append((i, names[match[0]], match[1], match[2]))

    keep = sorted(kept_set)
    kept = frame.iloc[keep].reset_index(drop=True)
    if drops:
        dropped = (
            frame.iloc[[d[0] for d in drops]]
            .reset_index(drop=True)
            .assign(
                kept_name=[d[1] for d in drops],
                distance_m=[d[2] for d in drops],
                reason=[d[3] for d in drops],
            )
        )
    else:
        dropped = empty
    return DedupeResult(category, n, kept, dropped)


class NameIndex:
    """Ada ve konuma göre aranabilen referans kayıtlar.

    OSM nesnesinin yerel veride "aynı adla, biraz ötede" bir karşılığı var mı
    sorusu için. Bir nesnenin birden fazla adı olabilir (``name``, ``name:az``,
    ``name:ru``); herhangi biri tutarsa eşleşir.
    """

    def __init__(self, frame: pd.DataFrame, named: bool = True):
        self.frame = frame.reset_index(drop=True)
        self.named = named and has_real_names(self.frame)
        names = self.frame["name"].fillna("").astype(str).tolist() if self.named else []
        self.raw = [name_key(x) for x in names]
        self.common = common_words(self.raw)
        self.keys = [without(k, self.common) for k in self.raw]
        self.folded = [fold(x) for x in names]
        self.tree = _tree(self.frame)[0] if len(self.frame) else None

    def find(
        self, lat: float, lon: float, names: list[str], radius_m: float
    ) -> tuple[int, float, str] | None:
        """En yakın, adı tutan referans kayıt: (sıra, metre, neden) ya da None."""
        if self.tree is None or not self.named:
            return None
        variants = [n for n in dict.fromkeys(names) if n and str(n).strip()]
        if not variants:
            return None
        idx, dist = self.tree.query_radius(
            np.radians([[lat, lon]]), r=radius_m / EARTH_RADIUS_M, return_distance=True
        )
        for j, d in sorted(zip(idx[0], dist[0], strict=True), key=lambda t: t[1]):
            metres = float(d) * EARTH_RADIUS_M
            for name in variants:
                raw = name_key(name)
                reason = match_reason(
                    raw, self.raw[j], without(raw, self.common), self.keys[j],
                    fold(name), self.folded[j], metres, True, radius_m, self.common,
                )  # fmt: skip
                if reason:
                    return int(j), round(metres, 1), reason
        return None


def has_real_names(frame: pd.DataFrame) -> bool:
    """Ad sütunu gerçek ad mı, yoksa dosya adından türetilmiş sabit bir etiket mi."""
    if "name" not in frame.columns or frame.empty:
        return False
    return frame["name"].astype(str).nunique() > 1


CROSS_COLUMNS = ["category_a", "name_a", "category_b", "name_b", "distance_m"]


def cross_duplicates(
    frames: dict[str, pd.DataFrame], categories: tuple[str, ...], radius_m: float = 30.0
) -> pd.DataFrame:
    """Aynı yerin iki farklı kategoride kayıtlı olduğu çiftler (yalnız rapor).

    Yemək dosyasında bir yer hem kafe hem restoran olarak geçebilir. Hangisinin
    doğru olduğu veri sahibinin kararı; burada yalnız sayılır, silinmez.
    """
    parts = [
        frames[c][["name", "lat", "lon"]].assign(category=c)
        for c in categories
        if c in frames and not frames[c].empty
    ]
    if not parts:
        return pd.DataFrame(columns=CROSS_COLUMNS)
    pool = pd.concat(parts, ignore_index=True)
    keys = [name_key(x) for x in pool["name"].fillna("").astype(str)]
    tree, coords = _tree(pool)
    neighbours, distances = tree.query_radius(
        coords, r=radius_m / EARTH_RADIUS_M, return_distance=True
    )
    common = common_words(keys)
    keys = [without(k, common) for k in keys]
    cats = pool["category"].to_numpy()
    rows = []
    for i in range(len(pool)):
        for j, d in zip(neighbours[i], distances[i], strict=True):
            j = int(j)
            if j <= i or cats[i] == cats[j] or not keys[i].core:
                continue
            if same_name(keys[i], keys[j]):
                rows.append(
                    {
                        "category_a": cats[i],
                        "name_a": pool.at[i, "name"],
                        "category_b": cats[j],
                        "name_b": pool.at[j, "name"],
                        "distance_m": round(float(d) * EARTH_RADIUS_M, 1),
                    }
                )
    return pd.DataFrame(rows, columns=CROSS_COLUMNS)
