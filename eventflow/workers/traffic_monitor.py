from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.event_publisher import RedisEventPublisher, RedisEventSubscriber
from eventflow.adapters.maps_client import FakeMapsClient, GoogleMapsClient
from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.domain import commands
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


def main() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for traffic_monitor worker")
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for traffic_monitor worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    publisher = RedisEventPublisher(settings.redis_url)
    subscriber = RedisEventSubscriber(settings.redis_url)

    if settings.google_maps_api_key:
        maps = GoogleMapsClient(api_key=settings.google_maps_api_key)
    else:
        maps = FakeMapsClient()

    def on_due_for_traffic_check(payload: dict) -> None:
        event_id = UUID(payload["event_id"])
        user_id = UUID(payload["user_id"])

        with uow:
            evt = uow.events.get(event_id)
            if evt is None:
                return
            venue = evt.venue
            origin_loc = uow.user_locations.get(user_id, "home")
            origin = origin_loc.address if origin_loc else venue

        now = datetime.now(timezone.utc)
        travel_seconds = maps.estimate_travel_seconds(origin=origin, destination=venue, depart_at=now)
        messagebus.handle_with_publisher(
            commands.ScheduleTrafficAlert(event_id=event_id, user_id=user_id, travel_seconds=travel_seconds),
            uow,
            publisher=publisher,
        )

    subscriber.run_forever(topic="event.due_for_traffic_check", handler=on_due_for_traffic_check)


if __name__ == "__main__":
    main()
