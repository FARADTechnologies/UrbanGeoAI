#!/usr/bin/env python
"""POI veri dosyalarının doğruluk denetimini çalıştırır.

Kullanım:
    python scripts/validate_data.py                    # konfigürasyondaki güncel veri
    python scripts/validate_data.py --dir yol/         # belirli bir dizin
    python scripts/validate_data.py --json rapor.json  # makine okunur çıktı
    python scripts/validate_data.py --strict           # hata varsa 1 döndür

Çıkış kodu varsayılan olarak sıfırdır: denetim rapor üretir, kapı görevi
görmez. Kapı davranışı için --strict kullanılır.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import config, console, validation  # noqa: E402


def _print_report(report: validation.FileReport) -> None:
    if report.unreadable:
        print(f"\n{report.path.name}")
        print(f"  OKUNAMADI: {report.unreadable}")
        return

    errors = len(report.errors)
    warnings = len(report.warnings)
    infos = len(report.findings) - errors - warnings

    status = "hata" if errors else ("uyarı" if warnings else "temiz")
    print(f"\n{report.path.name}  —  {report.rows} satır  —  {status}")

    if not report.findings:
        print("  bulgu yok")
        return

    for finding in sorted(report.findings, key=lambda f: (f.severity.value, f.check)):
        print("  " + finding.format())

    if infos and not errors and not warnings:
        print("  (yalnızca bilgi düzeyinde bulgu)")


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, help="Denetlenecek dizin")
    parser.add_argument("--json", type=Path, help="Raporu bu dosyaya JSON olarak yaz")
    parser.add_argument("--strict", action="store_true", help="Hata bulunursa 1 döndür")
    parser.add_argument("--pattern", default="*.csv", help="Dosya deseni")
    args = parser.parse_args()

    try:
        settings = config.load()
    except config.ConfigError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2

    directory = args.dir or settings.paths.raw_current
    if not directory.exists():
        print(f"HATA: dizin yok: {directory}", file=sys.stderr)
        print(
            "config/paths.yml içindeki 'paths.raw_current' değerini kontrol edin.", file=sys.stderr
        )
        return 2

    rules = settings.validation
    reports = validation.validate_directory(
        directory,
        bbox=settings.bbox if rules.get("enforce_bbox", True) else None,
        duplicate_radius_m=float(rules.get("duplicate_radius_m", 50)),
        min_decimals=int(rules.get("min_coordinate_decimals", 5)),
        pattern=args.pattern,
    )

    if not reports:
        print(f"'{args.pattern}' ile eşleşen dosya yok: {directory}")
        return 0

    print("=" * 78)
    print(f"POI DOĞRULUK DENETİMİ  —  {directory}")
    print("=" * 78)

    for report in reports:
        _print_report(report)

    total_errors = sum(len(r.errors) for r in reports)
    total_warnings = sum(len(r.warnings) for r in reports)
    unreadable = sum(1 for r in reports if r.unreadable)
    total_rows = sum(r.rows for r in reports)

    print("\n" + "=" * 78)
    print(
        f"{len(reports)} dosya, {total_rows} satır  —  "
        f"{total_errors} hata, {total_warnings} uyarı, {unreadable} okunamayan"
    )
    print("=" * 78)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "directory": str(directory),
            "summary": {
                "files": len(reports),
                "rows": total_rows,
                "errors": total_errors,
                "warnings": total_warnings,
                "unreadable": unreadable,
            },
            "files": [r.to_dict() for r in reports],
        }
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON rapor: {args.json}")

    return 1 if (args.strict and (total_errors or unreadable)) else 0


if __name__ == "__main__":
    sys.exit(main())
