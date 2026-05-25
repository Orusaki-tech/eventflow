from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from eventflow.adapters.repository import CalendarToken, OAuthState
from eventflow.config import get_settings
from eventflow.entrypoints.dependencies import get_current_user_id, get_uow


router = APIRouter(tags=["Calendar OAuth"])

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_PROVIDER = "google"


@router.get("/auth/google/calendar/start", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def google_calendar_oauth_start(
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    settings = get_settings()
    if not settings.google_calendar_credentials_json:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_CALENDAR_CREDENTIALS_JSON not configured")
    if not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_OAUTH_REDIRECT_URI not configured")

    client_config = __import__("json").loads(settings.google_calendar_credentials_json)
    flow = Flow.from_client_config(client_config, scopes=_SCOPES)
    flow.redirect_uri = settings.google_oauth_redirect_uri

    state = secrets.token_urlsafe(24)
    with uow:
        uow.oauth_states.upsert(
            OAuthState(
                user_id=user_id,
                provider=_PROVIDER,
                state=state,
                created_at=datetime.now(timezone.utc),
            )
        )
        uow.commit()

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
        include_granted_scopes="true",
    )
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/auth/google/calendar/callback", status_code=status.HTTP_200_OK)
async def google_calendar_oauth_callback(
    code: str,
    state: str,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    settings = get_settings()
    if not settings.google_calendar_credentials_json:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_CALENDAR_CREDENTIALS_JSON not configured")
    if not settings.google_oauth_redirect_uri:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="GOOGLE_OAUTH_REDIRECT_URI not configured")

    client_config = __import__("json").loads(settings.google_calendar_credentials_json)
    flow = Flow.from_client_config(client_config, scopes=_SCOPES, state=state)
    flow.redirect_uri = settings.google_oauth_redirect_uri

    with uow:
        expected = uow.oauth_states.get(user_id=user_id, provider=_PROVIDER)
        if expected is None or expected.state != state:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

        flow.fetch_token(code=code)
        creds = flow.credentials

        uow.calendar_tokens.upsert(
            CalendarToken(
                user_id=user_id,
                provider=_PROVIDER,
                access_token=str(creds.token),
                refresh_token=str(creds.refresh_token) if creds.refresh_token else None,
                token_uri=str(creds.token_uri or "https://oauth2.googleapis.com/token"),
                scopes=tuple(creds.scopes or _SCOPES),
                expiry=creds.expiry,
            )
        )
        uow.oauth_states.delete(user_id=user_id, provider=_PROVIDER)
        uow.commit()

    # Returning a minimal HTML body is friendlier than a blank response in browser redirects.
    return HTMLResponse("<html><body>You can close this tab.</body></html>", status_code=status.HTTP_200_OK)

