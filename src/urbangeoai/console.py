"""Konsol çıktısının Türkçe harfler yüzünden betiği düşürmesini engeller.

Windows'ta Python, çıktı bir dosyaya ya da başka bir programa yönlendirildiğinde
`cp1252` kullanır. Bu kod sayfasında `ı`, `ğ`, `ə` gibi harfler yoktur; tek bir
ilerleme satırı `UnicodeEncodeError` ile bütün üretimi durdurur.

Hata gerçek işin hiçbir yerinde değil — yalnızca ekrana yazarken çıkıyor. Bu
yüzden akış UTF-8'e alınıyor, çevrilemeyen bir karakter kalırsa da yazı
düşürülmüyor, yerine soru işareti konuyor.
"""

from __future__ import annotations

import sys
from typing import IO


def use_utf8(*streams: IO[str]) -> None:
    """Verilen akışları UTF-8'e alır. Akış belirtilmezse stdout ve stderr.

    Yeniden yapılandırmayı desteklemeyen akışlar (yakalanmış çıktı, bazı test
    koşucuları) sessizce atlanır: amaç çıktıyı kurtarmak, yeni bir hata
    üretmek değil.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue
