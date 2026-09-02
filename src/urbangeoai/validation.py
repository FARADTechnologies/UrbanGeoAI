"""POI veri dosyalarının doğruluk denetimi.

Bu modül veriyi düzeltmez; yalnızca ölçer ve raporlar. Düzeltme kararları
ayrı ele alınır, çünkü bir kısmı ürün kararıdır: yolun iki yönündeki durak
tek nokta mı sayılır, aktarma kompleksi bir istasyon mudur.

Her kontrol bağımsız bir fonksiyondur ve aynı ``Finding`` listesini üretir,
böylece yeni kontrol eklemek mevcutları etkilemez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0


class Severity(StrEnum):
    """Bulgunun aciliyeti.

    ``ERROR`` veriyi kullanılamaz kılar, ``WARNING`` sonucu bozabilir,
    ``INFO`` yalnızca kayıt amaçlıdır.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    """Tek bir kontrolün tek bir dosyada bulduğu sorun."""

    check: str
    severity: Severity
    message: str
    count: int
    rows: tuple[int, ...] = ()

    def format(self, max_rows: int = 5) -> str:
        shown = ", ".join(str(r) for r in self.rows[:max_rows])
        if len(self.rows) > max_rows:
            shown += f", … (+{len(self.rows) - max_rows})"
        suffix = f"  satır: {shown}" if shown else ""
        return f"[{self.severity.value:<7}] {self.check:<22} {self.message}{suffix}"


@dataclass
class FileReport:
    """Bir dosyanın bütün bulguları."""

    path: Path
    rows: int
    columns: tuple[str, ...]
    findings: list[Finding] = field(default_factory=list)
    unreadable: str | None = None

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    def to_dict(self) -> dict:
        return {
            "file": self.path.name,
            "rows": self.rows,
            "columns": list(self.columns),
            "unreadable": self.unreadable,
            "findings": [
                {
                    "check": f.check,
                    "severity": f.severity.value,
                    "message": f.message,
                    "count": f.count,
                    "rows": list(f.rows),
                }
                for f in self.findings
            ],
        }


# ── Tekil kontroller ────────────────────────────────────────────────────────
# Her biri bir tablo alır ve bulgu listesi döndürür. Bulgu yoksa boş liste.


def check_required_columns(frame: pd.DataFrame) -> list[Finding]:
    """Koordinat sütunlarının varlığı. Yoksa dosya kullanılamaz."""
    missing = [c for c in ("lat", "lon") if c not in frame.columns]
    if not missing:
        return []
    return [
        Finding(
            check="zorunlu_sutun",
            severity=Severity.ERROR,
            message=f"koordinat sütunu yok: {', '.join(missing)}",
            count=len(missing),
        )
    ]


def check_missing_name(frame: pd.DataFrame, synthesised: bool) -> list[Finding]:
    """Boş veya üretilmiş isimler.

    İsim sütununun hiç bulunmaması hata değil: durak ve kamera dosyalarında
    isim yok ve olması da gerekmiyor. Ancak bu durumda en yakın nesnenin adı
    raporlanamaz, o yüzden kayda geçer.
    """
    if synthesised:
        return [
            Finding(
                check="isim_sutunu",
                severity=Severity.INFO,
                message="dosyada 'name' sütunu yok; dosya adından etiket üretildi",
                count=len(frame),
            )
        ]
    if "name" not in frame.columns:
        return []

    blank = frame["name"].isna() | (frame["name"].astype(str).str.strip() == "")
    if not blank.any():
        return []
    return [
        Finding(
            check="bos_isim",
            severity=Severity.WARNING,
            message="isim alanı boş",
            count=int(blank.sum()),
            rows=tuple(int(i) for i in frame.index[blank]),
        )
    ]


def check_missing_type(frame: pd.DataFrame) -> list[Finding]:
    """Boş kategori alanı.

    Kategori, POI'nin hangi indekse gireceğini belirler. Boşsa kayıt hiçbir
    gruba düşmez ve sessizce yok sayılır.
    """
    if "type" not in frame.columns:
        return []
    blank = frame["type"].isna() | (frame["type"].astype(str).str.strip() == "")
    if not blank.any():
        return []
    severity = Severity.ERROR if blank.all() else Severity.WARNING
    return [
        Finding(
            check="bos_kategori",
            severity=severity,
            message="kategori alanı boş" + (" (dosyanın tamamı)" if blank.all() else ""),
            count=int(blank.sum()),
            rows=tuple(int(i) for i in frame.index[blank]),
        )
    ]


def check_coordinate_range(frame: pd.DataFrame) -> list[Finding]:
    """Fiziksel olarak geçersiz koordinatlar."""
    findings = []
    invalid = frame["lat"].isna() | frame["lon"].isna()
    if invalid.any():
        findings.append(
            Finding(
                check="koordinat_okunamadi",
                severity=Severity.ERROR,
                message="koordinat sayıya çevrilemedi",
                count=int(invalid.sum()),
                rows=tuple(int(i) for i in frame.index[invalid]),
            )
        )

    valid = frame.dropna(subset=["lat", "lon"])
    out_of_range = (
        (valid["lat"] < -90) | (valid["lat"] > 90) | (valid["lon"] < -180) | (valid["lon"] > 180)
    )
    if out_of_range.any():
        findings.append(
            Finding(
                check="koordinat_araligi",
                severity=Severity.ERROR,
                message="koordinat geçerli aralığın dışında",
                count=int(out_of_range.sum()),
                rows=tuple(int(i) for i in valid.index[out_of_range]),
            )
        )

    # Tam sıfır neredeyse her zaman eksik veriyi gösterir; Gine Körfezi'ndeki
    # o noktada gerçek bir POI bulunmaz.
    null_island = (valid["lat"] == 0) & (valid["lon"] == 0)
    if null_island.any():
        findings.append(
            Finding(
                check="sifir_koordinat",
                severity=Severity.ERROR,
                message="koordinat (0, 0) — eksik veri göstergesi",
                count=int(null_island.sum()),
                rows=tuple(int(i) for i in valid.index[null_island]),
            )
        )
    return findings


def check_bbox(frame: pd.DataFrame, bbox: tuple[float, float, float, float]) -> list[Finding]:
    """Analiz alanı dışındaki kayıtlar.

    Önceki veri sürümünde iki dosya ülke genelini kapsıyordu ve Bakı
    hücreleri yüzlerce kilometre uzaktaki nesnelere karşı puanlanıyordu.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    valid = frame.dropna(subset=["lat", "lon"])
    outside = (
        (valid["lon"] < min_lon)
        | (valid["lon"] > max_lon)
        | (valid["lat"] < min_lat)
        | (valid["lat"] > max_lat)
    )
    if not outside.any():
        return []
    return [
        Finding(
            check="alan_disi",
            severity=Severity.WARNING,
            message=f"analiz alanının dışında ({min_lon}, {min_lat}, {max_lon}, {max_lat})",
            count=int(outside.sum()),
            rows=tuple(int(i) for i in valid.index[outside]),
        )
    ]


def check_precision(frame: pd.DataFrame, min_decimals: int) -> list[Finding]:
    """Düşük koordinat hassasiyeti.

    Dört ondalık basamak enlemde yaklaşık 11 m belirsizlik demektir. 500 m
    yarıçapla çalışırken bu tolere edilebilir, ancak yakın tekrar tespitini
    zorlaştırır.
    """
    valid = frame.dropna(subset=["lat", "lon"])
    if valid.empty:
        return []

    def decimals(series: pd.Series) -> pd.Series:
        text = series.astype(str)
        return text.str.split(".").str[-1].str.len().where(text.str.contains(r"\."), 0)

    low = (decimals(valid["lat"]) < min_decimals) | (decimals(valid["lon"]) < min_decimals)
    if not low.any():
        return []
    return [
        Finding(
            check="dusuk_hassasiyet",
            severity=Severity.INFO,
            message=f"koordinat {min_decimals} basamaktan az",
            count=int(low.sum()),
            rows=tuple(int(i) for i in valid.index[low]),
        )
    ]


def check_exact_duplicates(frame: pd.DataFrame) -> list[Finding]:
    """Birebir aynı kayıtlar. Bunlar tartışmasız tekrardır."""
    findings = []

    same_coords = frame.duplicated(subset=["lat", "lon"], keep=False)
    if same_coords.any():
        findings.append(
            Finding(
                check="ayni_koordinat",
                severity=Severity.WARNING,
                message="birden fazla kayıt aynı koordinatta",
                count=int(same_coords.sum()),
                rows=tuple(int(i) for i in frame.index[same_coords]),
            )
        )

    if "name" in frame.columns:
        same_row = frame.duplicated(subset=["name", "lat", "lon"], keep=False)
        if same_row.any():
            findings.append(
                Finding(
                    check="birebir_tekrar",
                    severity=Severity.ERROR,
                    message="aynı isim ve aynı koordinat",
                    count=int(same_row.sum()),
                    rows=tuple(int(i) for i in frame.index[same_row]),
                )
            )
    return findings


def check_near_duplicates(frame: pd.DataFrame, radius_m: float) -> list[Finding]:
    """Yakın konumda aynı isimli kayıtlar.

    Birebir tekrardan ayrı raporlanır, çünkü yorumu farklıdır: aynı zincirin
    iki şubesi meşru olabilir, ama aynı okulun iki kaydı değildir. Karar veri
    sahibine aittir.
    """
    valid = frame.dropna(subset=["lat", "lon"])
    if len(valid) < 2 or "name" not in valid.columns:
        return []

    tree = BallTree(np.radians(valid[["lat", "lon"]].to_numpy()), metric="haversine")
    neighbours = tree.query_radius(
        np.radians(valid[["lat", "lon"]].to_numpy()), r=radius_m / EARTH_RADIUS_M
    )

    names = valid["name"].astype(str).str.strip().str.casefold().to_numpy()
    positions = valid.index.to_numpy()
    flagged: set[int] = set()
    for i, group in enumerate(neighbours):
        for j in group:
            if i < j and names[i] == names[j] and names[i]:
                flagged.add(int(positions[i]))
                flagged.add(int(positions[j]))

    if not flagged:
        return []
    return [
        Finding(
            check="yakin_tekrar",
            severity=Severity.WARNING,
            message=f"aynı isim {radius_m:.0f} m içinde tekrar ediyor",
            count=len(flagged),
            rows=tuple(sorted(flagged)),
        )
    ]


def check_clustering(frame: pd.DataFrame, radius_m: float) -> list[Finding]:
    """İsimsiz dosyalarda yakın konum yoğunluğu.

    Durak verisinde yolun iki yönü ayrı kayıt olabilir. Bu bir hata değil,
    ama sayımı ikiye katladığı için ölçülmesi gerekir.
    """
    valid = frame.dropna(subset=["lat", "lon"])
    if len(valid) < 2:
        return []

    tree = BallTree(np.radians(valid[["lat", "lon"]].to_numpy()), metric="haversine")
    counts = tree.query_radius(
        np.radians(valid[["lat", "lon"]].to_numpy()),
        r=radius_m / EARTH_RADIUS_M,
        count_only=True,
    )
    clustered = int((counts > 1).sum())
    if not clustered:
        return []
    return [
        Finding(
            check="yakin_kume",
            severity=Severity.INFO,
            message=(
                f"{radius_m:.0f} m içinde başka kayıt bulunan nokta "
                f"({clustered / len(valid):.0%} of {len(valid)})"
            ),
            count=clustered,
        )
    ]


def check_encoding(report_encoding: str) -> list[Finding]:
    """UTF-8 dışında bir kodlamayla okunabilen dosyalar.

    Böyle dosyalarda Azerbaycanca harfler bozulur ve isim eşleştirmesi
    güvenilmez hale gelir.
    """
    if report_encoding.lower().startswith("utf-8"):
        return []
    return [
        Finding(
            check="kodlama",
            severity=Severity.WARNING,
            message=f"dosya UTF-8 değil, '{report_encoding}' ile okundu",
            count=1,
        )
    ]


# ── Toplayıcı ───────────────────────────────────────────────────────────────


def validate_file(
    path: Path,
    bbox: tuple[float, float, float, float] | None = None,
    duplicate_radius_m: float = 50.0,
    min_decimals: int = 5,
) -> FileReport:
    """Tek bir POI dosyasını bütün kontrollerden geçirir.

    Okunamayan dosya istisna fırlatmaz; rapor ``unreadable`` alanıyla döner,
    böylece tek bozuk dosya bütün denetimi durdurmaz.
    """
    from . import io as poi_io

    try:
        loaded = poi_io.read_poi(path)
    except Exception as exc:
        return FileReport(path=path, rows=0, columns=(), unreadable=f"{type(exc).__name__}: {exc}")

    frame = loaded.frame
    report = FileReport(path=path, rows=len(frame), columns=tuple(frame.columns))

    report.findings += check_required_columns(frame)
    if report.errors:
        return report

    report.findings += check_encoding(loaded.encoding)
    report.findings += check_missing_name(frame, loaded.synthesised_name)
    report.findings += check_missing_type(frame)
    report.findings += check_coordinate_range(frame)
    report.findings += check_precision(frame, min_decimals)
    report.findings += check_exact_duplicates(frame)

    if loaded.synthesised_name:
        report.findings += check_clustering(frame, duplicate_radius_m)
    else:
        report.findings += check_near_duplicates(frame, duplicate_radius_m)

    if bbox is not None:
        report.findings += check_bbox(frame, bbox)

    if loaded.dropped_rows:
        report.findings.append(
            Finding(
                check="okumada_dusen",
                severity=Severity.WARNING,
                message="koordinatı okunamadığı için satır düştü",
                count=loaded.dropped_rows,
            )
        )
    return report


def validate_directory(
    directory: Path,
    bbox: tuple[float, float, float, float] | None = None,
    duplicate_radius_m: float = 50.0,
    min_decimals: int = 5,
    pattern: str = "*.csv",
) -> list[FileReport]:
    """Bir dizindeki bütün POI dosyalarını denetler."""
    return [
        validate_file(path, bbox, duplicate_radius_m, min_decimals)
        for path in sorted(directory.glob(pattern))
    ]
