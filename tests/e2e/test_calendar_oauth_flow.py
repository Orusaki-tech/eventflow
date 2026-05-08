from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from eventflow.config import get_settings
from eventflow.entrypoints import dependencies
from eventflow.entrypoints.fastapi_app import create_app
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


class _FakeCreds:
    def __init__(self) -> None:
        self.token = "access-123"
        self.refresh_token = "refresh-123"
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.scopes = ["https://www.googleapis.com/auth/calendar.events"]
        self.expiry = datetime.now(timezone.utc)


class _FakeFlow:
    def __init__(self, *, state: str | None = None) -> None:
        self.redirect_uri: str | None = None
        self._state = state
        self.credentials = _FakeCreds()

    @classmethod
    def from_client_config(cls, _client_config, *, scopes, state=None):  # noqa: ANN001
        return cls(state=state)

    def authorization_url(self, **kwargs):  # noqa: ANN003
        # Match google-auth-oauthlib's (url, state) shape.
        state = kwargs.get("state") or self._state or "state-123"
        return (f"https://example.test/oauth?state={state}", state)

    def fetch_token(self, *, code: str) -> None:
        assert code == "code-123"


def test_calendar_oauth_start_and_callback_persist_token(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"installed":{"client_id":"x","client_secret":"y"}}')
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/google/calendar/callback",
    )

    # Patch Flow used by the router module.
    import eventflow.entrypoints.api.routes.calendar_oauth as calendar_oauth_module

    monkeypatch.setattr(calendar_oauth_module, "Flow", _FakeFlow)

    app = create_app()
    user_id = uuid4()
    uow = FakeUnitOfWork()
    app.dependency_overrides[dependencies.get_uow] = lambda: uow
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: user_id

    client = TestClient(app)

    r1 = client.get("/api/v1/auth/google/calendar/start", follow_redirects=False)
    assert r1.status_code == 307
    assert "location" in {k.lower() for k in r1.headers.keys()}

    expected_state = uow.oauth_states.get(user_id=user_id, provider="google")
    assert expected_state is not None

    r2 = client.get(
        "/api/v1/auth/google/calendar/callback",
        params={"code": "code-123", "state": expected_state.state},
    )
    assert r2.status_code == 200

    token = uow.calendar_tokens.get(user_id=user_id)
    assert token is not None
    assert token.access_token == "access-123"
    assert token.refresh_token == "refresh-123"
    assert token.provider == "google"

    # State should be one-time use.
    assert uow.oauth_states.get(user_id=user_id, provider="google") is None

