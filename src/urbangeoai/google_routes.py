"""Google Routes API ile yürüme mesafesi.

**Şu an kullanılmıyor** (2026-09-28 kararı: Google API ücret nedeniyle iptal,
yaya mesafesi OSRM ile yerelde hesaplanıyor — ``urbangeoai.osrm``). Kod ileride
gerekirse diye duruyor; boru hattı ve panel buna bağlı değil.

Toplu hesap (120 bin hücre) OpenStreetMap yol ağıyla yapılıyor; Google bu
ölçekte çok pahalı. Google iki yerde kullanılır: tek daire raporunda canlı
mesafe, ve OSM yol ağının doğruluğunu örnek noktalarda sınamak.

Anahtar ``GOOGLE_MAPS_API_KEY`` ortam değişkeninden ya da depo kökündeki
``.env`` dosyasından okunur; ``.env`` depoya girmez.

Anahtar Google Cloud'da şöyle ayarlanmalı:
- API kısıtlaması: Routes API
- Uygulama kısıtlaması: IP adresi (sunucu) — web sitesi (HTTP referrer)
  kısıtlamalı bir tarayıcı anahtarı sunucudan çağrılamaz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

ENDPOINT = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
ENV_NAMES = ("GOOGLE_MAPS_API_KEY", "NEXT_PUBLIC_GOOGLE_MAPS_API_KEY")

#: Google'ın hata nedeni → bizim açıklamamız.
REASONS = {
    "API_KEY_HTTP_REFERRER_BLOCKED": (
        "Anahtar web sitesi (HTTP referrer) ile kısıtlı: yalnız belirli sitelerden, tarayıcı "
        "içinden çağrılabiliyor. Sunucudan çağrı için IP kısıtlamalı ayrı bir anahtar gerekir."
    ),
    "API_KEY_SERVICE_BLOCKED": "Anahtarda Routes API izinli değil (API kısıtlamasına eklenmeli).",
    "SERVICE_DISABLED": "Projede Routes API etkin değil (Cloud Console → Routes API → Enable).",
    "BILLING_DISABLED": "Projede faturalandırma kapalı; Routes API faturasız çalışmaz.",
    "API_KEY_INVALID": "Anahtar geçersiz.",
    "API_KEY_IP_ADDRESS_BLOCKED": "Anahtar IP ile kısıtlı ve bu makinenin IP'si listede değil.",
}


class RoutesError(RuntimeError):
    """Google isteği reddettiğinde; ``reason`` Google'ın hata kodudur."""

    def __init__(self, status: int, reason: str, message: str):
        self.status, self.reason = status, reason
        super().__init__(f"{status} {reason}: {REASONS.get(reason, message)}")


def load_key(repo: Path | None = None) -> str | None:
    for name in ENV_NAMES:
        if os.environ.get(name):
            return os.environ[name].strip()
    env = (repo or Path.cwd()) / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() in ENV_NAMES and value.strip():
                return value.strip()
    return None


@dataclass
class Leg:
    origin: int
    destination: int
    meters: float | None
    seconds: float | None


def walking_matrix(
    key: str,
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    timeout: int = 60,
) -> list[Leg]:
    """Başlangıç × varış için yürüme mesafesi (en fazla 25 × 25 = 625 hücre)."""

    def waypoint(p):
        return {"waypoint": {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}}

    response = requests.post(
        ENDPOINT,
        headers={
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration,condition",
            "Content-Type": "application/json",
        },
        json={
            "origins": [waypoint(p) for p in origins],
            "destinations": [waypoint(p) for p in destinations],
            "travelMode": "WALK",
        },
        timeout=timeout,
    )
    if not response.ok:
        body = response.json() if response.content[:1] in (b"{", b"[") else {}
        error = body[0]["error"] if isinstance(body, list) and body else body.get("error", {})
        reason = next(
            (d.get("reason") for d in error.get("details", []) if d.get("reason")),
            error.get("status", ""),
        )
        raise RoutesError(response.status_code, reason or "", error.get("message", response.text))
    legs = []
    for item in response.json():
        seconds = item.get("duration")
        legs.append(
            Leg(
                origin=item.get("originIndex", 0),
                destination=item.get("destinationIndex", 0),
                meters=item.get("distanceMeters"),
                seconds=float(seconds.rstrip("s")) if seconds else None,
            )
        )
    return legs
