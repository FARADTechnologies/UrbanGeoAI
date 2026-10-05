#!/usr/bin/env python
"""Bütün boru hattını sırayla çalıştırır (yerel bilgisayarda).

Sıra:

1. OSM zenginleştirme        enrich_osm.py
2. Tekrar ve ad raporu       check_duplicates.py
3. İndeksler (teslim tablosu) build_indices.py
4. Piyada skorları (OSRM)    build_walking.py
5. 1–10 bant kontrolü        check_bands.py
6. H10 kontrolü              verify_h10.py
7. Sürüm karşılaştırması     compare_versions.py   (önceki sürüm varsa)
8. Ekip karşılaştırması      compare_team.py       (ekibin 2025 dosyaları varsa)
9. Panel verisi              build_web_data.py
10. API paketi               build_api_bundle.py

Piyada adımı çalışan bir OSRM sunucusu ister (bkz. OSRM kurulum talimatı).
OSRM yoksa ``--no-walking`` ile mevcut ``out/walk_scores.csv`` korunur.

Kullanım:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --no-walking
    python scripts/run_pipeline.py --from indeksler
    python scripts/run_pipeline.py --list
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import config, console, osrm  # noqa: E402


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    args: tuple[str, ...]


STEPS: tuple[Step, ...] = (
    Step("osm", "OSM zenginleştirme", ("enrich_osm.py",)),
    Step("tekrar", "Tekrar ve ad raporu", ("check_duplicates.py",)),
    Step("indeksler", "İndeksler", ("build_indices.py",)),
    Step("piyada", "Piyada skorları (OSRM)", ("build_walking.py",)),
    Step("bantlar", "1–10 bant kontrolü", ("check_bands.py",)),
    Step("h10", "H10 kontrolü", ("verify_h10.py",)),
    Step(
        "surum", "Sürüm karşılaştırması", ("compare_versions.py", "--json", "{out}/comparison.json")
    ),
    Step("ekip", "Ekip karşılaştırması", ("compare_team.py",)),
    Step("panel", "Panel verisi", ("build_web_data.py",)),
    Step("api", "API paketi", ("build_api_bundle.py",)),
)


def skip_reason(step: Step, settings, args) -> str | None:
    """Adım atlanacaksa nedeni; çalışacaksa None."""
    if step.key == "piyada":
        if args.no_walking:
            return "--no-walking (mevcut out/walk_scores.csv korunuyor)"
        return None
    previous = settings.paths.raw_previous
    if step.key == "surum" and (previous is None or not previous.exists()):
        return "önceki veri sürümü yok (paths.raw_previous)"
    if step.key == "ekip":
        team = None if previous is None else previous / "calculated poi scores"
        if team is None or not (team / "poi_pca.csv").exists():
            return "ekibin 2025 dosyaları yok (calculated poi scores/)"
    return None


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-walking", action="store_true", help="Piyada adımını atla")
    parser.add_argument(
        "--from", dest="start", choices=[s.key for s in STEPS], help="Bu adımdan başla"
    )
    parser.add_argument("--list", action="store_true", help="Adımları listele")
    args = parser.parse_args()

    if args.list:
        for i, step in enumerate(STEPS, 1):
            print(f"{i:>2}. {step.key:<10} {step.title:<28} {' '.join(step.args)}")
        return 0

    settings = config.load()
    keys = [s.key for s in STEPS]
    steps = STEPS[keys.index(args.start) :] if args.start else STEPS

    if any(s.key == "piyada" for s in steps) and not args.no_walking:
        if not osrm.OSRMClient().alive():
            print(
                f"HATA: OSRM {osrm.DEFAULT_URL} adresinde cevap vermiyor.\n"
                "  Kurulum talimatına bakın ya da --no-walking ile piyada adımını atlayın.",
                file=sys.stderr,
            )
            return 2

    started = time.time()
    for i, step in enumerate(steps, 1):
        reason = skip_reason(step, settings, args)
        header = f"[{i}/{len(steps)}] {step.title}"
        if reason:
            print(f"\n{header} — atlandı: {reason}")
            continue
        print(f"\n{header}")
        t = time.time()
        command = [
            sys.executable,
            str(REPO / "scripts" / step.args[0]),
            *(a.format(out=settings.paths.output) for a in step.args[1:]),
        ]
        result = subprocess.run(command, cwd=REPO)
        if result.returncode != 0:
            print(
                f"\nHATA: '{step.title}' adımı {result.returncode} koduyla bitti.", file=sys.stderr
            )
            print(f"  Düzeltip kaldığınız yerden: --from {step.key}", file=sys.stderr)
            return result.returncode
        print(f"  ✓ {time.time() - t:.0f} sn")

    print(f"\nBitti · {(time.time() - started) / 60:.1f} dk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
