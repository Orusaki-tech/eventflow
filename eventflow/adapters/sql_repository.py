from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, desc, insert, select, text, update
from sqlalchemy.orm import Session

from eventflow.adapters.orm import (
    community_event_embeddings,
    community_events,
    device_push_tokens,
    venues,
    oauth_states,
    outbox_messages,
    user_calendar_tokens,
)
from eventflow.adapters.repository import (
    AbstractCalendarTokenRepository,
    AbstractCommunityEventEmbeddingRepository,
    AbstractCommunityEventRepository,
    AbstractDevicePushTokenRepository,
    AbstractDraftRepository,
    AbstractEventRepository,
    AbstractOAuthStateRepository,
    AbstractOutboxRepository,
    AbstractUserLocationRepository,
    CalendarToken,
    CommunityEvent,
    CommunityEventEmbedding,
    DevicePushToken,
    OAuthState,
    OutboxMessage,
    Venue,
    AbstractVenueRepository,
)
from eventflow.auth.token_crypto import decrypt, encrypt
from eventflow.config import get_settings
from eventflow.domain.model import EventDraft, ScheduledEvent, UserLocation


class SqlAlchemyEventRepository(AbstractEventRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _add(self, event: ScheduledEvent) -> None:
        self.session.add(event)

    def _get(self, event_id: UUID) -> Optional[ScheduledEvent]:
        return self.session.get(ScheduledEvent, event_id)

    def _list_upcoming(self, *, user_id: UUID, now: datetime, limit: int) -> list[ScheduledEvent]:
        # Keep this simple: callers that need alert joins should use a read-model view.
        stmt = (
            select(ScheduledEvent)
            .where(ScheduledEvent.user_id == user_id)
            .where(ScheduledEvent.start_time > now)
            .where(ScheduledEvent.cancelled_at.is_(None))
            .order_by(ScheduledEvent.start_time.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())


class SqlAlchemyDraftRepository(AbstractDraftRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _add(self, draft: EventDraft) -> None:
        self.session.add(draft)

    def _get(self, draft_id: UUID) -> Optional[EventDraft]:
        return self.session.get(EventDraft, draft_id)

    def _list_for_user(self, *, user_id: UUID, limit: int) -> list[EventDraft]:
        stmt = (
            select(EventDraft)
            .where(EventDraft.user_id == user_id)
            .order_by(desc(EventDraft.start_time).nulls_last())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())


class SqlAlchemyUserLocationRepository(AbstractUserLocationRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, loc: UserLocation) -> None:
        self.session.merge(loc)

    def _get(self, *, user_id: UUID, label: str) -> Optional[UserLocation]:
        return self.session.get(UserLocation, {"user_id": user_id, "label": label})


class SqlAlchemyDevicePushTokenRepository(AbstractDevicePushTokenRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, token: DevicePushToken) -> DevicePushToken:
        now = datetime.now(timezone.utc)
        values = {
            "id": token.id,
            "user_id": token.user_id,
            "expo_push_token": token.expo_push_token,
            "platform": token.platform,
            "device_id": token.device_id,
            "created_at": token.created_at or now,
            "last_seen_at": token.last_seen_at or now,
            "disabled_at": None,
        }

        stmt = (
            update(device_push_tokens)
            .where(device_push_tokens.c.user_id == token.user_id)
            .where(device_push_tokens.c.expo_push_token == token.expo_push_token)
            .values(
                platform=values["platform"],
                device_id=values["device_id"],
                last_seen_at=values["last_seen_at"],
                disabled_at=None,
            )
            .returning(device_push_tokens.c.id)
        )
        row = self.session.execute(stmt).first()
        if row is None:
            self.session.execute(insert(device_push_tokens).values(**values))
            return token
        token.id = row.id
        token.created_at = values["created_at"]
        token.last_seen_at = values["last_seen_at"]
        token.disabled_at = None
        return token

    def _get(self, *, token_id: UUID) -> DevicePushToken | None:
        row = self.session.execute(
            select(
                device_push_tokens.c.id,
                device_push_tokens.c.user_id,
                device_push_tokens.c.expo_push_token,
                device_push_tokens.c.platform,
                device_push_tokens.c.device_id,
                device_push_tokens.c.created_at,
                device_push_tokens.c.last_seen_at,
                device_push_tokens.c.disabled_at,
            ).where(device_push_tokens.c.id == token_id)
        ).first()
        if row is None:
            return None
        return DevicePushToken(
            id=row.id,
            user_id=row.user_id,
            expo_push_token=row.expo_push_token,
            platform=row.platform,
            device_id=row.device_id,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            disabled_at=row.disabled_at,
        )

    def _list_active(self, *, user_id: UUID) -> list[DevicePushToken]:
        rows = self.session.execute(
            select(
                device_push_tokens.c.id,
                device_push_tokens.c.user_id,
                device_push_tokens.c.expo_push_token,
                device_push_tokens.c.platform,
                device_push_tokens.c.device_id,
                device_push_tokens.c.created_at,
                device_push_tokens.c.last_seen_at,
                device_push_tokens.c.disabled_at,
            )
            .where(device_push_tokens.c.user_id == user_id)
            .where(device_push_tokens.c.disabled_at.is_(None))
            .order_by(device_push_tokens.c.created_at.asc())
        ).all()
        return [
            DevicePushToken(
                id=r.id,
                user_id=r.user_id,
                expo_push_token=r.expo_push_token,
                platform=r.platform,
                device_id=r.device_id,
                created_at=r.created_at,
                last_seen_at=r.last_seen_at,
                disabled_at=r.disabled_at,
            )
            for r in rows
        ]

    def _disable(self, *, token_id: UUID, disabled_at: datetime) -> None:
        self.session.execute(
            update(device_push_tokens)
            .where(device_push_tokens.c.id == token_id)
            .values(disabled_at=disabled_at)
        )

    def _disable_by_expo_token(self, *, expo_push_token: str, disabled_at: datetime) -> None:
        self.session.execute(
            update(device_push_tokens)
            .where(device_push_tokens.c.expo_push_token == expo_push_token)
            .values(disabled_at=disabled_at)
        )


class SqlAlchemyCommunityEventRepository(AbstractCommunityEventRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, evt: CommunityEvent) -> CommunityEvent:
        now = datetime.now(timezone.utc)
        values = {
            "id": evt.id,
            "user_id": evt.user_id,
            "source": evt.source,
            "title": evt.title,
            "start_time": evt.start_time,
            "venue": evt.venue,
            "description": evt.description,
            "poster_image_uri": getattr(evt, "poster_image_uri", None),
            "sponsored_rank": getattr(evt, "sponsored_rank", 0),
            "verified_badge": getattr(evt, "verified_badge", False),
            "created_at": evt.created_at or now,
        }
        stmt = (
            update(community_events)
            .where(community_events.c.id == evt.id)
            .values(
                source=values["source"],
                title=values["title"],
                start_time=values["start_time"],
                venue=values["venue"],
                description=values["description"],
                poster_image_uri=values["poster_image_uri"],
                sponsored_rank=values["sponsored_rank"],
                verified_badge=values["verified_badge"],
            )
        )
        result = self.session.execute(stmt)
        if result.rowcount == 0:
            self.session.execute(insert(community_events).values(**values))
        return evt

    def _get(self, *, community_event_id: UUID) -> CommunityEvent | None:
        row = self.session.execute(
            select(
                community_events.c.id,
                community_events.c.user_id,
                community_events.c.source,
                community_events.c.title,
                community_events.c.start_time,
                community_events.c.venue,
                community_events.c.description,
                community_events.c.poster_image_uri,
                community_events.c.created_at,
                community_events.c.sponsored_rank,
                community_events.c.verified_badge,
            ).where(community_events.c.id == community_event_id)
        ).first()
        if row is None:
            return None
        return CommunityEvent(
            id=row.id,
            user_id=row.user_id,
            source=row.source,
            title=row.title,
            start_time=row.start_time,
            venue=row.venue,
            description=row.description,
            poster_image_uri=row.poster_image_uri,
            sponsored_rank=int(row.sponsored_rank),
            verified_badge=bool(row.verified_badge),
            created_at=row.created_at,
        )


class SqlAlchemyCommunityEventEmbeddingRepository(AbstractCommunityEventEmbeddingRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, emb: CommunityEventEmbedding) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO community_event_embeddings
                    (community_event_id, embedding, embedding_model, embedded_at)
                VALUES
                    (:community_event_id, (:embedding)::vector, :embedding_model, :embedded_at)
                ON CONFLICT (community_event_id) DO UPDATE SET
                    embedding = (:embedding)::vector,
                    embedding_model = EXCLUDED.embedding_model,
                    embedded_at = EXCLUDED.embedded_at
                """
            ),
            {
                "community_event_id": str(emb.community_event_id),
                "embedding": emb.embedding,
                "embedding_model": emb.embedding_model,
                "embedded_at": emb.embedded_at,
            },
        )

class SqlAlchemyCalendarTokenRepository(AbstractCalendarTokenRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, token: CalendarToken) -> None:
        settings = get_settings()
        if not settings.calendar_token_key:
            raise RuntimeError("CALENDAR_TOKEN_KEY not configured")

        scopes_csv = ",".join(token.scopes)
        values = {
            "user_id": token.user_id,
            "provider": token.provider,
            "access_token": encrypt(plaintext=token.access_token, key=settings.calendar_token_key),
            "refresh_token": encrypt(plaintext=token.refresh_token, key=settings.calendar_token_key)
            if token.refresh_token
            else None,
            "token_uri": token.token_uri,
            "scopes": scopes_csv,
            "expiry": token.expiry,
        }

        stmt = (
            update(user_calendar_tokens)
            .where(user_calendar_tokens.c.user_id == token.user_id)
            .values(**values)
        )
        result = self.session.execute(stmt)
        if result.rowcount == 0:
            self.session.execute(insert(user_calendar_tokens).values(**values))

    def _get(self, *, user_id: UUID) -> CalendarToken | None:
        settings = get_settings()
        if not settings.calendar_token_key:
            return None

        row = self.session.execute(
            select(
                user_calendar_tokens.c.user_id,
                user_calendar_tokens.c.provider,
                user_calendar_tokens.c.access_token,
                user_calendar_tokens.c.refresh_token,
                user_calendar_tokens.c.token_uri,
                user_calendar_tokens.c.scopes,
                user_calendar_tokens.c.expiry,
            ).where(user_calendar_tokens.c.user_id == user_id)
        ).first()
        if row is None:
            return None

        scopes = tuple(s for s in (row.scopes or "").split(",") if s)
        return CalendarToken(
            user_id=row.user_id,
            provider=row.provider,
            access_token=decrypt(ciphertext=row.access_token, key=settings.calendar_token_key),
            refresh_token=decrypt(ciphertext=row.refresh_token, key=settings.calendar_token_key)
            if row.refresh_token
            else None,
            token_uri=row.token_uri,
            scopes=scopes,
            expiry=row.expiry,
        )


class SqlAlchemyOAuthStateRepository(AbstractOAuthStateRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _upsert(self, oauth_state: OAuthState) -> None:
        values = {
            "user_id": oauth_state.user_id,
            "provider": oauth_state.provider,
            "state": oauth_state.state,
            "created_at": oauth_state.created_at,
        }
        stmt = (
            update(oauth_states)
            .where(oauth_states.c.user_id == oauth_state.user_id)
            .values(**values)
        )
        result = self.session.execute(stmt)
        if result.rowcount == 0:
            self.session.execute(insert(oauth_states).values(**values))

    def _get(self, *, user_id: UUID, provider: str) -> OAuthState | None:
        row = self.session.execute(
            select(
                oauth_states.c.user_id,
                oauth_states.c.provider,
                oauth_states.c.state,
                oauth_states.c.created_at,
            ).where((oauth_states.c.user_id == user_id) & (oauth_states.c.provider == provider))
        ).first()
        if row is None:
            return None
        return OAuthState(
            user_id=row.user_id,
            provider=row.provider,
            state=row.state,
            created_at=row.created_at,
        )

    def _delete(self, *, user_id: UUID, provider: str) -> None:
        self.session.execute(
            delete(oauth_states).where((oauth_states.c.user_id == user_id) & (oauth_states.c.provider == provider))
        )


class SqlAlchemyOutboxRepository(AbstractOutboxRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _add(self, msg: OutboxMessage) -> None:
        self.session.add(msg)

    def _list_unpublished(self, *, limit: int) -> list[OutboxMessage]:
        rows = self.session.execute(
            select(OutboxMessage)
            .where(outbox_messages.c.published_at.is_(None))
            .order_by(outbox_messages.c.occurred_at.asc())
            .limit(limit)
        ).scalars()
        return list(rows)

    def _claim_batch(
        self,
        *,
        limit: int,
        locked_by: str,
        now: datetime,
        lock_ttl_seconds: int,
        max_attempts: int,
    ) -> list[OutboxMessage]:
        lock_expired_before = now - timedelta(seconds=lock_ttl_seconds)
        # Postgres: SKIP LOCKED allows multiple publishers without double-claiming.
        stmt = (
            select(OutboxMessage)
            .where(outbox_messages.c.published_at.is_(None))
            .where(outbox_messages.c.attempts < max_attempts)
            .where((outbox_messages.c.next_attempt_at.is_(None)) | (outbox_messages.c.next_attempt_at <= now))
            .where((outbox_messages.c.locked_at.is_(None)) | (outbox_messages.c.locked_at <= lock_expired_before))
            .order_by(outbox_messages.c.occurred_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        msgs = list(self.session.execute(stmt).scalars())
        if not msgs:
            return []

        ids = [m.id for m in msgs]
        self.session.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id.in_(ids))
            .values(locked_at=now, locked_by=locked_by)
        )
        return msgs

    def _mark_published(self, *, message_id: UUID, published_at: datetime) -> None:
        self.session.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(published_at=published_at, locked_at=None, locked_by=None, last_error=None)
        )

    def _mark_failed(
        self,
        *,
        message_id: UUID,
        now: datetime,
        attempts: int,
        next_attempt_at: datetime,
        last_error: str,
    ) -> None:
        self.session.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(
                attempts=attempts,
                last_error=last_error[:4000],
                next_attempt_at=next_attempt_at,
                locked_at=now,
            )
        )


class SqlAlchemyVenueRepository(AbstractVenueRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    def _add(self, venue: Venue) -> Venue:
        self.session.add(venue)
        return venue

    def _get(self, *, venue_id: UUID) -> Venue | None:
        return self.session.get(Venue, venue_id)

    def _search(self, *, q: str, limit: int) -> list[Venue]:
        ql = q.strip()
        if not ql:
            return []
        rows = self.session.execute(
            select(Venue)
            .where(venues.c.name.ilike(f"%{ql}%"))
            .order_by(venues.c.name.asc())
            .limit(limit)
        ).scalars()
        return list(rows)

    def _upsert_by_place_id(self, *, venue: Venue) -> Venue:
        # If place_id exists and matches, update; else insert.
        if venue.place_id:
            row = self.session.execute(select(Venue).where(venues.c.place_id == venue.place_id)).scalar_one_or_none()
            if row is not None:
                row.name = venue.name
                row.address = venue.address
                row.lat = venue.lat
                row.lng = venue.lng
                row.updated_by_user_id = venue.updated_by_user_id
                row.updated_at = venue.updated_at
                return row
        self.session.add(venue)
        return venue

