"""Kategori kataloğu: azalım katsayıları ve indeks grupları.

Bu tanımlar boru hattının tek doğruluk kaynağıdır. Bir kategoriyi eklemek veya
çıkarmak yalnızca burayı değiştirmeyi gerektirir; defterler ve betikler buradan
okur.

Azalım katsayısı ``beta``, mesafeyle birlikte katkının ne kadar hızlı
düştüğünü belirler. Küçük değer uzağa da yürünen hizmetleri (metro), büyük
değer yalnızca çok yakında sayılanları (dayanacaq) anlatır.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Kategori adı -> kaynak dosya ve, tek dosyada birden fazla kategori varsa,
#: ``type`` alanındaki değer.
SOURCES: dict[str, tuple[str, str | None]] = {
    "kdgr": ("mekteb,bagca.csv", "uşaq bağçası"),
    "schl": ("mekteb,bagca.csv", "məktəb"),
    "univ": ("Ali mekteb.csv", None),
    "bus": ("dayanacaq.csv", None),
    "shopping": ("Ticaret merkezi.csv", None),
    "parks": ("Park.csv", None),
    "museum": ("muzey.csv", None),
    "theatre": ("Teatr.csv", None),
    "coffee": ("qida.csv", "kafe"),
    "restaurant": ("qida.csv", "restoran"),
    "fast_food": ("qida.csv", "fast-food"),
    "bars": ("qida.csv", "bar"),
    "sport": ("idman zali.csv", None),
    "hotel": ("hotel.csv", None),
    "monuments": ("Tarixi abide.csv", None),
    "camera": ("Ts Kamera.csv", None),
    "fire": ("Yangindan muhafize.csv", None),
}

#: Dakika başına azalım katsayısı. Değerler önceki çalışmadan devralındı;
#: türetildikleri hedef değişken belgelenmemiş, kalibrasyon bekliyor.
DECAY: dict[str, float] = {
    "kdgr": 0.1,
    "schl": 0.2,
    "univ": 0.1,
    "bus": 0.7,
    "metro": 0.05,
    "shopping": 0.1,
    "parks": 0.1,
    "sport": 0.2,
    "museum": 0.1,
    "theatre": 0.1,
    "hotel": 0.1,
    "monuments": 0.1,
    "coffee": 0.5,
    "restaurant": 0.3,
    "fast_food": 0.3,
    "bars": 0.2,
    "camera": 0.3,
    "fire": 0.05,
}

#: İndeks grupları. Bir kategori birden fazla grupta yer alabilir; bu,
#: indekslerin birbirinden bağımsız olmamasının sebeplerinden biridir.
GROUPS: dict[str, list[str]] = {
    "təhsil": ["kdgr", "schl", "univ"],
    "nəqliyyat": ["metro", "bus"],
    "turizm": ["museum", "theatre", "hotel", "monuments"],
    "yemək": ["coffee", "restaurant", "fast_food"],
    "istirahət": ["parks", "sport"],
    "əyləncə": [
        "museum",
        "shopping",
        "parks",
        "theatre",
        "coffee",
        "restaurant",
        "fast_food",
        "bars",
    ],
    "təhlükəsizlik": ["camera", "fire"],
}

#: Boru hattından çıkarılmış kategoriler ve gerekçeleri. Kayıt olarak tutulur:
#: bir kategorinin neden yok olduğu, olmadığı kadar önemlidir.
RETIRED: dict[str, str] = {
    "concert_hall": (
        "İş ortağı bu kategoriye ihtiyaç olmadığını bildirdi (2026-09). "
        "Kaynak dosya zaten yenilenmemişti ve sekiz kaydın tamamında kategori "
        "alanı boştu."
    ),
}

#: En yakın nesne mesafesinin dışa aktarıldığı kategoriler ve hizmet yarıçapı.
#: Yarıçapın ötesi boş döner; 'en yakın metro 39 km' bir erişilebilirlik
#: bilgisi değildir.
SERVICE_RADIUS_M: dict[str, float] = {
    "kdgr": 2000,
    "schl": 2000,
    "metro": 3000,
    "shopping": 5000,
    "parks": 2000,
}


@dataclass(frozen=True)
class CatalogueIssue:
    """Katalog tutarsızlığı."""

    kind: str
    detail: str


def check() -> list[CatalogueIssue]:
    """Katalogun kendi içinde tutarlı olduğunu doğrular.

    Sessiz tutarsızlıklar pahalıdır: bir grupta adı geçen ama katsayısı
    tanımlanmamış kategori, çalışma anında anlaşılmaz bir hataya dönüşür.
    """
    issues: list[CatalogueIssue] = []
    known = set(DECAY)

    for group, members in GROUPS.items():
        for member in members:
            if member not in known:
                issues.append(
                    CatalogueIssue(
                        "katsayı yok",
                        f"'{group}' grubundaki '{member}' için azalım katsayısı tanımlı değil",
                    )
                )
            if member in RETIRED:
                issues.append(
                    CatalogueIssue(
                        "emekli kategori",
                        f"'{group}' grubu çıkarılmış '{member}' kategorisini kullanıyor",
                    )
                )

    for name in SOURCES:
        if name not in DECAY:
            issues.append(
                CatalogueIssue("katsayı yok", f"'{name}' kaynağı tanımlı ama azalım katsayısı yok")
            )

    used = {m for members in GROUPS.values() for m in members}
    for name in DECAY:
        if name not in used:
            issues.append(
                CatalogueIssue("kullanılmayan", f"'{name}' için katsayı var ama hiçbir grupta yok")
            )

    for name in RETIRED:
        if name in SOURCES or name in DECAY:
            issues.append(
                CatalogueIssue(
                    "emekli ama tanımlı", f"'{name}' çıkarılmış ama katalogda hâlâ tanımlı"
                )
            )

    return issues
