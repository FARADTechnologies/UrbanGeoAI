"""POI adlarının itkisiz standartlaştırılması.

Amaç görünüşü düzeltmek, anlamı değiştirmemek. Orijinal ad hiçbir zaman
silinmez; standart ad yanına ayrı bir sütun olarak yazılır.

Yalnız şu farklar düzeltilir — hepsi okuyan için aynı adı verir:

- Unicode normal formu (aynı harfin iki farklı kodlanışı)
- görünmez karakterler ve bölünmez boşluk
- art arda ya da baştaki/sondaki boşluk, noktalamadan önceki boşluk
- tırnak ve tire çeşitleri (« » “ ” → ", – — → -)
- Latin bir sözcüğün içine karışmış Kiril harf: "mәktәb" içindeki ``ә``
  (U+04D9) Kiril'dir, gözle ayırt edilmez ama arama ve eşleştirmede başka bir
  harftir. Yalnız Latin harf de taşıyan sözcüklerde çevrilir; tamamen Kiril
  bir ad ("Кафе Наргиз") olduğu gibi kalır.

Büyük/küçük harfe dokunulmaz: "KFC" ya da "iPhone" bozulurdu.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

#: Kiril harf → görünüşü aynı Latin/Azərbaycan harfi.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
        "і": "i", "ј": "j", "ѕ": "s", "һ": "h", "ә": "ə", "ө": "ö", "ү": "ü",
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
        "Р": "P", "С": "C", "Т": "T", "Х": "X", "Ә": "Ə", "Ө": "Ö", "Ү": "Ü",
        "І": "I", "Ј": "J", "Ѕ": "S", "Һ": "H",
    }
)  # fmt: skip

PUNCTUATION = str.maketrans(
    {
        "«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "″": '"',
        "‘": "'", "’": "'", "‚": "'", "`": "'", "´": "'", "ʼ": "'",
        "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
        " ": " ", " ": " ", " ": " ", "\t": " ",
        "​": "", "‌": "", "‍": "", "﻿": "",
    }
)  # fmt: skip

_WORD = re.compile(r"\w+")
_LATIN = re.compile(r"[A-Za-zƏəÇçĞğİıÖöŞşÜüÂâ]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def _fix_mixed(match: re.Match) -> str:
    word = match.group(0)
    if _LATIN.search(word) and _CYRILLIC.search(word):
        return word.translate(HOMOGLYPHS)
    return word


def standard_name(name) -> str:
    """Adın standart hâli. Boş ya da eksik ad boş dizge döner."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = unicodedata.normalize("NFC", str(name)).translate(PUNCTUATION)
    text = _WORD.sub(_fix_mixed, text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.;:!?)])", r"\1", text)


def standardise(frame: pd.DataFrame, column: str = "name") -> pd.DataFrame:
    """``name_std`` sütununu ekler; orijinal sütun değişmez."""
    if column not in frame.columns:
        return frame
    return frame.assign(name_std=frame[column].map(standard_name))


def changes(frame: pd.DataFrame, column: str = "name") -> pd.DataFrame:
    """Standart adı orijinalinden farklı olan satırlar (önce → sonra)."""
    std = frame[column].map(standard_name)
    original = frame[column].fillna("").astype(str)
    changed = std != original
    return pd.DataFrame({"before": original[changed], "after": std[changed]})


def collisions(frame: pd.DataFrame, column: str = "name") -> pd.DataFrame:
    """Farklı orijinal adların aynı standart ada düştüğü gruplar.

    Standartlaştırma yalnız görünmez farkları sildiği için bu gruplar zaten
    aynı ad olmalı; tablo bunun kanıtı olarak tutulur ve elle okunur.
    """
    original = frame[column].fillna("").astype(str)
    table = pd.DataFrame({"original": original, "std": original.map(standard_name)})
    groups = table.drop_duplicates().groupby("std")["original"].agg(list)
    groups = groups[groups.map(len) > 1]
    return pd.DataFrame({"std": groups.index, "originals": [" | ".join(v) for v in groups]})
