#!/usr/bin/env python
"""UrbanGeoAI API-sini işə salır.

Başqa sistemlər (platforma, qiymətləndirmə modeli) indeksləri bu xidmətdən
alır. Önce ``build_indices.py`` çalışmış olmalı.

Kullanım:
    python scripts/serve_api.py
    python scripts/serve_api.py --port 8080
    python scripts/serve_api.py --bundle out/api --host 0.0.0.0   # bulut (Cloud Run)

``--bundle`` verilirse ham verilere ve Overpass'a ihtiyaç yoktur; paket
``scripts/build_api_bundle.py`` ile hazırlanır. Port ``PORT`` ortam
değişkeninden de alınır (Cloud Run bunu verir).
    → http://127.0.0.1:8000/docs   (interaktiv sənəd)
"""

from __future__ import annotations

import argparse
import os
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
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--bundle", type=Path, help="Hazır API paketi (bulut)")
    args = parser.parse_args()

    import uvicorn  # noqa: PLC0415

    if args.bundle:
        app = api.create_app(
            lambda: api.load_bundle(args.bundle),
            allowed_origins=api.DEFAULT_ORIGINS + api.PRODUCTION_ORIGINS,
        )
    else:
        settings = config.load()
        app = api.create_app(lambda: api.load_store(settings))
    print(f"API: http://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
