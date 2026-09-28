#!/usr/bin/env python
"""Bulutta çalışan API için kendine yeten paketi hazırlar.

Çıktı ``out/api/``: teslim tablosu, model ve hazır POI havuzu. Docker imajı
(``Dockerfile``) bu klasörü kopyalar; sunucu başlarken ham verilere ve
Overpass'a gitmez.

Kullanım:
    python scripts/build_api_bundle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import api, config, console  # noqa: E402


def main() -> int:
    console.use_utf8()
    settings = config.load()
    dest = api.write_bundle(settings, settings.paths.output / "api")
    for path in sorted(dest.iterdir()):
        print(f"  {path.name:<28} {path.stat().st_size / 1e6:6.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
