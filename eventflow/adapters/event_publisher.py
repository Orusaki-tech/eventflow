from __future__ import annotations

import abc
import json
from dataclasses import dataclass
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Callable, Dict
from uuid import UUID

import redis


class AbstractEventPublisher(abc.ABC):
    @abc.abstractmethod
    def publish(self, *, topic: str, payload: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError


class AbstractEventSubscriber(abc.ABC):
    @abc.abstractmethod
    def run_forever(self, *, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class NoOpEventPublisher(AbstractEventPublisher):
    def publish(self, *, topic: str, payload: Dict[str, Any]) -> None:
        return


class RedisEventPublisher(AbstractEventPublisher):
    def __init__(self, redis_url: str):
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)

    def publish(self, *, topic: str, payload: Dict[str, Any]) -> None:
        self._r.publish(topic, json.dumps(payload))


class RedisEventSubscriber(AbstractEventSubscriber):
    def __init__(self, redis_url: str):
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)

    def run_forever(self, *, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        pubsub = self._r.pubsub()
        pubsub.subscribe(topic)
        for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            data = json.loads(msg["data"])
            handler(data)


def event_to_payload(evt: Any) -> Dict[str, Any]:
    if is_dataclass(evt):
        raw = asdict(evt)
    else:
        raw = dict(getattr(evt, "__dict__", {}))

    def _coerce(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, UUID):
            return str(v)
        return v

    cooked = {k: _coerce(v) for k, v in raw.items()}
    return {"event_type": f"{type(evt).__module__}.{type(evt).__name__}", **cooked}

