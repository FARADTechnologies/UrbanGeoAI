"""Konsol kodlaması düzeltmesinin testleri.

Bu düzeltme olmadan Windows'ta tek bir Türkçe ilerleme satırı bütün üretimi
durduruyordu. Testler iki şeyi sabitler: düzeltme gerçekten uygulanıyor ve
uygulanamadığı yerde yeni bir hata üretmiyor.
"""

from __future__ import annotations

import io

from urbangeoai import console


class Recorder:
    """`reconfigure` çağrısını kaydeden sahte akış."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def reconfigure(self, **kwargs) -> None:
        self.calls.append(kwargs)


class Unsupported:
    """`reconfigure` desteklemeyen akış — yakalanmış çıktıda böyle olur."""


class Failing:
    def reconfigure(self, **kwargs):
        raise ValueError("akış yeniden yapılandırılamaz")


def test_streams_are_switched_to_utf8():
    stream = Recorder()
    console.use_utf8(stream)
    assert stream.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_unsupported_streams_are_skipped():
    """Yakalanmış çıktı yeniden yapılandırılamaz; bu bir hata değil."""
    console.use_utf8(Unsupported())


def test_failures_do_not_propagate():
    """Düzeltme başarısız olsa bile betik çalışmaya devam etmeli."""
    console.use_utf8(Failing())


def test_all_given_streams_are_handled():
    first, second = Recorder(), Recorder()
    console.use_utf8(first, Unsupported(), second)
    assert first.calls and second.calls


def test_turkish_output_survives_a_cp1252_stream():
    """Asıl belirti buydu: cp1252 akışa yazarken UnicodeEncodeError."""
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", newline="")
    console.use_utf8(stream)
    print("ızgara hazırlanıyor… ə", file=stream)
    stream.flush()
    assert "ızgara" in raw.getvalue().decode("utf-8")
