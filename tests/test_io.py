"""POI okuyucusunun sözleşmesini sabitleyen testler."""

from __future__ import annotations

from pathlib import Path

import pytest

from urbangeoai import io

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalises_long_to_lon():
    """Kaynak dosyalar 'long' kullanıyor; şema 'lon' bekliyor."""
    result = io.read_poi(FIXTURES / "poi_with_defects.csv")
    assert "lon" in result.frame.columns
    assert "long" not in result.frame.columns


def test_coordinates_are_numeric():
    result = io.read_poi(FIXTURES / "poi_with_defects.csv")
    assert result.frame["lat"].dtype.kind == "f"
    assert result.frame["lon"].dtype.kind == "f"


def test_missing_name_column_is_synthesised_not_fatal():
    """Durak ve kamera dosyalarında 'name' yok.

    Önceki uygulama bu dosyalarda KeyError veriyordu. Okuyucu artık dosya
    adından bir etiket üretir ve bunu bildirir.
    """
    result = io.read_poi(FIXTURES / "poi_without_name.csv")
    assert result.synthesised_name is True
    assert "name" in result.frame.columns
    assert (result.frame["name"] == "poi_without_name").all()


def test_name_column_preserved_when_present():
    result = io.read_poi(FIXTURES / "poi_with_defects.csv")
    assert result.synthesised_name is False
    assert result.frame.loc[0, "name"] == "Örnek Məktəb A"


def test_filter_type_is_case_and_whitespace_insensitive():
    result = io.read_poi(FIXTURES / "poi_with_defects.csv")
    lower = io.filter_type(result.frame, "məktəb")
    upper = io.filter_type(result.frame, "  MƏKTƏB  ")
    assert len(lower) == len(upper) == 4


def test_filter_type_requires_type_column():
    result = io.read_poi(FIXTURES / "poi_without_name.csv")
    frame = result.frame.drop(columns=["type"])
    with pytest.raises(ValueError, match="type"):
        io.filter_type(frame, "dayanacaq")


def test_missing_coordinate_column_raises():
    """Koordinat olmadan dosya kullanılamaz; sessizce geçilmemeli."""
    import pandas as pd

    tmp = FIXTURES / "_tmp_no_coords.csv"
    pd.DataFrame({"id": [1], "name": ["x"]}).to_csv(tmp, index=False)
    try:
        with pytest.raises(ValueError, match="koordinat"):
            io.read_poi(tmp)
    finally:
        tmp.unlink()
