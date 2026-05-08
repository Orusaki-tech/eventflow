from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


class AbstractPushClient(abc.ABC):
    @abc.abstractmethod
    def schedule_push(
        self,
        *,
        user_id: str,
        title: str,
        body: str,
        trigger_at_iso: str,
    ) -> None:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class NoopPushClient(AbstractPushClient):
    def schedule_push(self, *, user_id: str, title: str, body: str, trigger_at_iso: str) -> None:
        return

