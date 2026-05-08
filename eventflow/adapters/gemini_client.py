from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ParsedEventDraft:
    title: str
    """UTC-aware datetime when known; None when the model cannot infer time from the source."""
    start_time: datetime | None
    venue: str
    confidence_score: float
    price: str | None = None


class AbstractGeminiClient(abc.ABC):
    @abc.abstractmethod
    def parse_event_image(
        self,
        *,
        image_bytes: bytes,
        content_type: str | None = None,
        reference_calendar_date: date | None = None,
    ) -> ParsedEventDraft:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def parse_event_text(
        self, *, text: str, reference_calendar_date: date | None = None
    ) -> ParsedEventDraft:  # pragma: no cover
        raise NotImplementedError


class FakeGeminiClient(AbstractGeminiClient):
    def __init__(self, parsed: ParsedEventDraft):
        self._parsed = parsed

    def parse_event_image(
        self,
        *,
        image_bytes: bytes,
        content_type: str | None = None,
        reference_calendar_date: date | None = None,
    ) -> ParsedEventDraft:
        return self._parsed

    def parse_event_text(self, *, text: str, reference_calendar_date: date | None = None) -> ParsedEventDraft:
        return self._parsed

