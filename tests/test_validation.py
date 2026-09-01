"""Doğruluk denetimi kontrollerinin davranışını sabitleyen testler.

Test verisi bilinen kusurları taşıyor; her kontrolün onu bulduğu ve temiz
veride yanlış alarm üretmediği ayrı ayrı doğrulanıyor.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from urbangeoai import validation
from urbangeoai.validation import Severity

FIXTURES = Path(__file__).parent / "fixtures"
DEFECTS = FIXTURES / "poi_with_defects.csv"
NO_NAME = FIXTURES / "poi_without_name.csv"
SAMPLE = Path(__file__).parents[1] / "data" / "sample" / "poi_sample.csv"

BAKU_BBOX = (49.5, 40.2, 50.4, 40.6)


def _checks(report: validation.FileReport) -> set[str]:
    return {f.check for f in report.findings}


# ── Dosya düzeyi ────────────────────────────────────────────────────────────


def test_clean_sample_has_no_errors_or_warnings():
    """Örnek veri temiz; denetim yanlış alarm üretmemeli."""
    report = validation.validate_file(SAMPLE, bbox=BAKU_BBOX)
    assert report.errors == []
    assert report.warnings == []


def test_defect_file_is_readable_and_reports_findings():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX)
    assert report.unreadable is None
    assert report.rows == 8
    assert report.findings


def test_unreadable_file_does_not_raise(tmp_path):
    """Tek bozuk dosya bütün denetimi durdurmamalı."""
    broken = tmp_path / "broken.csv"
    broken.write_text("bu bir csv degil\n", encoding="utf-8")
    report = validation.validate_file(broken)
    assert report.unreadable is not None
    assert report.rows == 0


# ── Tekil kontroller ────────────────────────────────────────────────────────


def test_blank_name_is_flagged():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX)
    assert "bos_isim" in _checks(report)


def test_blank_type_is_flagged():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX)
    assert "bos_kategori" in _checks(report)


def test_out_of_bbox_record_is_flagged_with_row():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX)
    finding = next(f for f in report.findings if f.check == "alan_disi")
    assert finding.count == 1
    assert finding.rows  # satır bilgisi olmalı


def test_bbox_check_is_skipped_when_bbox_is_none():
    report = validation.validate_file(DEFECTS, bbox=None)
    assert "alan_disi" not in _checks(report)


def test_low_precision_is_flagged():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX, min_decimals=5)
    assert "dusuk_hassasiyet" in _checks(report)


def test_precision_threshold_is_configurable():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX, min_decimals=1)
    assert "dusuk_hassasiyet" not in _checks(report)


def test_near_duplicate_is_flagged_separately_from_exact():
    """İkisi ayrı raporlanmalı; yorumları farklı."""
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX, duplicate_radius_m=50)
    assert "yakin_tekrar" in _checks(report)
    assert "birebir_tekrar" not in _checks(report)


def test_near_duplicate_radius_is_configurable():
    tight = validation.validate_file(DEFECTS, bbox=BAKU_BBOX, duplicate_radius_m=0.5)
    assert "yakin_tekrar" not in _checks(tight)


def test_missing_name_column_is_info_not_error():
    """Durak ve kamera dosyalarında isim yok; bu bir hata değil."""
    report = validation.validate_file(NO_NAME, bbox=BAKU_BBOX)
    finding = next(f for f in report.findings if f.check == "isim_sutunu")
    assert finding.severity is Severity.INFO
    assert report.errors == []


def test_clustering_reported_for_unnamed_files():
    """İsimsiz dosyada isim karşılaştırılamaz; yoğunluk ölçülür."""
    report = validation.validate_file(NO_NAME, bbox=BAKU_BBOX, duplicate_radius_m=50)
    assert "yakin_kume" in _checks(report)
    assert "yakin_tekrar" not in _checks(report)


# ── Doğrudan fonksiyon testleri ─────────────────────────────────────────────


def test_zero_coordinates_are_an_error():
    frame = pd.DataFrame({"lat": [0.0, 40.4], "lon": [0.0, 49.8], "name": ["a", "b"]})
    findings = validation.check_coordinate_range(frame)
    assert any(f.check == "sifir_koordinat" and f.severity is Severity.ERROR for f in findings)


def test_out_of_range_coordinates_are_an_error():
    frame = pd.DataFrame({"lat": [200.0], "lon": [49.8], "name": ["a"]})
    findings = validation.check_coordinate_range(frame)
    assert any(f.check == "koordinat_araligi" for f in findings)


def test_exact_duplicate_rows_are_an_error():
    frame = pd.DataFrame({"lat": [40.4, 40.4], "lon": [49.8, 49.8], "name": ["Okul", "Okul"]})
    findings = validation.check_exact_duplicates(frame)
    assert any(f.check == "birebir_tekrar" and f.severity is Severity.ERROR for f in findings)


def test_same_coordinate_different_name_is_only_a_warning():
    frame = pd.DataFrame({"lat": [40.4, 40.4], "lon": [49.8, 49.8], "name": ["A", "B"]})
    findings = validation.check_exact_duplicates(frame)
    checks = {f.check for f in findings}
    assert "ayni_koordinat" in checks
    assert "birebir_tekrar" not in checks


def test_all_blank_type_is_error_not_warning():
    """Tek kayıtta boş kategori uyarı, dosyanın tamamında hatadır."""
    frame = pd.DataFrame({"lat": [40.4], "lon": [49.8], "type": [None]})
    findings = validation.check_missing_type(frame)
    assert findings[0].severity is Severity.ERROR


def test_partial_blank_type_is_warning():
    frame = pd.DataFrame({"lat": [40.4, 40.5], "lon": [49.8, 49.9], "type": [None, "park"]})
    findings = validation.check_missing_type(frame)
    assert findings[0].severity is Severity.WARNING


def test_non_utf8_encoding_is_flagged():
    assert validation.check_encoding("ISO-8859-1")
    assert validation.check_encoding("utf-8-sig") == []


def test_missing_coordinate_columns_are_an_error():
    frame = pd.DataFrame({"name": ["a"]})
    findings = validation.check_required_columns(frame)
    assert findings and findings[0].severity is Severity.ERROR


# ── Rapor biçimi ────────────────────────────────────────────────────────────


def test_finding_format_truncates_long_row_lists():
    finding = validation.Finding(
        check="ornek",
        severity=Severity.WARNING,
        message="mesaj",
        count=10,
        rows=tuple(range(10)),
    )
    text = finding.format(max_rows=3)
    assert "+7" in text


def test_report_serialises_to_dict():
    report = validation.validate_file(DEFECTS, bbox=BAKU_BBOX)
    payload = report.to_dict()
    assert payload["file"] == DEFECTS.name
    assert payload["rows"] == 8
    assert isinstance(payload["findings"], list)


def test_validate_directory_reads_every_matching_file():
    reports = validation.validate_directory(FIXTURES, bbox=BAKU_BBOX)
    assert {r.path.name for r in reports} >= {DEFECTS.name, NO_NAME.name}


@pytest.mark.parametrize("radius", [10.0, 50.0, 200.0])
def test_clustering_count_grows_with_radius(radius):
    report = validation.validate_file(NO_NAME, duplicate_radius_m=radius)
    findings = [f for f in report.findings if f.check == "yakin_kume"]
    assert len(findings) <= 1
