#!/usr/bin/env python
"""UrbanGeoAI API-sini işə salır.

Başqa sistemlər (platforma, qiymətləndirmə modeli) indeksləri bu xidmətdən
alır. Önce ``build_indices.py`` çalışmış olmalı.

Kullanım:
    python scripts/serve_api.py
    python scripts/serve_api.py --port 8080
    → http://127.0.0.1:8000/docs   (interaktiv sənəd)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import api, config, console  # noqa: E402


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn  # noqa: PLC0415

    settings = config.load()
    app = api.create_app(lambda: api.load_store(settings))
    print(f"API: http://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
