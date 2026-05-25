from __future__ import annotations

import asyncio
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from PIL import Image
from starlette.datastructures import UploadFile
from starlette.datastructures import Headers

from eventflow.entrypoints.api.routes import share as share_routes


def _valid_png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _FakeRedis:
    get_value: bytes | None = None
    set_calls: list[tuple[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self):
        self.set_calls = []

    def get(self, key: str):
        return self.get_value

    def set(self, key: str, value: str, ex: int | None = None):
        self.set_calls.append((key, value))
        return True


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    def __init__(
        self,
        parsed_json: dict | None = None,
        poster_asset_id: UUID | None = None,
        *,
        poster_content_sha256: str | None = None,
    ):
        self.parsed_json = parsed_json
        self.poster_asset_id = poster_asset_id
        self.poster_content_sha256 = poster_content_sha256 or hashlib.sha256(_valid_png_bytes()).hexdigest()
        self.executed: list[str] = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self.executed.append(sql)
        if "FROM poster_asset_parses" in sql:
            if self.parsed_json is None:
                return _FakeResult(None)
            return _FakeResult((self.parsed_json,))
        if "SELECT content_sha256 FROM poster_assets WHERE id" in sql:
            return _FakeResult((self.poster_content_sha256,))
        if "SELECT id FROM poster_assets" in sql:
            if self.poster_asset_id is None:
                return _FakeResult(None)
            return _FakeResult((self.poster_asset_id,))
        return _FakeResult(None)


class _FakeUow:
    def __init__(self, session: _FakeSession):
        self.session = session
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.committed = True


class _FakePosterStore:
    def put(self, *, content_type: str, image_bytes: bytes):
        return uuid4()


def test_share_poster_cache_hit_does_not_call_gemini(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("DB_URL", "postgresql://example.invalid/db")

    cached_asset_id = uuid4()
    fake_redis = _FakeRedis(get_value=str(cached_asset_id).encode("utf-8"))
    monkeypatch.setattr(share_routes.redis, "Redis", type("R", (), {"from_url": staticmethod(lambda _u: fake_redis)}))

    parsed_json = {
        "title": "T",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "venue": "V",
        "confidence_score": 0.9,
    }
    uow = _FakeUow(_FakeSession(parsed_json=parsed_json))

    called = {"gemini": 0}

    def _no_gemini(*args, **kwargs):
        called["gemini"] += 1
        raise AssertionError("Gemini should not be called on cache hit")

    monkeypatch.setattr(share_routes.handlers, "handle_capture_event_upload_image", _no_gemini)

    def _persist(*, user_id, parsed, uow):
        return {
            "draft_id": uuid4(),
            "title": parsed.title,
            "start_time": parsed.start_time,
            "venue": parsed.venue,
            "confidence_score": parsed.confidence_score,
        }

    monkeypatch.setattr(share_routes.handlers, "persist_draft_from_parsed", _persist)

    up = UploadFile(
        filename="x.jpg",
        file=io.BytesIO(_valid_png_bytes()),
        headers=Headers({"content-type": "image/jpeg"}),
    )
    async def _read():
        return _valid_png_bytes()
    monkeypatch.setattr(up, "read", _read)  # type: ignore[method-assign]

    out = asyncio.run(
        share_routes.share_poster(  # type: ignore[misc]
            file=up,
            source_url="https://example.com/post",
            user_id=uuid4(),
            uow=uow,
            gemini=None,
            store=_FakePosterStore(),
        )
    )

    assert out.poster_asset_id == cached_asset_id
    assert called["gemini"] == 0


def test_share_poster_cache_miss_calls_gemini_once(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("DB_URL", "postgresql://example.invalid/db")

    fake_redis = _FakeRedis(get_value=None)
    monkeypatch.setattr(share_routes.redis, "Redis", type("R", (), {"from_url": staticmethod(lambda _u: fake_redis)}))

    uow = _FakeUow(_FakeSession(parsed_json=None, poster_asset_id=None))

    called = {"gemini": 0}

    def _gemini(*args, **kwargs):
        called["gemini"] += 1
        return {
            "draft_id": uuid4(),
            "title": "T",
            "start_time": datetime.now(timezone.utc),
            "venue": "V",
            "confidence_score": 0.7,
        }

    monkeypatch.setattr(share_routes.handlers, "handle_capture_event_upload_image", _gemini)

    up = UploadFile(
        filename="x.jpg",
        file=io.BytesIO(_valid_png_bytes()),
        headers=Headers({"content-type": "image/jpeg"}),
    )
    async def _read2():
        return _valid_png_bytes()
    monkeypatch.setattr(up, "read", _read2)  # type: ignore[method-assign]

    out = asyncio.run(
        share_routes.share_poster(  # type: ignore[misc]
            file=up,
            source_url=None,
            user_id=uuid4(),
            uow=uow,
            gemini=None,
            store=_FakePosterStore(),
        )
    )

    assert called["gemini"] == 1
    assert isinstance(UUID(str(out.poster_asset_id)), UUID)
