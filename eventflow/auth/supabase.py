from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from urllib.request import build_opener, ProxyHandler, Request, HTTPSHandler
import ssl
import certifi
import json

from eventflow.config import get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    raw_claims: Dict[str, Any]


@lru_cache
def _jwks_url() -> str:
    settings = get_settings()
    if not settings.supabase_jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL not configured")
    return settings.supabase_jwks_url


def _fetch_jwks(*, url: str) -> dict:
    # Avoid env proxy settings; they can break CONNECT tunnels and prevent
    # fetching JWKS in some environments.
    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    req = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "EventFlow/1.0"},
        method="GET",
    )
    with opener.open(req, timeout=5.0) as resp:
        raw = resp.read(1_000_000)
    return json.loads(raw.decode("utf-8"))


@lru_cache
def _cached_jwks() -> dict:
    return _fetch_jwks(url=_jwks_url())


def _get_signing_key_for_token(token: str):
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("Missing kid header")

    jwks = _cached_jwks()
    keys = jwks.get("keys") or []
    for k in keys:
        if isinstance(k, dict) and k.get("kid") == kid:
            kty = k.get("kty")
            if kty == "EC":
                return ECAlgorithm.from_jwk(json.dumps(k))
            return RSAAlgorithm.from_jwk(json.dumps(k))

    # Key rotation or stale cache: refetch once.
    _cached_jwks.cache_clear()
    jwks = _cached_jwks()
    keys = jwks.get("keys") or []
    for k in keys:
        if isinstance(k, dict) and k.get("kid") == kid:
            kty = k.get("kty")
            if kty == "EC":
                return ECAlgorithm.from_jwk(json.dumps(k))
            return RSAAlgorithm.from_jwk(json.dumps(k))
    raise jwt.InvalidTokenError("Signing key not found for kid")


def verify_supabase_jwt(token: str) -> AuthenticatedUser:
    settings = get_settings()

    signing_key = _get_signing_key_for_token(token)

    options = {
        "verify_aud": True,
        "verify_iss": bool(settings.supabase_jwt_issuer),
    }

    claims = jwt.decode(
        token,
        signing_key,
        algorithms=["ES256", "RS256"],
        audience=settings.supabase_jwt_audience,
        issuer=settings.supabase_jwt_issuer,
        options=options,
    )

    sub = claims.get("sub")
    if not sub:
        raise jwt.InvalidTokenError("Missing sub claim")

    return AuthenticatedUser(id=str(sub), raw_claims=dict(claims))

