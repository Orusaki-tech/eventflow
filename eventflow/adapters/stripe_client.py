from __future__ import annotations

import logging
from uuid import UUID

import stripe

from eventflow.config import get_settings

_log = logging.getLogger(__name__)


def _init_stripe() -> bool:
    key = get_settings().stripe_secret_key
    if not key:
        return False
    stripe.api_key = key
    return True


def create_checkout_session(
    *,
    user_id: UUID,
    success_url: str,
    cancel_url: str,
    price_id: str | None = None,
) -> str | None:
    if not _init_stripe():
        _log.warning("stripe_secret_key is not set; cannot create checkout session")
        return None

    pid = price_id or get_settings().stripe_premium_price_id
    if not pid:
        _log.warning("No Stripe price ID configured (STRIPE_PREMIUM_PRICE_ID)")
        return None

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": pid, "quantity": 1}],
            client_reference_id=str(user_id),
            metadata={"user_id": str(user_id)},
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "metadata": {"user_id": str(user_id)},
            },
        )
        return session.url
    except stripe.error.StripeError as e:
        _log.error("Stripe checkout session creation failed: %s", e, exc_info=True)
        return None


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict | None:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        _log.warning("stripe_webhook_secret is not set; cannot verify webhook")
        return None
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
        return event
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        _log.warning("Stripe webhook signature verification failed: %s", e)
        return None
