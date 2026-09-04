"""Kategori kataloğunun kendi içinde tutarlı kalmasını sağlayan testler."""

from __future__ import annotations

from urbangeoai import catalogue


def test_catalogue_is_self_consistent():
    """Sessiz tutarsızlık çalışma anında anlaşılmaz hataya dönüşür."""
    assert catalogue.check() == []


def test_every_group_member_has_a_decay_coefficient():
    known = set(catalogue.DECAY)
    for group, members in catalogue.GROUPS.items():
        for member in members:
            assert member in known, f"{group}/{member}"


def test_retired_category_is_not_used_anywhere():
    used = {m for members in catalogue.GROUPS.values() for m in members}
    for name in catalogue.RETIRED:
        assert name not in used
        assert name not in catalogue.SOURCES
        assert name not in catalogue.DECAY


def test_retired_categories_carry_a_reason():
    """Bir kategorinin neden çıkarıldığı, çıkarıldığı kadar önemlidir."""
    for name, reason in catalogue.RETIRED.items():
        assert len(reason) > 30, name


def test_concert_hall_is_retired():
    assert "concert_hall" in catalogue.RETIRED


def test_metro_has_no_file_source():
    """Metro OpenStreetMap'ten gelir, yerel dosyadan değil."""
    assert "metro" in catalogue.DECAY
    assert "metro" not in catalogue.SOURCES


def test_check_detects_a_missing_coefficient(monkeypatch):
    monkeypatch.setitem(catalogue.GROUPS, "test", ["olmayan_kategori"])
    issues = catalogue.check()
    assert any(i.kind == "katsayı yok" for i in issues)


def test_check_detects_use_of_a_retired_category(monkeypatch):
    monkeypatch.setitem(catalogue.GROUPS, "test", ["concert_hall"])
    issues = catalogue.check()
    assert any(i.kind == "emekli kategori" for i in issues)


def test_service_radius_targets_exported_categories():
    for name in catalogue.SERVICE_RADIUS_M:
        assert name in catalogue.DECAY
