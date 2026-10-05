"""Tek komutluk boru hattının adım listesini sabitler."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_pipeline", REPO / "scripts" / "run_pipeline.py")
run_pipeline = importlib.util.module_from_spec(_spec)
# dataclass modülü sys.modules'ta arıyor.
sys.modules["run_pipeline"] = run_pipeline
_spec.loader.exec_module(run_pipeline)


def test_every_step_script_exists():
    for step in run_pipeline.STEPS:
        assert (REPO / "scripts" / step.args[0]).exists(), step.args[0]


def test_indices_run_before_anything_that_reads_them():
    keys = [s.key for s in run_pipeline.STEPS]
    assert keys.index("osm") < keys.index("indeksler")
    for later in ("piyada", "bantlar", "h10", "panel", "api"):
        assert keys.index("indeksler") < keys.index(later)
    assert keys.index("piyada") < keys.index("panel")
    assert keys[-1] == "api"
