"""Shared ``businesses.verified`` updates for admin tooling."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text

from eventflow.entrypoints.api.schemas import BusinessResponse


def set_business_verified(session: object, *, business_id: UUID, verified: bool) -> BusinessResponse:
    session.execute(
        text("UPDATE businesses SET verified = :v WHERE id = :id"),
        {"v": verified, "id": str(business_id)},
    )
    session.commit()
    row = session.execute(
        text("SELECT id, name, whatsapp_e164, verified FROM businesses WHERE id = :id LIMIT 1"),
        {"id": str(business_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return BusinessResponse(business_id=row[0], name=row[1], whatsapp_e164=row[2], verified=bool(row[3]))
