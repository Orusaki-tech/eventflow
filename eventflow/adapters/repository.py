from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Set
from uuid import UUID, uuid4

from eventflow.domain.model import EventDraft, ScheduledEvent, UserLocation


class AbstractRepository(abc.ABC):
    def __init__(self) -> None:
        self.seen: Set[object] = set()


class AbstractEventRepository(AbstractRepository, abc.ABC):
    def add(self, event: ScheduledEvent) -> None:
        self._add(event)
        self.seen.add(event)

    def get(self, event_id: UUID) -> Optional[ScheduledEvent]:
        evt = self._get(event_id)
        if evt is not None:
            self.seen.add(evt)
        return evt

    def list_upcoming(self, *, user_id: UUID, now: datetime, limit: int = 50) -> list[ScheduledEvent]:
        return self._list_upcoming(user_id=user_id, now=now, limit=limit)

    @abc.abstractmethod
    def _add(self, event: ScheduledEvent) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, event_id: UUID) -> Optional[ScheduledEvent]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _list_upcoming(self, *, user_id: UUID, now: datetime, limit: int) -> list[ScheduledEvent]:  # pragma: no cover
        raise NotImplementedError


class AbstractDraftRepository(AbstractRepository, abc.ABC):
    def add(self, draft: EventDraft) -> None:
        self._add(draft)
        self.seen.add(draft)

    def get(self, draft_id: UUID) -> Optional[EventDraft]:
        d = self._get(draft_id)
        if d is not None:
            self.seen.add(d)
        return d

    def list_for_user(self, *, user_id: UUID, limit: int = 50) -> list[EventDraft]:
        return self._list_for_user(user_id=user_id, limit=limit)

    @abc.abstractmethod
    def _add(self, draft: EventDraft) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, draft_id: UUID) -> Optional[EventDraft]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _list_for_user(self, *, user_id: UUID, limit: int) -> list[EventDraft]:  # pragma: no cover
        raise NotImplementedError


class AbstractUserLocationRepository(AbstractRepository, abc.ABC):
    def upsert(self, loc: UserLocation) -> None:
        self._upsert(loc)
        self.seen.add(loc)

    def get(self, user_id: UUID, label: str) -> Optional[UserLocation]:
        loc = self._get(user_id=user_id, label=label)
        if loc is not None:
            self.seen.add(loc)
        return loc

    @abc.abstractmethod
    def _upsert(self, loc: UserLocation) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, user_id: UUID, label: str) -> Optional[UserLocation]:  # pragma: no cover
        raise NotImplementedError


class FakeEventRepository(AbstractEventRepository):
    def __init__(self, events: Iterable[ScheduledEvent] = ()) -> None:
        super().__init__()
        self._events: Dict[UUID, ScheduledEvent] = {e.id: e for e in events}

    def _add(self, event: ScheduledEvent) -> None:
        self._events[event.id] = event

    def _get(self, event_id: UUID) -> Optional[ScheduledEvent]:
        return self._events.get(event_id)

    def _list_upcoming(self, *, user_id: UUID, now: datetime, limit: int) -> list[ScheduledEvent]:
        items = [
            e
            for e in self._events.values()
            if e.user_id == user_id
            and e.start_time > now
            and getattr(e, "cancelled_at", None) is None
        ]
        items.sort(key=lambda e: e.start_time)
        return items[:limit]


class FakeDraftRepository(AbstractDraftRepository):
    def __init__(self, drafts: Iterable[EventDraft] = ()) -> None:
        super().__init__()
        self._drafts: Dict[UUID, EventDraft] = {d.id: d for d in drafts}

    def _add(self, draft: EventDraft) -> None:
        self._drafts[draft.id] = draft

    def _get(self, draft_id: UUID) -> Optional[EventDraft]:
        return self._drafts.get(draft_id)

    def _list_for_user(self, *, user_id: UUID, limit: int) -> list[EventDraft]:
        items = [d for d in self._drafts.values() if d.user_id == user_id]
        items.sort(
            key=lambda d: (
                d.start_time is None,
                -(d.start_time.timestamp()) if d.start_time is not None else 0,
            )
        )
        return items[:limit]


class FakeUserLocationRepository(AbstractUserLocationRepository):
    def __init__(self, locations: Iterable[UserLocation] = ()) -> None:
        super().__init__()
        self._locations: Dict[tuple[UUID, str], UserLocation] = {(l.user_id, l.label): l for l in locations}

    def _upsert(self, loc: UserLocation) -> None:
        self._locations[(loc.user_id, loc.label)] = loc

    def _get(self, *, user_id: UUID, label: str) -> Optional[UserLocation]:
        return self._locations.get((user_id, label))


@dataclass
class DevicePushToken:
    user_id: UUID
    expo_push_token: str
    platform: str | None = None  # "ios" | "android"
    device_id: str | None = None
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    disabled_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


class AbstractDevicePushTokenRepository(AbstractRepository, abc.ABC):
    def upsert(self, token: DevicePushToken) -> DevicePushToken:
        return self._upsert(token)

    def get(self, *, token_id: UUID) -> DevicePushToken | None:
        return self._get(token_id=token_id)

    def list_active(self, *, user_id: UUID) -> list[DevicePushToken]:
        return self._list_active(user_id=user_id)

    def disable(self, *, token_id: UUID, disabled_at: datetime) -> None:
        self._disable(token_id=token_id, disabled_at=disabled_at)

    def disable_by_expo_token(self, *, expo_push_token: str, disabled_at: datetime) -> None:
        self._disable_by_expo_token(expo_push_token=expo_push_token, disabled_at=disabled_at)

    @abc.abstractmethod
    def _upsert(self, token: DevicePushToken) -> DevicePushToken:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, token_id: UUID) -> DevicePushToken | None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _list_active(self, *, user_id: UUID) -> list[DevicePushToken]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _disable(self, *, token_id: UUID, disabled_at: datetime) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _disable_by_expo_token(self, *, expo_push_token: str, disabled_at: datetime) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeDevicePushTokenRepository(AbstractDevicePushTokenRepository):
    def __init__(self, tokens: Iterable[DevicePushToken] = ()) -> None:
        super().__init__()
        self._tokens: Dict[UUID, DevicePushToken] = {t.id: t for t in tokens}

    def _upsert(self, token: DevicePushToken) -> DevicePushToken:
        # Unique by (user_id, expo_push_token): if exists, update last_seen_at + metadata.
        for existing in self._tokens.values():
            if existing.user_id == token.user_id and existing.expo_push_token == token.expo_push_token:
                existing.platform = token.platform
                existing.device_id = token.device_id
                existing.last_seen_at = token.last_seen_at
                existing.disabled_at = None
                return existing
        self._tokens[token.id] = token
        return token

    def _get(self, *, token_id: UUID) -> DevicePushToken | None:
        return self._tokens.get(token_id)

    def _list_active(self, *, user_id: UUID) -> list[DevicePushToken]:
        return [t for t in self._tokens.values() if t.user_id == user_id and t.disabled_at is None]

    def _disable(self, *, token_id: UUID, disabled_at: datetime) -> None:
        tok = self._tokens.get(token_id)
        if tok is None:
            return
        tok.disabled_at = disabled_at

    def _disable_by_expo_token(self, *, expo_push_token: str, disabled_at: datetime) -> None:
        for tok in self._tokens.values():
            if tok.expo_push_token == expo_push_token:
                tok.disabled_at = disabled_at


@dataclass
class CommunityEvent:
    user_id: UUID
    source: str
    title: str
    start_time: datetime
    venue: str
    description: str | None = None
    poster_image_uri: str | None = None
    sponsored_rank: int = 0
    verified_badge: bool = False
    created_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class CommunityEventEmbedding:
    community_event_id: UUID
    embedding: str  # vector literal string, e.g. "[0.1,0.2,...]"
    embedding_model: str
    embedded_at: datetime


class AbstractCommunityEventRepository(AbstractRepository, abc.ABC):
    def upsert(self, evt: CommunityEvent) -> CommunityEvent:
        return self._upsert(evt)

    def get(self, *, community_event_id: UUID) -> CommunityEvent | None:
        return self._get(community_event_id=community_event_id)

    @abc.abstractmethod
    def _upsert(self, evt: CommunityEvent) -> CommunityEvent:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, community_event_id: UUID) -> CommunityEvent | None:  # pragma: no cover
        raise NotImplementedError


class AbstractCommunityEventEmbeddingRepository(AbstractRepository, abc.ABC):
    def upsert(self, emb: CommunityEventEmbedding) -> None:
        self._upsert(emb)

    @abc.abstractmethod
    def _upsert(self, emb: CommunityEventEmbedding) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeCommunityEventRepository(AbstractCommunityEventRepository):
    def __init__(self, events: Iterable[CommunityEvent] = ()) -> None:
        super().__init__()
        self._events: Dict[UUID, CommunityEvent] = {e.id: e for e in events}

    def _upsert(self, evt: CommunityEvent) -> CommunityEvent:
        self._events[evt.id] = evt
        return evt

    def _get(self, *, community_event_id: UUID) -> CommunityEvent | None:
        return self._events.get(community_event_id)


class FakeCommunityEventEmbeddingRepository(AbstractCommunityEventEmbeddingRepository):
    def __init__(self) -> None:
        super().__init__()
        self._embeddings: Dict[UUID, CommunityEventEmbedding] = {}

    def _upsert(self, emb: CommunityEventEmbedding) -> None:
        self._embeddings[emb.community_event_id] = emb


@dataclass(frozen=True)
class CalendarToken:
    user_id: UUID
    provider: str  # "google"
    access_token: str
    refresh_token: str | None
    token_uri: str
    scopes: tuple[str, ...]
    expiry: datetime | None = None


class AbstractCalendarTokenRepository(AbstractRepository, abc.ABC):
    def upsert(self, token: CalendarToken) -> None:
        self._upsert(token)
        self.seen.add(token)

    def get(self, user_id: UUID) -> CalendarToken | None:
        tok = self._get(user_id=user_id)
        if tok is not None:
            self.seen.add(tok)
        return tok

    @abc.abstractmethod
    def _upsert(self, token: CalendarToken) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, user_id: UUID) -> CalendarToken | None:  # pragma: no cover
        raise NotImplementedError


class FakeCalendarTokenRepository(AbstractCalendarTokenRepository):
    def __init__(self, tokens: Iterable[CalendarToken] = ()) -> None:
        super().__init__()
        self._tokens: Dict[UUID, CalendarToken] = {t.user_id: t for t in tokens}

    def _upsert(self, token: CalendarToken) -> None:
        self._tokens[token.user_id] = token

    def _get(self, *, user_id: UUID) -> CalendarToken | None:
        return self._tokens.get(user_id)


@dataclass(frozen=True)
class OAuthState:
    user_id: UUID
    provider: str
    state: str
    created_at: datetime


class AbstractOAuthStateRepository(AbstractRepository, abc.ABC):
    def upsert(self, oauth_state: OAuthState) -> None:
        self._upsert(oauth_state)
        self.seen.add(oauth_state)

    def get(self, *, user_id: UUID, provider: str) -> OAuthState | None:
        st = self._get(user_id=user_id, provider=provider)
        if st is not None:
            self.seen.add(st)
        return st

    def delete(self, *, user_id: UUID, provider: str) -> None:
        self._delete(user_id=user_id, provider=provider)

    @abc.abstractmethod
    def _upsert(self, oauth_state: OAuthState) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, user_id: UUID, provider: str) -> OAuthState | None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _delete(self, *, user_id: UUID, provider: str) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeOAuthStateRepository(AbstractOAuthStateRepository):
    def __init__(self, states: Iterable[OAuthState] = ()) -> None:
        super().__init__()
        self._states: Dict[tuple[UUID, str], OAuthState] = {(s.user_id, s.provider): s for s in states}

    def _upsert(self, oauth_state: OAuthState) -> None:
        self._states[(oauth_state.user_id, oauth_state.provider)] = oauth_state

    def _get(self, *, user_id: UUID, provider: str) -> OAuthState | None:
        return self._states.get((user_id, provider))

    def _delete(self, *, user_id: UUID, provider: str) -> None:
        self._states.pop((user_id, provider), None)


@dataclass
class Group:
    name: str
    owner_user_id: UUID
    group_type: str = "friend"
    invite_token: str | None = None
    pinned_event_id: UUID | None = None
    created_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class GroupMembership:
    group_id: UUID
    user_id: UUID
    role: str  # "owner" | "member"
    created_at: datetime


@dataclass
class EventShare:
    event_id: UUID
    group_id: UUID
    shared_by_user_id: UUID
    created_at: datetime


@dataclass
class Venue:
    name: str
    lat: float
    lng: float
    address: str | None = None
    place_id: str | None = None
    created_by_user_id: UUID | None = None
    updated_by_user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


class AbstractVenueRepository(AbstractRepository, abc.ABC):
    def add(self, venue: Venue) -> Venue:
        return self._add(venue)

    def get(self, *, venue_id: UUID) -> Venue | None:
        return self._get(venue_id=venue_id)

    def search(self, *, q: str, limit: int = 10) -> list[Venue]:
        return self._search(q=q, limit=limit)

    def upsert_by_place_id(self, *, venue: Venue) -> Venue:
        return self._upsert_by_place_id(venue=venue)

    @abc.abstractmethod
    def _add(self, venue: Venue) -> Venue:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, *, venue_id: UUID) -> Venue | None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _search(self, *, q: str, limit: int) -> list[Venue]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _upsert_by_place_id(self, *, venue: Venue) -> Venue:  # pragma: no cover
        raise NotImplementedError


class FakeVenueRepository(AbstractVenueRepository):
    def __init__(self, venues: Iterable[Venue] = ()) -> None:
        super().__init__()
        self._venues: Dict[UUID, Venue] = {v.id: v for v in venues}

    def _add(self, venue: Venue) -> Venue:
        self._venues[venue.id] = venue
        return venue

    def _get(self, *, venue_id: UUID) -> Venue | None:
        return self._venues.get(venue_id)

    def _search(self, *, q: str, limit: int) -> list[Venue]:
        ql = q.lower().strip()
        out = [v for v in self._venues.values() if ql in (v.name or "").lower()]
        return out[:limit]

    def _upsert_by_place_id(self, *, venue: Venue) -> Venue:
        if venue.place_id:
            for v in self._venues.values():
                if v.place_id == venue.place_id:
                    v.name = venue.name
                    v.address = venue.address
                    v.lat = venue.lat
                    v.lng = venue.lng
                    v.updated_by_user_id = venue.updated_by_user_id
                    v.updated_at = venue.updated_at
                    return v
        return self._add(venue)


@dataclass
class OutboxMessage:
    topic: str
    payload: Dict[str, Any]
    occurred_at: datetime
    id: UUID = field(default_factory=uuid4)
    published_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: datetime | None = None
    locked_at: datetime | None = None
    locked_by: str | None = None


class AbstractOutboxRepository(AbstractRepository, abc.ABC):
    def add(self, msg: OutboxMessage) -> None:
        self._add(msg)

    def list_unpublished(self, *, limit: int = 100) -> list[OutboxMessage]:
        return self._list_unpublished(limit=limit)

    def claim_batch(
        self,
        *,
        limit: int = 100,
        locked_by: str,
        now: datetime,
        lock_ttl_seconds: int = 60,
        max_attempts: int = 20,
    ) -> list[OutboxMessage]:
        return self._claim_batch(
            limit=limit,
            locked_by=locked_by,
            now=now,
            lock_ttl_seconds=lock_ttl_seconds,
            max_attempts=max_attempts,
        )

    def mark_published(self, *, message_id: UUID, published_at: datetime) -> None:
        self._mark_published(message_id=message_id, published_at=published_at)

    def mark_failed(self, *, message_id: UUID, now: datetime, attempts: int, next_attempt_at: datetime, last_error: str) -> None:
        self._mark_failed(
            message_id=message_id,
            now=now,
            attempts=attempts,
            next_attempt_at=next_attempt_at,
            last_error=last_error,
        )

    @abc.abstractmethod
    def _add(self, msg: OutboxMessage) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _list_unpublished(self, *, limit: int) -> list[OutboxMessage]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _claim_batch(
        self,
        *,
        limit: int,
        locked_by: str,
        now: datetime,
        lock_ttl_seconds: int,
        max_attempts: int,
    ) -> list[OutboxMessage]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _mark_published(self, *, message_id: UUID, published_at: datetime) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def _mark_failed(
        self,
        *,
        message_id: UUID,
        now: datetime,
        attempts: int,
        next_attempt_at: datetime,
        last_error: str,
    ) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeOutboxRepository(AbstractOutboxRepository):
    def __init__(self, messages: Iterable[OutboxMessage] = ()) -> None:
        super().__init__()
        self._messages: Dict[UUID, OutboxMessage] = {m.id: m for m in messages}

    def _add(self, msg: OutboxMessage) -> None:
        self._messages[msg.id] = msg

    def _list_unpublished(self, *, limit: int) -> list[OutboxMessage]:
        items = [m for m in self._messages.values() if m.published_at is None]
        items.sort(key=lambda m: m.occurred_at)
        return items[:limit]

    def _claim_batch(
        self,
        *,
        limit: int,
        locked_by: str,
        now: datetime,
        lock_ttl_seconds: int,
        max_attempts: int,
    ) -> list[OutboxMessage]:
        items: list[OutboxMessage] = []
        for msg in self._messages.values():
            if msg.published_at is not None:
                continue
            if msg.attempts >= max_attempts:
                continue
            if msg.next_attempt_at is not None and msg.next_attempt_at > now:
                continue
            if msg.locked_at is not None and (now - msg.locked_at).total_seconds() < lock_ttl_seconds:
                continue
            items.append(msg)
        items.sort(key=lambda m: m.occurred_at)
        claimed = items[:limit]
        for m in claimed:
            m.locked_at = now
            m.locked_by = locked_by
        return claimed

    def _mark_published(self, *, message_id: UUID, published_at: datetime) -> None:
        msg = self._messages.get(message_id)
        if msg is None:
            return
        msg.published_at = published_at

    def _mark_failed(
        self,
        *,
        message_id: UUID,
        now: datetime,
        attempts: int,
        next_attempt_at: datetime,
        last_error: str,
    ) -> None:
        msg = self._messages.get(message_id)
        if msg is None:
            return
        msg.attempts = attempts
        msg.last_error = last_error
        msg.next_attempt_at = next_attempt_at
        msg.locked_at = now

