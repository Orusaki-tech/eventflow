from __future__ import annotations

import abc
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from icalendar import Calendar, Event as ICalEvent

from eventflow.domain.model import ScheduledEvent


@dataclass(frozen=True)
class CalendarRef:
    provider: str
    external_id: str


@dataclass(frozen=True)
class CalendarUpsertResult:
    ref: CalendarRef
    access_token: str
    refresh_token: Optional[str]
    expiry: Optional[datetime]


@dataclass(frozen=True)
class CalendarDeleteResult:
    access_token: str
    refresh_token: Optional[str]
    expiry: Optional[datetime]


class AbstractCalendarClient(abc.ABC):
    @abc.abstractmethod
    def upsert_event(
        self,
        *,
        user_id: str,
        event: ScheduledEvent,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> CalendarUpsertResult:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def build_ics(self, *, event: ScheduledEvent) -> str:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def delete_event(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: str,
    ) -> CalendarDeleteResult:  # pragma: no cover
        raise NotImplementedError


class GoogleCalendarClient(AbstractCalendarClient):
    def __init__(self, *, credentials_json: str):
        # OAuth client credentials JSON (installed/web) from Google Cloud Console.
        self._client_info = json.loads(credentials_json)

    def upsert_event(
        self,
        *,
        user_id: str,
        event: ScheduledEvent,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> CalendarUpsertResult:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri or "https://oauth2.googleapis.com/token",
            client_id=self._client_info.get("installed", {}).get("client_id")
            or self._client_info.get("web", {}).get("client_id"),
            client_secret=self._client_info.get("installed", {}).get("client_secret")
            or self._client_info.get("web", {}).get("client_secret"),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        end_time = event.start_time + timedelta(hours=1)
        body = {
            "summary": event.title,
            "location": event.venue,
            "start": {"dateTime": event.start_time.isoformat()},
            "end": {"dateTime": end_time.isoformat()},
        }

        if external_id:
            updated = (
                service.events().update(calendarId="primary", eventId=external_id, body=body).execute()
            )
            eid = str(updated["id"])
        else:
            created = service.events().insert(calendarId="primary", body=body).execute()
            eid = str(created["id"])

        return CalendarUpsertResult(
            ref=CalendarRef(provider="google", external_id=eid),
            access_token=str(creds.token),
            refresh_token=str(creds.refresh_token) if creds.refresh_token else None,
            expiry=creds.expiry,
        )

    def delete_event(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: str,
    ) -> CalendarDeleteResult:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri or "https://oauth2.googleapis.com/token",
            client_id=self._client_info.get("installed", {}).get("client_id")
            or self._client_info.get("web", {}).get("client_id"),
            client_secret=self._client_info.get("installed", {}).get("client_secret")
            or self._client_info.get("web", {}).get("client_secret"),
            scopes=["https://www.googleapis.com/auth/calendar.events"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        service.events().delete(calendarId="primary", eventId=external_id).execute()
        return CalendarDeleteResult(
            access_token=str(creds.token),
            refresh_token=str(creds.refresh_token) if creds.refresh_token else None,
            expiry=creds.expiry,
        )

    def build_ics(self, *, event: ScheduledEvent) -> str:
        cal = Calendar()
        cal.add("prodid", "-//EventFlow//EN")
        cal.add("version", "2.0")

        ical_evt = ICalEvent()
        ical_evt.add("uid", str(event.id))
        ical_evt.add("summary", event.title)
        ical_evt.add("location", event.venue)
        ical_evt.add("dtstart", event.start_time)
        ical_evt.add("dtstamp", datetime.now(timezone.utc))
        cal.add_component(ical_evt)
        return cal.to_ical().decode("utf-8")


class NoOpCalendarClient(AbstractCalendarClient):
    def upsert_event(
        self,
        *,
        user_id: str,
        event: ScheduledEvent,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> CalendarUpsertResult:
        return CalendarUpsertResult(
            ref=CalendarRef(provider="noop", external_id=external_id or str(event.id)),
            access_token=access_token,
            refresh_token=refresh_token,
            expiry=None,
        )

    def delete_event(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        external_id: str,
    ) -> CalendarDeleteResult:
        return CalendarDeleteResult(access_token=access_token, refresh_token=refresh_token, expiry=None)

    def build_ics(self, *, event: ScheduledEvent) -> str:
        return GoogleCalendarClient(credentials_json='{"installed":{}}').build_ics(event=event)

