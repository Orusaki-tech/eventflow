from __future__ import annotations

import abc
from typing import Callable, Iterator, Optional

from sqlalchemy.orm import Session

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
    FakeCalendarTokenRepository,
    FakeCommunityEventEmbeddingRepository,
    FakeCommunityEventRepository,
    FakeDevicePushTokenRepository,
    FakeDraftRepository,
    FakeEventRepository,
    FakeOAuthStateRepository,
    FakeOutboxRepository,
    FakeUserLocationRepository,
    AbstractVenueRepository,
    FakeVenueRepository,
)
from eventflow.adapters.sql_repository import (
    SqlAlchemyCalendarTokenRepository,
    SqlAlchemyCommunityEventEmbeddingRepository,
    SqlAlchemyCommunityEventRepository,
    SqlAlchemyDevicePushTokenRepository,
    SqlAlchemyDraftRepository,
    SqlAlchemyEventRepository,
    SqlAlchemyOAuthStateRepository,
    SqlAlchemyOutboxRepository,
    SqlAlchemyUserLocationRepository,
    SqlAlchemyVenueRepository,
)


class AbstractUnitOfWork(abc.ABC):
    events: AbstractEventRepository
    drafts: AbstractDraftRepository
    user_locations: AbstractUserLocationRepository
    device_push_tokens: AbstractDevicePushTokenRepository
    community_events: AbstractCommunityEventRepository
    community_event_embeddings: AbstractCommunityEventEmbeddingRepository
    calendar_tokens: AbstractCalendarTokenRepository
    oauth_states: AbstractOAuthStateRepository
    outbox: AbstractOutboxRepository
    venues: AbstractVenueRepository

    def __enter__(self) -> "AbstractUnitOfWork":
        return self

    def __exit__(self, *args) -> None:
        self.rollback()

    @abc.abstractmethod
    def commit(self) -> None:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def collect_new_events(self) -> Iterator[object]:
        for entity in list(self.events.seen):
            evts = getattr(entity, "events", None)
            if not evts:
                continue
            while entity.events:
                yield entity.events.pop(0)


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(
        self,
        *,
        events: Optional[FakeEventRepository] = None,
        drafts: Optional[FakeDraftRepository] = None,
        user_locations: Optional[FakeUserLocationRepository] = None,
        device_push_tokens: Optional[FakeDevicePushTokenRepository] = None,
        community_events: Optional[FakeCommunityEventRepository] = None,
        community_event_embeddings: Optional[FakeCommunityEventEmbeddingRepository] = None,
        calendar_tokens: Optional[FakeCalendarTokenRepository] = None,
        oauth_states: Optional[FakeOAuthStateRepository] = None,
        outbox: Optional[FakeOutboxRepository] = None,
        venues: Optional[FakeVenueRepository] = None,
    ) -> None:
        self.events = events or FakeEventRepository()
        self.drafts = drafts or FakeDraftRepository()
        self.user_locations = user_locations or FakeUserLocationRepository()
        self.device_push_tokens = device_push_tokens or FakeDevicePushTokenRepository()
        self.community_events = community_events or FakeCommunityEventRepository()
        self.community_event_embeddings = community_event_embeddings or FakeCommunityEventEmbeddingRepository()
        self.calendar_tokens = calendar_tokens or FakeCalendarTokenRepository()
        self.oauth_states = oauth_states or FakeOAuthStateRepository()
        self.outbox = outbox or FakeOutboxRepository()
        self.venues = venues or FakeVenueRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.events = SqlAlchemyEventRepository(self.session)
        self.drafts = SqlAlchemyDraftRepository(self.session)
        self.user_locations = SqlAlchemyUserLocationRepository(self.session)
        self.device_push_tokens = SqlAlchemyDevicePushTokenRepository(self.session)
        self.community_events = SqlAlchemyCommunityEventRepository(self.session)
        self.community_event_embeddings = SqlAlchemyCommunityEventEmbeddingRepository(self.session)
        self.calendar_tokens = SqlAlchemyCalendarTokenRepository(self.session)
        self.oauth_states = SqlAlchemyOAuthStateRepository(self.session)
        self.outbox = SqlAlchemyOutboxRepository(self.session)
        self.venues = SqlAlchemyVenueRepository(self.session)
        return super().__enter__()

    def __exit__(self, *args) -> None:
        super().__exit__(*args)
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

