"""Metro tekilleştirme kurallarını sabitleyen testler.

Kaydedilmiş bir Overpass yanıtı kullanılıyor; testler ağ erişimi gerektirmez.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from urbangeoai import metro, osm
from urbangeoai.metro import Decision

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_metro_response.json"


@pytest.fixture(scope="module")
def raw_records() -> list[dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return osm.nodes_to_records(payload)


def _names(report: metro.MetroReport, decision: Decision) -> set[str]:
    return {r.name for r in report.records if r.decision is decision}


# ── Servis noktaları ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["Xocəsən Depo Metro", "Dərnəgül deposu", "Y14", "Y15", "B-4", "Azər Neft Yağ"],
)
def test_service_nodes_are_recognised(name):
    assert metro.is_service_node(name)


@pytest.mark.parametrize(
    "name",
    ["28 May", "Nizami", "İçərişəhər", "Həzi Aslanov", "Memar Əcəmi", "20 Yanvar st."],
)
def test_real_stations_are_not_service_nodes(name):
    assert not metro.is_service_node(name)


def test_service_nodes_are_removed_from_the_real_response(raw_records):
    """İsim kalıbı yalnızca etiketsiz düğümler için devrede.

    Dərnəgül deposu, Y14, Y15 ve B-4 'construction' etiketi taşıdığı için
    daha üstteki kural onları zaten işletme dışı sayıyor. Xocəsən Depo'da
    etiket yok; onu isim kalıbı yakalıyor.
    """
    report = metro.deduplicate(raw_records)
    assert "Xocəsən Depo Metro" in _names(report, Decision.SERVICE)
    assert "Xocəsən Depo Metro" not in {r.name for r in report.kept}


# ── Birebir tekrar ──────────────────────────────────────────────────────────


def test_duplicate_station_is_removed_once(raw_records):
    """Memar Əcəmi ham yanıtta iki düğüm; biri düşmeli."""
    report = metro.deduplicate(raw_records)
    kept = [r for r in report.kept if r.name == "Memar Əcəmi"]
    assert len(kept) == 1
    assert "Memar Əcəmi" in _names(report, Decision.DUPLICATE)


def test_duplicate_radius_is_respected():
    """Yarıçap daraltılınca aynı isimli uzak kayıtlar tekrar sayılmaz."""
    records = [
        {"osm_id": 1, "name": "İstasyon", "lat": 40.4000, "lon": 49.8000},
        {"osm_id": 2, "name": "İstasyon", "lat": 40.4020, "lon": 49.8000},  # ~222 m
    ]
    tight = metro.deduplicate(records, duplicate_radius_m=100, merge_interchanges=False)
    loose = metro.deduplicate(records, duplicate_radius_m=300, merge_interchanges=False)
    assert len(tight.kept) == 2
    assert len(loose.kept) == 1


def test_duplicate_record_names_what_it_merged_into():
    records = [
        {"osm_id": 11, "name": "İstasyon", "lat": 40.4000, "lon": 49.8000},
        {"osm_id": 22, "name": "İstasyon", "lat": 40.4001, "lon": 49.8000},
    ]
    report = metro.deduplicate(records, merge_interchanges=False)
    duplicate = next(r for r in report.records if r.decision is Decision.DUPLICATE)
    assert duplicate.merged_with == "11"


# ── İşletmede olmayan istasyonlar ───────────────────────────────────────────


def test_not_operational_station_is_removed(raw_records):
    report = metro.deduplicate(raw_records, not_operational=("Nəsimi",))
    assert "Nəsimi" in _names(report, Decision.NOT_OPERATIONAL)
    assert "Nəsimi" not in {r.name for r in report.kept}


def test_not_operational_match_ignores_case_and_whitespace(raw_records):
    report = metro.deduplicate(raw_records, not_operational=("  NƏSİMİ  ",))
    kept = {metro.normalise_name(r.name) for r in report.kept}
    assert "nəsimi" not in kept


# ── İsim normalizasyonu ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("İçərişəhər", "içərişəhər"),
        ("İNŞAATÇILAR", "İnşaatçılar"),
        ("Nəsimi", "  NƏSİMİ  "),
        ("Şah İsmayıl Xətai", "şah ismayıl xətai"),
    ],
)
def test_dotted_i_variants_compare_equal(a, b):
    """Azerbaycanca İ harfi casefold ile birleşik noktaya açılıyor.

    Düzeltilmezse aynı istasyonun büyük ve küçük yazılmış iki kaydı
    eşleşmez ve tekilleştirme sessizce çalışmaz.
    """
    assert metro.normalise_name(a) == metro.normalise_name(b)


def test_plain_casefold_would_fail_on_dotted_i():
    """Düzeltmenin neye karşı yapıldığını belgeler."""
    assert "İçərişəhər".casefold() != "içərişəhər"


def test_duplicate_detection_survives_case_difference():
    records = [
        {"osm_id": 1, "name": "İçərişəhər", "lat": 40.4000, "lon": 49.8000},
        {"osm_id": 2, "name": "İÇƏRİŞƏHƏR", "lat": 40.4001, "lon": 49.8000},
    ]
    report = metro.deduplicate(records, merge_interchanges=False)
    assert len(report.kept) == 1


def test_empty_manual_list_still_removes_construction_tagged_nodes(raw_records):
    """Elle liste boş olsa da etiketli düğümler eleniyor.

    Önceki davranış listeye bağlıydı; artık karar verinin kendisinden çıkıyor.
    """
    report = metro.deduplicate(raw_records, not_operational=())
    closed = _names(report, Decision.NOT_OPERATIONAL)
    assert "Məhəmməd Hadi" in closed
    assert all(
        "construction=" in r.reason
        for r in report.records
        if r.decision is Decision.NOT_OPERATIONAL
    )


# ── Aktarma kompleksi ───────────────────────────────────────────────────────


def test_interchange_pair_is_merged_when_enabled(raw_records):
    """28 May ile Cəfər Cabbarlı 35 m arayla; tek erişim noktası."""
    report = metro.deduplicate(raw_records, merge_interchanges=True)
    kept = {r.name for r in report.kept}
    assert not {"28 May", "Cəfər Cabbarlı"} <= kept


def test_interchange_pair_is_kept_separate_when_disabled(raw_records):
    report = metro.deduplicate(raw_records, merge_interchanges=False)
    kept = {r.name for r in report.kept}
    assert {"28 May", "Cəfər Cabbarlı"} <= kept


def test_interchange_decision_records_the_distance(raw_records):
    """Karar gerekçesi denetlenebilir olmalı."""
    report = metro.deduplicate(raw_records, merge_interchanges=True)
    merged = [r for r in report.records if r.decision is Decision.INTERCHANGE]
    assert merged
    assert all("m mesafede" in r.reason for r in merged)
    assert all(r.merged_with for r in merged)


def test_distant_stations_are_never_merged(raw_records):
    """Farklı istasyonlar birleştirilmemeli."""
    report = metro.deduplicate(raw_records, merge_interchanges=True)
    kept = {r.name for r in report.kept}
    assert {"Nizami", "Koroğlu", "Bakmil"} <= kept


# ── Sıralama ve bütünlük ────────────────────────────────────────────────────


def test_every_raw_node_gets_a_decision(raw_records):
    """Hiçbir düğüm sessizce kaybolmamalı."""
    report = metro.deduplicate(raw_records)
    assert len(report.records) == len(raw_records)


def test_service_nodes_are_removed_before_interchange_check():
    """Depo yanındaki gerçek istasyon aktarma sanılmamalı."""
    records = [
        {"osm_id": 1, "name": "Gerçek İstasyon", "lat": 40.4000, "lon": 49.8000},
        {"osm_id": 2, "name": "Xocəsən Depo", "lat": 40.4002, "lon": 49.8000},
    ]
    report = metro.deduplicate(records, merge_interchanges=True)
    assert [r.name for r in report.kept] == ["Gerçek İstasyon"]
    assert "Xocəsən Depo" in _names(report, Decision.SERVICE)


def test_unnamed_node_is_not_kept():
    records = [{"osm_id": 1, "name": None, "lat": 40.4, "lon": 49.8}]
    report = metro.deduplicate(records)
    assert report.kept == []
    assert report.records[0].decision is Decision.UNNAMED


def test_empty_input_produces_empty_report():
    report = metro.deduplicate([])
    assert report.records == []
    assert report.kept == []


# ── Çıktı biçimi ────────────────────────────────────────────────────────────


def test_station_frame_has_scoring_columns(raw_records):
    frame = metro.deduplicate(raw_records).frame()
    assert set(frame.columns) >= {"name", "lat", "lon"}
    assert len(frame) > 0


def test_audit_frame_covers_every_node(raw_records):
    audit = metro.deduplicate(raw_records).audit_frame()
    assert len(audit) == len(raw_records)
    assert audit["reason"].notna().all()


def test_summary_counts_add_up(raw_records):
    report = metro.deduplicate(raw_records)
    assert sum(report.summary().values()) == len(raw_records)


def test_result_is_deterministic(raw_records):
    """Aynı girdi aynı çıktıyı vermeli; sürümler arası karşılaştırma buna dayanıyor."""
    first = metro.deduplicate(raw_records).frame()
    second = metro.deduplicate(raw_records).frame()
    assert first.equals(second)


# ── construction etiketi ────────────────────────────────────────────────────


def test_construction_tag_is_detected():
    assert metro.has_construction_tag({"tags": {"construction": "station"}}) == "station"
    assert metro.has_construction_tag({"tags": {"construction": "yes"}}) == "yes"


def test_node_without_construction_tag_returns_none():
    assert metro.has_construction_tag({"tags": {"railway": "station"}}) is None
    assert metro.has_construction_tag({}) is None


def test_construction_nodes_are_marked_not_operational(raw_records):
    """İşletme durumu tahmin edilmez, veriden okunur."""
    report = metro.deduplicate(raw_records)
    closed = _names(report, Decision.NOT_OPERATIONAL)
    assert {"Məhəmməd Hadi", "Y14", "Y15", "B-4", "Dərnəgül deposu"} <= closed


def test_construction_reason_cites_the_tag(raw_records):
    """Gerekçe kanıta dayanmalı, kalıba değil."""
    report = metro.deduplicate(raw_records)
    hadi = next(r for r in report.records if r.name == "Məhəmməd Hadi")
    assert hadi.decision is Decision.NOT_OPERATIONAL
    assert "construction=station" in hadi.reason


def test_operational_station_is_not_removed_by_construction_rule(raw_records):
    """Nəsimi işletmede (start_date=2008-10-09); silinmemeli."""
    report = metro.deduplicate(raw_records)
    assert "Nəsimi" in {r.name for r in report.kept}


def test_construction_check_runs_before_interchange_merge(raw_records):
    """Kapalı istasyon, yanındaki gerçek istasyonla birleştirilmemeli.

    Məhəmməd Hadi, Həzi Aslanov'a 145 m mesafede. Sıra yanlış olsaydı
    'aktarma kompleksi' diye birleşir ve gerekçe yanlış olurdu.
    """
    report = metro.deduplicate(raw_records, merge_interchanges=True)
    hadi = next(r for r in report.records if r.name == "Məhəmməd Hadi")
    assert hadi.decision is Decision.NOT_OPERATIONAL
    assert "Həzi Aslanov" in {r.name for r in report.kept}


def test_manual_list_still_works_for_untagged_stations():
    """Etiketi olmayan ama kapalı bilinen istasyonlar için elle liste."""
    records = [{"osm_id": 1, "name": "Kapalı İstasyon", "lat": 40.4, "lon": 49.8, "tags": {}}]
    report = metro.deduplicate(records, not_operational=("Kapalı İstasyon",))
    assert report.kept == []
    assert "konfigürasyondaki" in report.records[0].reason
