from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Type

from eventflow.domain import commands, events
from eventflow.adapters.event_publisher import AbstractEventPublisher, NoOpEventPublisher, event_to_payload
from eventflow.adapters.repository import OutboxMessage
from eventflow.service_layer import handlers
from eventflow.service_layer.unit_of_work import AbstractUnitOfWork


CommandHandler = Callable[[Any, AbstractUnitOfWork], Any]
EventHandler = Callable[[Any, AbstractUnitOfWork], None]


COMMAND_HANDLERS: Dict[Type[Any], CommandHandler] = {
    commands.CaptureEventImage: handlers.handle_capture_event_image,
    commands.CaptureEventText: handlers.handle_capture_event_text,
    commands.CaptureEventUrl: handlers.handle_capture_event_url,
    commands.CaptureEventUploadImage: handlers.handle_capture_event_upload_image,
    commands.CaptureEventIcs: handlers.handle_capture_event_ics,
    commands.UpsertCommunityEvent: handlers.handle_upsert_community_event,
    commands.ConfirmEventDraft: handlers.handle_confirm_event_draft,
    commands.CancelEvent: handlers.handle_cancel_event,
    commands.ScheduleTrafficAlert: handlers.handle_schedule_traffic_alert,
    commands.ScheduleReminderAlert: handlers.handle_schedule_reminder_alert,
}

EVENT_HANDLERS: Dict[Type[Any], List[EventHandler]] = {
    # Cross-component side-effects are worker-driven via Redis topics published
    # from the transactional outbox.
    #
    # Keep this empty (or only include fully in-process, idempotent effects).
}


def handle(message: Any, uow: AbstractUnitOfWork) -> Any:
    return handle_with_publisher(message, uow, publisher=NoOpEventPublisher())


def handle_with_publisher(
    message: Any,
    uow: AbstractUnitOfWork,
    *,
    publisher: AbstractEventPublisher,
) -> Any:
    # NOTE: publisher is kept for backwards compatibility, but reliable delivery
    # is handled via the transactional outbox. Publishing occurs in the separate
    # outbox publisher worker after commit.
    queue: List[Any] = [message]
    last_result: Any = None

    while queue:
        msg = queue.pop(0)
        if type(msg) in COMMAND_HANDLERS:
            last_result = _handle_command(msg, queue, uow)
        else:
            _handle_event(msg, queue, uow)

    return last_result


def _handle_command(cmd: Any, queue: List[Any], uow: AbstractUnitOfWork) -> Any:
    handler = COMMAND_HANDLERS[type(cmd)]
    with uow:
        result = handler(cmd, uow)
        new_events = list(uow.collect_new_events())
        _enqueue_outbox_messages(new_events, uow)
        uow.commit()

    queue.extend(new_events)
    return result


def _handle_event(evt: Any, queue: List[Any], uow: AbstractUnitOfWork) -> None:
    for handler in EVENT_HANDLERS.get(type(evt), []):
        try:
            handler(evt, uow)
        except Exception:
            # event side-effects fail independently; caller can add retry/logging later
            continue
        queue.extend(uow.collect_new_events())

def _enqueue_outbox_messages(domain_events: list[Any], uow: AbstractUnitOfWork) -> None:
    now = datetime.now(timezone.utc)
    for evt in domain_events:
        topic = _topic_for_event(evt)
        if not topic:
            continue
        uow.outbox.add(OutboxMessage(topic=topic, payload=event_to_payload(evt), occurred_at=now))


def _topic_for_event(evt: Any) -> str | None:
    if isinstance(evt, events.EventConfirmed):
        return "event.confirmed"
    if isinstance(evt, events.AlertScheduled):
        return "alert.scheduled"
    if isinstance(evt, events.EventCancelled):
        return "event.cancelled"
    if isinstance(evt, events.CommunityEventUpserted):
        return "community_event.upserted"
    return None

