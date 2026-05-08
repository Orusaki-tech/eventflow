from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict
from zoneinfo import ZoneInfo

from dateutil import parser as dateutil_parser
from google import genai

from eventflow.adapters.gemini_client import AbstractGeminiClient, ParsedEventDraft


def _extract_first_json_object(text: str) -> str | None:
    """
    Best-effort extraction of a JSON object from model output.
    Gemini sometimes wraps JSON in prose or code fences.
    """
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return cleaned[start : end + 1].strip()


def _parse_strict_event_json(raw_text: str) -> Dict[str, Any]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise ValueError("Gemini returned empty response text")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(raw_text)
        if not extracted:
            raise ValueError(f"Gemini returned non-JSON: {raw_text[:200]!r}") from None
        try:
            return json.loads(extracted)
        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini returned invalid JSON: {extracted[:200]!r}") from e


def _coerce_optional_price(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    if isinstance(value, (int, float)):
        return str(value)
    return None


_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_H24 = re.compile(r"^(\d{1,2}):(\d{2})$")
_TIME_AMPM = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)$")
# Loose detection so event_time values like "10AM", "10 AM", "7:30pm" prefer structured merge over bad ISO.
_AM_PM_IN_CLOCK = re.compile(r"(?<![A-Za-z])(?:am|pm|a\.m\.|p\.m\.)(?![A-Za-z])", re.IGNORECASE)


def _event_time_prints_am_pm(ts_raw: str) -> bool:
    return bool(ts_raw and _AM_PM_IN_CLOCK.search(ts_raw))


def _infer_twelve_hour_confusion(iso_wall_dt: datetime, event_time_raw: str) -> bool:
    """
    Model often emits ISO hour 22 when the poster says 10AM (structured event_time \"10:00\" + wrong ISO).
    Same minute, structured hour 1–11, ISO hour == structured + 12 → treat as AM/PM mix-up.
    """
    parsed = _parse_event_clock_to_hh_mm(event_time_raw.strip())
    if parsed is None:
        return False
    sh, sm = parsed
    ih, im = iso_wall_dt.hour, iso_wall_dt.minute
    if im != sm:
        return False
    return 1 <= sh <= 11 and ih == sh + 12


def _parse_event_clock_to_hh_mm(ts_raw: str) -> tuple[int, int] | None:
    """
    Parse local clock text from flyers: "19:30", "7:30 PM", "10AM", "10:00 am".
    Returns None if not recognised.
    """
    s = " ".join(ts_raw.strip().split())
    if not s:
        return None
    m24 = _TIME_H24.match(s)
    if m24:
        hh, mm = int(m24.group(1)), int(m24.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
        return None
    m12 = _TIME_AMPM.match(s)
    if not m12:
        return None
    hh = int(m12.group(1))
    mm = int(m12.group(2) or "0")
    if not (1 <= hh <= 12 and 0 <= mm <= 59):
        return None
    ap = m12.group(3).upper()
    if ap == "PM" and hh != 12:
        hh += 12
    elif ap == "AM" and hh == 12:
        hh = 0
    return hh, mm


def _parse_offset_tz(s: str):
    m = re.match(r"^([+-])(\d{2}):(\d{2})$", s.strip())
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    hours = int(m.group(2))
    mins = int(m.group(3))
    return timezone(sign * timedelta(hours=hours, minutes=mins))


def _resolve_timezone_hint(raw: Any):
    if raw is None:
        return timezone.utc
    s = str(raw).strip()
    if not s:
        return timezone.utc
    if s.upper() in {"Z", "UTC"}:
        return timezone.utc
    oz = _parse_offset_tz(s)
    if oz is not None:
        return oz
    try:
        return ZoneInfo(s)
    except Exception:
        return timezone.utc


def _offset_string_from_aware_dt(dt: datetime) -> str | None:
    """Format ±HH:MM for combine fallback when LLM left timezone null but ISO carries an offset."""
    if dt.tzinfo is None:
        return None
    off = dt.utcoffset()
    if off is None:
        return None
    total_seconds = int(off.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    return f"{sign}{hh:02d}:{mm:02d}"


def _structured_event_clock_is_set(data: Dict[str, Any]) -> bool:
    ts_raw = str(data.get("event_time") or "").strip()
    return bool(ts_raw) and _parse_event_clock_to_hh_mm(ts_raw) is not None


def _parse_event_date_from_llm(data: Dict[str, Any]) -> date | None:
    raw = data.get("event_date")
    if raw is None:
        return None
    ds = str(raw).strip()
    if not ds or not _DATE_ISO.match(ds):
        return None
    y, mo, d = (int(x) for x in ds.split("-"))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _parse_loose_datetime_string(s: str) -> datetime | None:
    """ISO first, then dateutil (ambiguous dates treated as unreliable upstream)."""
    s = s.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        dt = dateutil_parser.parse(s)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _combine_calendar_parts(
    *,
    event_date: Any,
    event_time: Any,
    timezone_hint: Any,
) -> tuple[datetime | None, bool]:
    """
    Build datetime from structured fields. unreliable=True when time or timezone was defaulted.
    """
    ds = str(event_date).strip() if event_date is not None else ""
    if not ds or not _DATE_ISO.match(ds):
        return None, False
    y, mo, d = (int(x) for x in ds.split("-"))
    unreliable = False
    ts_raw = str(event_time).strip() if event_time is not None else ""
    parsed_clock = _parse_event_clock_to_hh_mm(ts_raw) if ts_raw else None
    if parsed_clock is not None:
        hh, mm = parsed_clock
    else:
        hh, mm = 12, 0
        unreliable = True
    tz = _resolve_timezone_hint(timezone_hint)
    if timezone_hint is None or (isinstance(timezone_hint, str) and not timezone_hint.strip()):
        unreliable = True
    try:
        return datetime(y, mo, d, hh, mm, tzinfo=tz), unreliable
    except ValueError:
        return None, False


def interpret_event_timing_from_llm_dict(data: Dict[str, Any]) -> tuple[datetime | None, bool]:
    """
    Resolve event start time from LLM JSON.
    Returns (start_time_utc_or_none, unreliable_any_step).

    Priority: structured clock from event_date/event_time when AM/PM is explicit or ISO looks like a +12h mistake;
    then datetime / unix → ISO start_time (reconciled vs event_date); then structured fields; then loose parse.

    Gemini sometimes fills ISO start_time with \"today\" while event_date matches the poster; when event_date is
    valid and its calendar day differs from the ISO string's calendar day, we prefer structured assembly or the
    poster date with the ISO wall-clock time.
    """
    unreliable = False
    combined = data.get("start_time")

    if isinstance(combined, datetime):
        dt = combined
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        et_raw = str(data.get("event_time") or "")
        if _structured_event_clock_is_set(data) and _event_time_prints_am_pm(et_raw):
            dt_parts, unr_parts = _combine_calendar_parts(
                event_date=data.get("event_date"),
                event_time=data.get("event_time"),
                timezone_hint=data.get("timezone"),
            )
            if unr_parts:
                unreliable = True
            if dt_parts is not None:
                return dt_parts, unreliable
        if _structured_event_clock_is_set(data) and _infer_twelve_hour_confusion(dt, et_raw.strip()):
            dt_parts, unr_parts = _combine_calendar_parts(
                event_date=data.get("event_date"),
                event_time=data.get("event_time"),
                timezone_hint=data.get("timezone"),
            )
            if dt_parts is not None:
                return dt_parts, True
        d_ev = _parse_event_date_from_llm(data)
        if d_ev is not None and dt.date() != d_ev:
            if _structured_event_clock_is_set(data):
                dt_parts, unr_parts = _combine_calendar_parts(
                    event_date=data.get("event_date"),
                    event_time=data.get("event_time"),
                    timezone_hint=data.get("timezone"),
                )
                if unr_parts:
                    unreliable = True
                if dt_parts is not None:
                    return dt_parts, unreliable
            try:
                return dt.replace(year=d_ev.year, month=d_ev.month, day=d_ev.day), True
            except ValueError:
                pass
            tz_hint = data.get("timezone")
            if tz_hint is None or (isinstance(tz_hint, str) and not str(tz_hint).strip()):
                tz_hint = _offset_string_from_aware_dt(dt)
            dt_merge, unr_merge = _combine_calendar_parts(
                event_date=data.get("event_date"),
                event_time=f"{dt.hour:02d}:{dt.minute:02d}",
                timezone_hint=tz_hint,
            )
            if dt_merge is not None:
                return dt_merge, unreliable or unr_merge or True
        return dt, unreliable
    if isinstance(combined, (int, float)):
        return datetime.fromtimestamp(float(combined), tz=timezone.utc), unreliable

    dt_from_iso: datetime | None = None
    if isinstance(combined, str):
        s = combined.strip()
        if s:
            try:
                dt_from_iso = datetime.fromisoformat(s.replace("Z", "+00:00"))
                if dt_from_iso.tzinfo is None:
                    dt_from_iso = dt_from_iso.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    et_raw_str = str(data.get("event_time") or "")
    if _structured_event_clock_is_set(data) and _event_time_prints_am_pm(et_raw_str):
        dt_parts, unr_parts = _combine_calendar_parts(
            event_date=data.get("event_date"),
            event_time=data.get("event_time"),
            timezone_hint=data.get("timezone"),
        )
        if unr_parts:
            unreliable = True
        if dt_parts is not None:
            return dt_parts, unreliable

    if dt_from_iso is not None:
        if _structured_event_clock_is_set(data):
            if _infer_twelve_hour_confusion(dt_from_iso, et_raw_str.strip()):
                dt_parts, unr_parts = _combine_calendar_parts(
                    event_date=data.get("event_date"),
                    event_time=data.get("event_time"),
                    timezone_hint=data.get("timezone"),
                )
                if dt_parts is not None:
                    return dt_parts, True
        d_ev = _parse_event_date_from_llm(data)
        if d_ev is not None and dt_from_iso.date() != d_ev:
            if _structured_event_clock_is_set(data):
                dt_parts, unr_parts = _combine_calendar_parts(
                    event_date=data.get("event_date"),
                    event_time=data.get("event_time"),
                    timezone_hint=data.get("timezone"),
                )
                if unr_parts:
                    unreliable = True
                if dt_parts is not None:
                    return dt_parts, unreliable
            try:
                return dt_from_iso.replace(year=d_ev.year, month=d_ev.month, day=d_ev.day), True
            except ValueError:
                pass
            tz_hint = data.get("timezone")
            if tz_hint is None or (isinstance(tz_hint, str) and not str(tz_hint).strip()):
                tz_hint = _offset_string_from_aware_dt(dt_from_iso)
            dt_merge, unr_merge = _combine_calendar_parts(
                event_date=data.get("event_date"),
                event_time=f"{dt_from_iso.hour:02d}:{dt_from_iso.minute:02d}",
                timezone_hint=tz_hint,
            )
            if dt_merge is not None:
                return dt_merge, unreliable or unr_merge or True
        return dt_from_iso, unreliable

    dt_parts, unr_parts = _combine_calendar_parts(
        event_date=data.get("event_date"),
        event_time=data.get("event_time"),
        timezone_hint=data.get("timezone"),
    )
    if unr_parts:
        unreliable = True
    if dt_parts is not None:
        return dt_parts, unreliable

    if isinstance(combined, str) and combined.strip():
        loose = _parse_loose_datetime_string(combined.strip())
        if loose is not None:
            return loose, True

    return None, True


def damp_confidence_for_timing(*, confidence: float, start_time: datetime | None, unreliable_time: bool) -> float:
    c = float(confidence)
    if start_time is None:
        return min(c, 0.35)
    if unreliable_time:
        return min(c, 0.48)
    return c


def _inline_image_mime_type(*, declared_content_type: str | None, image_bytes: bytes) -> str:
    ct = (declared_content_type or "").split(";")[0].strip().lower()
    if ct.startswith("image/"):
        return ct
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(image_bytes) >= 12 and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


_POSTER_IMAGE_PROMPT = """You extract structured event data from ONE raster image: a flyer, poster, ticket graphic, or social carousel slide.

REFERENCE CALENDAR DATE (UTC)
The server's UTC calendar date today is {reference_calendar_date_iso}. Use it ONLY to infer a missing YEAR when month + day are explicit ON THE IMAGE (optionally with weekday) but no four-digit year prints anywhere nearby — choose the plausible upcoming promotional date on or after this reference such that month/day (and weekday if printed) match Gregorian calendar rules. Never replace or contradict a printed four-digit year.

CRITICAL — NOT THE EVENT DAY
- The reference date is NOT the event's month or day. Never copy today's day-of-month or month from the reference into event_date or start_time when the poster shows different typography (e.g. poster prints "May 10" → event_date must end in -05-10, never today's DOM).
- start_time's calendar date must equal event_date whenever both are set (same advertised local calendar day). Do not set start_time to \"now\" or today's date.

SOURCE OF TRUTH
- Use ONLY letters/numbers/diagrams PRINTED or DRAWN inside this image.
- Ignore: filenames, Instagram/TikTok UI, profile names, like counts, captions not overlaid on the art, post timestamps, watermarks that are not part of the flyer layout.

WHAT TO CAPTURE AS "START"
- The instant the MAIN advertised experience begins (headline session, show doors-open only if that is the only stated start, yoga/fitness class start, concert ticket time).
- If the poster lists several slots for ONE day (e.g. workshops), use the earliest clearly labelled PUBLIC session start, not staff/setup times.
- If BOTH "doors open" and "show starts" appear, prefer SHOW STARTS / MAIN PERFORMANCE time.
- Ignore unrelated clocks (e.g. stock imagery with random watches).

CORRECT CALENDAR DATE (event_date)
- Output event_date strictly as YYYY-MM-DD. Every digit must match what is justified by the flyer OR by the reference-date rule above for missing year only.
- Named months remove ambiguity: "May 10", "May 10th", "10 May", "Sun May 10" → month and day are locked before choosing year.
- If BOTH weekday AND numeric month/day appear, verify they agree in the Gregorian calendar; if they clash, trust the numeric month/day print and lower confidence_score.
- Pure slash/numeric dates without month names (e.g. 03/04/2026): use venue geography ON THE IMAGE — Americas → commonly MM/DD/YYYY; Kenya/UK/EU/Africa defaults → commonly DD/MM/YYYY when plausible; if still ambiguous set lower confidence_score and pick the reading best supported by nearby language/format cues (leading day >12 implies DD/MM, etc.).
- Date spans ("May 10–12", "Fri–Sat"): use the OPENING day unless a specific session names another day.
- Do NOT shift event_date because of timezone conversion — date is the printed local calendar day.

TIME RULES
- Printed AM/PM is authoritative: "10AM" / "10 AM" is morning hour 10, NEVER hour 22 (10 PM). Same for "10PM" → evening.
- Convert printed clock copy to event_time as HH:MM 24-hour (examples: 10AM → "10:00", 7:30 PM → "19:30"). You MAY instead output event_time with AM/PM (e.g. "10AM", "7:30 PM"); never contradict the poster's meridian.
- start_time's LOCAL hour and minute must match event_time for the same zone — do not emit ISO with hour 22 when event_time is "10:00" from a 10AM poster (that is a critical error).
- Fill start_time as ISO-8601 with explicit offset only when event_date + local clock + timezone are justified together; event_date + event_time must describe the same local calendar instant.

TIMEZONE
- Prefer IANA names when geography is clear from venue/city/country ON the image (examples: venue in Nairobi → Africa/Nairobi; London UK → Europe/London).
- If only offset is stated ("UTC+3", "EAT"), use ±HH:MM offset form for timezone (e.g. "+03:00").
- If neither geography nor offset appears on the image, timezone MUST be null (do not guess from generic English phrases alone).

OUTPUT
Return STRICT JSON with exactly these keys and no others:
- title (string): event title as on poster.
- venue (string): primary venue or location line(s).
- confidence_score (number 0..1): lower if date order, weekday match, or timezone was ambiguous.
- price (string or null): admission exactly as shown; null if absent.
- start_time (string or null): single ISO-8601 datetime with explicit offset (e.g. 2026-05-10T10:00:00+03:00). Null when date AND/OR clock cannot be fixed without guessing.
- event_date (string or null): YYYY-MM-DD when readable from the image (must match local calendar day for start_time).
- event_time (string or null): local start when readable — HH:MM 24h and/or AM/PM forms such as "10AM", "10:30 PM" (must match start_time if both set).
- timezone (string or null): IANA zone OR ±HH:MM offset per rules above.

When date exists but clock does not, set event_time and start_time null.
Never invent placeholder dates or times not justified by the image pixels (except missing-year resolution using the reference date rule).
"""


_TEXT_PARSE_PROMPT_TEMPLATE = """You extract event details from TEXT (caption, invite email, chat paste). Prefer stated event lines over generic publication dates.

REFERENCE CALENDAR DATE (UTC)
Today's UTC calendar date is {reference_calendar_date_iso}. Use it ONLY to resolve missing years on phrases like "Sunday May 10" without a year — pick the plausible upcoming occurrence on or after this reference consistent with weekday + month/day. Never override an explicit four-digit year in the text.

NOT THE EVENT DAY
- Do not use today's calendar day as event_date or inside start_time when the message states a different event day (e.g. "May 10" → May 10, not today's DOM).

CORRECT DATE (event_date)
- Always prefer event_date as YYYY-MM-DD named dates ("May 10") lock month/day before year choice.
- Numeric ambiguous slashes: use city/country named in the SAME text for DD/MM vs MM/DD bias; lower confidence when guessing.

START TIME
- Use the clearest stated datetime for when the EVENT begins (not "posted on", not upload metadata unless no other time exists).
- If multiple times appear (doors vs show), prefer the main performance/session start.
- Output event_time as HH:MM 24h when possible.
- Output start_time as ISO-8601 with explicit offset when timezone is justified by named geography in the text or stated offset; otherwise null start_time while still filling event_date/event_time when wall-clock is explicit locally.

Return STRICT JSON only:
title (string),
start_time (string or null, ISO-8601 with offset),
event_date (YYYY-MM-DD or null),
event_time (HH:MM 24h or null),
timezone (IANA or ±HH:MM or null),
venue (string),
confidence_score (0..1 float),
price (string or null).

TEXT:
{text}
"""


class GeminiClient(AbstractGeminiClient):
    def __init__(self, *, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def parse_event_image(
        self,
        *,
        image_bytes: bytes,
        content_type: str | None = None,
        reference_calendar_date: date | None = None,
    ) -> ParsedEventDraft:
        ref = reference_calendar_date if reference_calendar_date is not None else datetime.now(timezone.utc).date()
        poster_prompt = _POSTER_IMAGE_PROMPT.format(reference_calendar_date_iso=ref.isoformat())
        mime = _inline_image_mime_type(declared_content_type=content_type, image_bytes=image_bytes)
        resp = self._client.models.generate_content(
            model=self._model,
            contents=[
                poster_prompt,
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": image_bytes,
                    }
                },
            ],
        )

        text = (getattr(resp, "text", None) or "").strip()
        data = _parse_strict_event_json(text)
        start_time, unreliable_time = interpret_event_timing_from_llm_dict(data)

        return ParsedEventDraft(
            title=str(data.get("title") or ""),
            start_time=start_time,
            venue=str(data.get("venue") or ""),
            confidence_score=damp_confidence_for_timing(
                confidence=float(data.get("confidence_score") or 0),
                start_time=start_time,
                unreliable_time=unreliable_time,
            ),
            price=_coerce_optional_price(data.get("price")),
        )

    def parse_event_text(self, *, text: str, reference_calendar_date: date | None = None) -> ParsedEventDraft:
        ref = reference_calendar_date if reference_calendar_date is not None else datetime.now(timezone.utc).date()
        prompt = _TEXT_PARSE_PROMPT_TEMPLATE.format(
            text=text,
            reference_calendar_date_iso=ref.isoformat(),
        )
        resp = self._client.models.generate_content(
            model=self._model,
            contents=[prompt],
        )

        raw = (getattr(resp, "text", None) or "").strip()
        data = _parse_strict_event_json(raw)
        start_time, unreliable_time = interpret_event_timing_from_llm_dict(data)

        return ParsedEventDraft(
            title=str(data.get("title") or ""),
            start_time=start_time,
            venue=str(data.get("venue") or ""),
            confidence_score=damp_confidence_for_timing(
                confidence=float(data.get("confidence_score") or 0),
                start_time=start_time,
                unreliable_time=unreliable_time,
            ),
            price=_coerce_optional_price(data.get("price")),
        )
