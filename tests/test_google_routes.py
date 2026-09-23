"""Google Routes istemcisinin testleri — ağa çıkmadan."""

from __future__ import annotations

import json

import pytest

from urbangeoai import google_routes


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.ok = status < 400
        self.content = json.dumps(body).encode()
        self.text = self.content.decode()
        self._body = body

    def json(self):
        return self._body


def test_key_is_read_from_dotenv(tmp_path, monkeypatch):
    for name in google_routes.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("OTHER=1\nGOOGLE_MAPS_API_KEY=abc123\n", encoding="utf-8")
    assert google_routes.load_key(tmp_path) == "abc123"


def test_referrer_blocked_key_is_explained(monkeypatch):
    body = [
        {
            "error": {
                "code": 403,
                "status": "PERMISSION_DENIED",
                "message": "Requests from referer <empty> are blocked.",
                "details": [{"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}],
            }
        }
    ]
    monkeypatch.setattr(google_routes.requests, "post", lambda *a, **k: FakeResponse(403, body))
    with pytest.raises(google_routes.RoutesError) as err:
        google_routes.walking_matrix("k", [(40.4, 49.8)], [(40.41, 49.81)])
    assert err.value.reason == "API_KEY_HTTP_REFERRER_BLOCKED"
    assert "IP" in str(err.value)


def test_successful_matrix_is_parsed(monkeypatch):
    body = [{"originIndex": 0, "destinationIndex": 0, "distanceMeters": 1234, "duration": "900s"}]
    monkeypatch.setattr(google_routes.requests, "post", lambda *a, **k: FakeResponse(200, body))
    (leg,) = google_routes.walking_matrix("k", [(40.4, 49.8)], [(40.41, 49.81)])
    assert (leg.meters, leg.seconds) == (1234, 900.0)
