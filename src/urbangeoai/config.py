"""Konfigürasyon yükleme ve doğrulama.

Yollar kaynak koda yazılmaz. Sıralama:

1. ``URBANGEOAI_CONFIG`` ortam değişkeninin gösterdiği dosya
2. Depo kökündeki ``config/paths.yml``
3. Depo kökündeki ``config/paths.example.yml`` (yalnızca varsayılan değerler için)

Doğrudan çalıştırıldığında konfigürasyonu doğrular ve eksik yolları raporlar::

    python -m urbangeoai.config
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "paths.yml"
EXAMPLE_CONFIG = REPO_ROOT / "config" / "paths.example.yml"

ENV_VAR = "URBANGEOAI_CONFIG"


class ConfigError(RuntimeError):
    """Konfigürasyon bulunamadığında veya geçersiz olduğunda."""


@dataclass(frozen=True)
class Paths:
    """Projenin okuduğu ve yazdığı dizinler."""

    raw_current: Path
    raw_previous: Path | None
    reference: Path
    sample: Path
    output: Path
    cache: Path

    def missing(self) -> list[tuple[str, Path]]:
        """Var olması beklenen ama bulunamayan girdi dizinleri."""
        required = [("raw_current", self.raw_current)]
        if self.raw_previous is not None:
            required.append(("raw_previous", self.raw_previous))
        return [(name, p) for name, p in required if not p.exists()]

    def ensure_writable(self) -> None:
        """Çıktı ve önbellek dizinlerini oluştur."""
        for p in (self.output, self.cache, self.reference):
            p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    """Tam konfigürasyon: yollar artı analiz parametreleri."""

    paths: Paths
    bbox: tuple[float, float, float, float]
    h3_resolution: int
    validation: dict[str, Any] = field(default_factory=dict)
    metro: dict[str, Any] = field(default_factory=dict)
    overpass_mirrors: tuple[str, ...] = ()


def _resolve(value: str | os.PathLike[str], base: Path) -> Path:
    """Göreli yolları depo köküne göre çöz, mutlak yolları olduğu gibi bırak."""
    p = Path(os.path.expandvars(str(value))).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def config_path() -> Path:
    """Kullanılacak konfigürasyon dosyasının yolu."""
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser()
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    return EXAMPLE_CONFIG


def load(path: Path | None = None) -> Settings:
    """Konfigürasyonu oku ve doğrula.

    Raises:
        ConfigError: dosya yoksa, okunamıyorsa veya zorunlu alanlar eksikse.
    """
    cfg_file = Path(path) if path is not None else config_path()
    if not cfg_file.exists():
        raise ConfigError(
            f"Konfigürasyon dosyası bulunamadı: {cfg_file}\n"
            f"'{EXAMPLE_CONFIG.name}' dosyasını 'config/paths.yml' olarak "
            f"kopyalayın ve kendi yollarınızı yazın."
        )

    try:
        raw = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Konfigürasyon okunamadı ({cfg_file}): {exc}") from exc

    section = raw.get("paths")
    if not isinstance(section, dict):
        raise ConfigError(f"'paths' bölümü eksik veya hatalı: {cfg_file}")

    for key in ("raw_current", "reference", "output", "cache"):
        if not section.get(key):
            raise ConfigError(f"'paths.{key}' tanımlanmamış: {cfg_file}")

    previous = section.get("raw_previous")
    paths = Paths(
        raw_current=_resolve(section["raw_current"], REPO_ROOT),
        raw_previous=_resolve(previous, REPO_ROOT) if previous else None,
        reference=_resolve(section["reference"], REPO_ROOT),
        sample=_resolve(section.get("sample", "data/sample"), REPO_ROOT),
        output=_resolve(section["output"], REPO_ROOT),
        cache=_resolve(section["cache"], REPO_ROOT),
    )

    grid = raw.get("grid", {})
    bbox = grid.get("bbox", [49.5, 40.2, 50.4, 40.6])
    if len(bbox) != 4:
        raise ConfigError("'grid.bbox' dört değer içermeli: [min_lon, min_lat, max_lon, max_lat]")

    return Settings(
        paths=paths,
        bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        h3_resolution=int(grid.get("h3_resolution", 10)),
        validation=raw.get("validation", {}) or {},
        metro=raw.get("metro", {}) or {},
        overpass_mirrors=tuple(raw.get("overpass", {}).get("mirrors", ())),
    )


def _main() -> int:
    cfg_file = config_path()
    print(f"Konfigürasyon : {cfg_file}")
    if cfg_file == EXAMPLE_CONFIG:
        print("  UYARI: örnek dosya kullanılıyor. 'config/paths.yml' oluşturun.")

    try:
        settings = load()
    except ConfigError as exc:
        print(f"\nHATA: {exc}", file=sys.stderr)
        return 1

    print(f"H3 çözünürlüğü: {settings.h3_resolution}")
    print(f"Sınır kutusu  : {settings.bbox}")
    print("\nYollar:")
    for name in ("raw_current", "raw_previous", "reference", "sample", "output", "cache"):
        value = getattr(settings.paths, name)
        if value is None:
            print(f"  {name:<13} tanımlanmamış (isteğe bağlı)")
            continue
        print(f"  {name:<13} {'var  ' if value.exists() else 'YOK  '} {value}")

    missing = settings.paths.missing()
    if missing:
        print("\nEksik girdi dizinleri:", file=sys.stderr)
        for name, p in missing:
            print(f"  paths.{name}: {p}", file=sys.stderr)
        return 1

    print("\nKonfigürasyon geçerli.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
