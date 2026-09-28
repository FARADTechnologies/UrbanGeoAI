"""Ad standartlaştırmasının yalnız görünmez farkları sildiğini sabitler."""

from __future__ import annotations

import pandas as pd

from urbangeoai import names


def test_mixed_script_word_is_fixed():
    # "mәktәb": ә burada Kiril U+04D9.
    assert names.standard_name("260 nömrəli tam orta mәktәb") == "260 nömrəli tam orta məktəb"


def test_pure_cyrillic_name_is_kept():
    assert names.standard_name("Кафе Наргиз") == "Кафе Наргиз"


def test_case_is_not_touched():
    assert names.standard_name("KFC") == "KFC"
    assert names.standard_name("TERRACE lounge") == "TERRACE lounge"


def test_spaces_quotes_dashes():
    assert (
        names.standard_name("  «Nargiz»  kafe ,  Bakı – mərkəz ") == '"Nargiz" kafe, Bakı - mərkəz'
    )


def test_invisible_characters_removed():
    assert names.standard_name("Kafe​ Alov") == "Kafe Alov"


def test_decomposed_letters_are_composed():
    decomposed = "Güneş"  # ü iki kod noktası olarak
    assert names.standard_name(decomposed) == "Güneş"


def test_missing_name():
    assert names.standard_name(None) == ""
    assert names.standard_name(float("nan")) == ""


def test_original_column_is_kept():
    frame = pd.DataFrame({"name": ["  Alov  kafe "]})
    out = names.standardise(frame)
    assert out.loc[0, "name"] == "  Alov  kafe "
    assert out.loc[0, "name_std"] == "Alov kafe"


def test_collisions_only_group_trivial_variants():
    frame = pd.DataFrame({"name": ["Alov kafe", "Alov  kafe", "Alov Kafe"]})
    table = names.collisions(frame)
    assert len(table) == 1
    assert "Alov Kafe" not in table.loc[0, "originals"], "böyük hərf fərqi birləşməməli"
