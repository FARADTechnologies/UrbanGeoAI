"""Metro istasyonu listesinin denetlenmesi ve tekilleştirilmesi.

Ham Overpass sorgusu istasyon olmayan düğümler de döndürüyor. Dört ayrı durum
var ve üçü farklı karar gerektiriyor:

**Birebir tekrar.** Aynı istasyon iki düğüm olarak kayıtlı. Tartışmasız
tekrardır, biri düşer.

**Servis noktası.** Depo, makas, bakım alanı. Yolcu bunları kullanamaz, bu
yüzden erişilebilirlik açısından istasyon değildir.

**İşletmede olmayan istasyon.** İnşa hâlindeki veya planlanan istasyonlar
OpenStreetMap'te bulunur. Bir konuma "metroya 200 m" demek, o metro açık
değilse yanlıştır.

**Aktarma kompleksi.** İki ayrı istasyon fiziksel olarak tek bir yapı içinde.
Yolcu için tek erişim noktasıdır; iki kez saymak o noktanın ulaşım puanını
şişirir.

Son ikisi ürün kararıdır, bu yüzden davranış konfigürasyondan değiştirilebilir
ve her kaydın gerekçesi raporda kalır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0

#: Aynı istasyonun iki kaydı sayılacağı azami mesafe.
DUPLICATE_RADIUS_M = 200.0

#: Aktarma kompleksi sayılacağı azami mesafe. Farklı isimler için geçerli.
INTERCHANGE_RADIUS_M = 150.0

#: Servis noktalarını tanıyan kalıplar. İsimde geçerse istasyon değildir.
SERVICE_PATTERNS = ("depo", "deposu", "depot", "elektrik deposu", "azər neft yağ")

#: Hat numarası biçimindeki teknik düğümler (Y14, B-4 gibi).
TECHNICAL_PATTERN = r"^[A-Za-zƏəÜüÖöĞğİıŞşÇç]{1,2}-?\d{1,3}$"


class Decision(StrEnum):
    """Bir düğümün akıbeti."""

    KEEP = "tutuldu"
    DUPLICATE = "birebir_tekrar"
    SERVICE = "servis_noktasi"
    NOT_OPERATIONAL = "isletmede_degil"
    INTERCHANGE = "aktarma_kompleksi"
    UNNAMED = "isimsiz"


@dataclass
class NodeRecord:
    """Tek bir ham düğüm ve hakkında verilen karar."""

    osm_id: int
    name: str
    lat: float
    lon: float
    decision: Decision
    reason: str = ""
    merged_with: str | None = None


@dataclass
class MetroReport:
    """Denetimin tam çıktısı."""

    records: list[NodeRecord] = field(default_factory=list)

    @property
    def kept(self) -> list[NodeRecord]:
        return [r for r in self.records if r.decision is Decision.KEEP]

    @property
    def removed(self) -> list[NodeRecord]:
        return [r for r in self.records if r.decision is not Decision.KEEP]

    def frame(self) -> pd.DataFrame:
        """Tutulan istasyonları skorlamaya uygun tabloya çevirir."""
        return pd.DataFrame(
            [{"name": r.name, "lat": r.lat, "lon": r.lon, "osm_id": r.osm_id} for r in self.kept]
        )

    def audit_frame(self) -> pd.DataFrame:
        """Her düğüm için karar ve gerekçe. İzlenebilirlik kaydı."""
        return pd.DataFrame(
            [
                {
                    "osm_id": r.osm_id,
                    "name": r.name,
                    "lat": r.lat,
                    "lon": r.lon,
                    "decision": r.decision.value,
                    "reason": r.reason,
                    "merged_with": r.merged_with,
                }
                for r in self.records
            ]
        )

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.decision.value] = counts.get(record.decision.value, 0) + 1
        return counts


def normalise_name(name: str) -> str:
    """İsimleri karşılaştırılabilir hale getirir.

    Python'un ``casefold`` yöntemi Azerbaycanca noktalı **İ** harfini
    ``i`` artı ayrı bir birleşik nokta olarak açıyor. Aynı ismin biri büyük
    biri küçük yazılmış iki kaydı bu yüzden eşleşmiyor. İstasyon adlarının
    çoğunda bu harf bulunduğu için (``İçərişəhər``, ``İnşaatçılar``) noktalı
    ve noktasız I çiftleri karşılaştırmadan önce elle eşleniyor.
    """
    return name.strip().replace("İ", "i").replace("I", "ı").casefold()


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """İki koordinat arası büyük çember mesafesi."""
    lat1, lon1, lat2, lon2 = map(np.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return float(2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(h)))


def is_service_node(name: str) -> bool:
    """Depo, makas ve bakım noktalarını tanır."""
    lowered = normalise_name(name)
    if any(pattern in lowered for pattern in SERVICE_PATTERNS):
        return True
    return bool(pd.Series([name.strip()]).str.match(TECHNICAL_PATTERN, case=False).iloc[0])


def deduplicate(
    records: list[dict],
    not_operational: tuple[str, ...] = (),
    merge_interchanges: bool = True,
    duplicate_radius_m: float = DUPLICATE_RADIUS_M,
    interchange_radius_m: float = INTERCHANGE_RADIUS_M,
) -> MetroReport:
    """Ham düğüm listesini denetler ve tekilleştirir.

    Args:
        records: ``osm_id``, ``name``, ``lat``, ``lon`` alanlı ham düğümler.
        not_operational: İşletmede olmayan istasyon adları. Eşleşme büyük
            küçük harf ve baştaki sondaki boşluktan bağımsızdır.
        merge_interchanges: True ise birbirine yakın farklı isimli istasyonlar
            tek erişim noktası sayılır ve ilki tutulur.
        duplicate_radius_m: Aynı isimli iki kaydın tekrar sayılacağı mesafe.
        interchange_radius_m: Farklı isimli iki istasyonun aktarma kompleksi
            sayılacağı mesafe.

    Returns:
        Her düğüm için karar ve gerekçe taşıyan rapor.

    Not:
        Karar sırası önemli. Servis ve işletme dışı düğümler önce elenir,
        böylece bir depo yakınındaki gerçek istasyonu aktarma sanmayız.
    """
    normalised = {normalise_name(n) for n in not_operational}
    report = MetroReport()

    # 1. Adım: isimsiz, servis ve işletme dışı düğümleri ayır.
    candidates: list[dict] = []
    for node in records:
        name = (node.get("name") or "").strip()
        if not name or name == "Unnamed":
            report.records.append(
                NodeRecord(
                    osm_id=node.get("osm_id", -1),
                    name=name or "(isimsiz)",
                    lat=node["lat"],
                    lon=node["lon"],
                    decision=Decision.UNNAMED,
                    reason="düğümün adı yok, istasyon olarak doğrulanamıyor",
                )
            )
            continue

        if is_service_node(name):
            report.records.append(
                NodeRecord(
                    osm_id=node.get("osm_id", -1),
                    name=name,
                    lat=node["lat"],
                    lon=node["lon"],
                    decision=Decision.SERVICE,
                    reason="depo, makas veya teknik nokta; yolcu erişimine kapalı",
                )
            )
            continue

        if normalise_name(name) in normalised:
            report.records.append(
                NodeRecord(
                    osm_id=node.get("osm_id", -1),
                    name=name,
                    lat=node["lat"],
                    lon=node["lon"],
                    decision=Decision.NOT_OPERATIONAL,
                    reason="istasyon işletmede değil",
                )
            )
            continue

        candidates.append({**node, "name": name})

    if not candidates:
        return report

    # 2. Adım: aynı isim, yakın konum -> birebir tekrar.
    kept: list[dict] = []
    for node in candidates:
        twin = next(
            (
                k
                for k in kept
                if normalise_name(k["name"]) == normalise_name(node["name"])
                and _distance_m((k["lat"], k["lon"]), (node["lat"], node["lon"]))
                <= duplicate_radius_m
            ),
            None,
        )
        if twin is None:
            kept.append(node)
            continue
        distance = _distance_m((twin["lat"], twin["lon"]), (node["lat"], node["lon"]))
        report.records.append(
            NodeRecord(
                osm_id=node.get("osm_id", -1),
                name=node["name"],
                lat=node["lat"],
                lon=node["lon"],
                decision=Decision.DUPLICATE,
                reason=f"aynı isim {distance:.0f} m mesafede zaten kayıtlı",
                merged_with=str(twin.get("osm_id", "")),
            )
        )

    # 3. Adım: farklı isim, çok yakın konum -> aktarma kompleksi.
    if merge_interchanges and len(kept) > 1:
        coords = np.radians([[k["lat"], k["lon"]] for k in kept])
        tree = BallTree(coords, metric="haversine")
        neighbours = tree.query_radius(coords, r=interchange_radius_m / EARTH_RADIUS_M)

        merged: set[int] = set()
        for i, group in enumerate(neighbours):
            if i in merged:
                continue
            for j in group:
                if j <= i or j in merged:
                    continue
                distance = _distance_m(
                    (kept[i]["lat"], kept[i]["lon"]), (kept[j]["lat"], kept[j]["lon"])
                )
                merged.add(int(j))
                report.records.append(
                    NodeRecord(
                        osm_id=kept[j].get("osm_id", -1),
                        name=kept[j]["name"],
                        lat=kept[j]["lat"],
                        lon=kept[j]["lon"],
                        decision=Decision.INTERCHANGE,
                        reason=(
                            f"'{kept[i]['name']}' ile {distance:.0f} m mesafede; "
                            "tek aktarma kompleksi sayıldı"
                        ),
                        merged_with=kept[i]["name"],
                    )
                )
        kept = [k for i, k in enumerate(kept) if i not in merged]

    for node in kept:
        report.records.append(
            NodeRecord(
                osm_id=node.get("osm_id", -1),
                name=node["name"],
                lat=node["lat"],
                lon=node["lon"],
                decision=Decision.KEEP,
                reason="işletmedeki istasyon",
            )
        )
    return report
