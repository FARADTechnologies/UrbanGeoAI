"""Tekrar temizliğinin kurallarını sabitler.

İki yönlü risk var: aynı yer iki kez kalırsa skor şişer; iki ayrı yer
birleştirilirse gerçek bir hizmet kaybolur. Testler ikisini de kapsar.
"""

from __future__ import annotations

import pandas as pd

from urbangeoai import dedupe, enrich

LAT, LON = 40.3777, 49.8520
METRE = 1 / 111_320


def frame(*rows):
    """(ad, kuzeye metre) çiftlerinden tablo."""
    return pd.DataFrame([{"name": n, "lat": LAT + m * METRE, "lon": LON} for n, m in rows])


def kept(result):
    return sorted(result.kept["name"])


# ── Ad anahtarı ────────────────────────────────────────────────────────────


def test_fold_removes_script_and_letter_differences():
    assert dedupe.fold("Nərgiz") == dedupe.fold("Nargiz") == dedupe.fold("Наргиз")
    assert dedupe.fold("GƏNCLİK") == dedupe.fold("Gənclik")


def test_generic_words_do_not_count_as_name():
    assert dedupe.name_key("Uşaq bağçası").core == frozenset()
    assert dedupe.name_key("Nargiz kafe").core == frozenset({"nargiz"})


def test_numbers_separate_places():
    a, b = dedupe.name_key("Uşaq bağçası 317"), dedupe.name_key("Uşaq bağçası 212")
    assert not dedupe.same_name(a, b)
    same = dedupe.name_key("27 saylı Uşaq Bağçası"), dedupe.name_key("27 saylı Uşaq Bağması")
    assert dedupe.same_name(*same)


def test_number_on_one_side_means_another_branch():
    assert not dedupe.same_name(
        dedupe.name_key("Maya uşaq bağçası 2"), dedupe.name_key("Maya uşaq bağçası")
    )


def test_single_shared_word_is_not_enough():
    assert not dedupe.same_name(
        dedupe.name_key("Arzu restoran"), dedupe.name_key("Arzu şadlıq sarayı")
    )


# ── Temizlik ───────────────────────────────────────────────────────────────


def test_same_name_nearby_is_one_place():
    result = dedupe.dedupe(frame(("Soul Kitchen restoran", 0), ("Soul Kitchen", 20)), "restaurant")
    assert result.after == 1
    assert result.dropped["reason"].iloc[0] == dedupe.REASON_NAME


def test_spelling_variant_is_one_place():
    result = dedupe.dedupe(frame(("Gənclik City restoran", 0), ("Gənlik City", 30)), "restaurant")
    assert result.after == 1


def test_chain_branches_far_apart_stay():
    result = dedupe.dedupe(frame(("Qoç Ət restoran", 0), ("Qoç Ət restoran", 900)), "restaurant")
    assert result.after == 2


def test_different_names_in_same_building_stay():
    result = dedupe.dedupe(frame(("Peekaboo uşaq bağçası", 0), ("America uşaq bağçası", 1)), "kdgr")
    assert result.after == 2


def test_generic_only_names_merge_only_when_very_close():
    close = dedupe.dedupe(frame(("Kafe", 0), ("Kafe", 15)), "coffee")
    far = dedupe.dedupe(frame(("Kafe", 0), ("Kafe", 60)), "coffee")
    assert (close.after, far.after) == (1, 2)


def test_no_chaining_through_a_middle_record():
    """Korpus 4 ≈ ana bina ≈ Korpus 5 → üçü tek kayda inmemeli."""
    rows = frame(
        ("Tibb Universiteti Korpus 4", 0),
        ("Tibb Universiteti", 100),
        ("Tibb Universiteti Korpus 5", 200),
    )
    result = dedupe.dedupe(rows, "univ")
    assert {"Tibb Universiteti Korpus 4", "Tibb Universiteti Korpus 5"} <= set(kept(result))


def test_unnamed_files_only_merge_identical_points():
    rows = frame(("dayanacaq", 0), ("dayanacaq", 0.5), ("dayanacaq", 20))
    result = dedupe.dedupe(rows, "bus", named=False)
    assert result.after == 2, "yolun iki yönündeki iki durak ayrı qalmalı"


def test_bus_stops_with_same_name_stay_separate():
    result = dedupe.dedupe(frame(("Gənclik m/st", 0), ("Gənclik m/st", 26)), "bus")
    assert result.after == 2


def test_longest_name_is_kept():
    result = dedupe.dedupe(frame(("Nağıl", 0), ("Nağıl S uşaq bağçası", 10)), "kdgr")
    assert kept(result) == ["Nağıl S uşaq bağçası"]


def test_has_real_names_detects_file_stem_labels():
    assert not dedupe.has_real_names(frame(("dayanacaq", 0), ("dayanacaq", 50)))
    assert dedupe.has_real_names(frame(("A", 0), ("B", 50)))


def test_cross_food_is_reported_not_removed():
    pool = {
        "coffee": frame(("Şam Bağı kafe", 0)),
        "restaurant": frame(("Şam Bağı restoran", 9)),
    }
    pairs = dedupe.cross_duplicates(pool, enrich.FOOD)
    assert len(pairs) == 1
    assert len(pool["coffee"]) == len(pool["restaurant"]) == 1


# ── OSM ────────────────────────────────────────────────────────────────────


def osm(*rows):
    out = pd.DataFrame(
        [
            {"category": c, "name": n, "alt_names": alt, "lat": LAT + m * METRE, "lon": LON}
            for c, n, alt, m in rows
        ]
    )
    return out.assign(area_m2=0, osm_type="node", osm_id=range(len(out)), osm_value="")


def test_osm_name_match_beyond_distance_radius():
    """Kafe radiusu 30 m; 35 m-də eyni adlı yerli kafe varsa OSM kopyası əlavə olunmur."""
    local = {"coffee": frame(("Nərgiz kafe", 0), ("Başqa", 500))}
    added, results = enrich.compare(local, osm(("coffee", "Cafe Nargiz", "", 35)))
    assert added.empty
    assert next(r for r in results if r.category == "coffee").matched_by_name == 1


def test_osm_alternative_name_is_used():
    local = {"coffee": frame(("Nərgiz kafe", 0), ("Başqa", 500))}
    added, _ = enrich.compare(local, osm(("coffee", "Кафе", "Кафе|Nargiz", 35)))
    assert added.empty


def test_osm_point_and_area_with_different_names_stay():
    both = osm(("coffee", "Alfa", "", 0), ("coffee", "Beta", "", 5))
    assert len(enrich.dedupe_osm(both)) == 2


def test_osm_same_place_tagged_cafe_and_restaurant():
    both = osm(("coffee", "Manqaliya", "", 0), ("restaurant", "MANQALİYA", "", 5))
    report: list = []
    out = enrich.dedupe_osm(both, report=report)
    assert len(out) == 1
    assert report
