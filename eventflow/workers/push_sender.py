from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import httpx
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class ExpoConfig:
    endpoint: str = "https://exp.host/--/api/v2/push/send"
    timeout_s: float = 10.0


def _expo_headers(*, access_token: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def send_expo_push(
    *,
    access_token: str | None,
    to_tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> list[dict]:
    # Expo supports batching; keep it simple and send one request with N messages.
    msg_body: dict = {"title": title, "body": body}
    if data:
        msg_body["data"] = data
    messages = [{"to": t, **msg_body} for t in to_tokens]
    cfg = ExpoConfig()
    with httpx.Client(timeout=cfg.timeout_s) as client:
        resp = client.post(cfg.endpoint, headers=_expo_headers(access_token=access_token), json=messages)
        resp.raise_for_status()
        data = resp.json()
        # shape: {"data":[{"status":"ok","id":"..." } | {"status":"error","message":...,"details":...}], ...}
        return list(data.get("data") or [])


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for push_sender worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for push_sender worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("push.due")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        payload = json.loads(msg["data"])
        user_id = UUID(payload["user_id"])
        title = payload.get("title") or "EventFlow"
        body = payload.get("body") or ""
        extras: dict[str, str] = {}
        if payload.get("event_id"):
            extras["eventId"] = str(payload["event_id"])
        if payload.get("venue_lat") is not None:
            extras["venueLat"] = str(payload["venue_lat"])
        if payload.get("venue_lng") is not None:
            extras["venueLng"] = str(payload["venue_lng"])
        if payload.get("action"):
            extras["action"] = str(payload["action"])

        with uow:
            tokens = uow.device_push_tokens.list_active(user_id=user_id)
            uow.commit()

        expo_tokens = [t.expo_push_token for t in tokens if t.expo_push_token]
        if not expo_tokens:
            continue

        try:
            results = send_expo_push(
                access_token=settings.expo_access_token,
                to_tokens=expo_tokens,
                title=title,
                body=body,
                data=extras if extras else None,
            )
        except Exception as e:
            logging.exception("expo_push.send_failed", extra={"error": repr(e)})
            continue

        # Best-effort token disabling on common invalid token errors.
        now = datetime.now(timezone.utc)
        invalid = []
        for idx, res in enumerate(results):
            if not isinstance(res, dict):
                continue
            if res.get("status") == "error":
                details = res.get("details") or {}
                err = details.get("error")
                if err in {"DeviceNotRegistered"}:
                    invalid.append(expo_tokens[min(idx, len(expo_tokens) - 1)])

        if invalid:
            with uow:
                for tok in invalid:
                    uow.device_push_tokens.disable_by_expo_token(expo_push_token=tok, disabled_at=now)
                uow.commit()


if __name__ == "__main__":
    main()

