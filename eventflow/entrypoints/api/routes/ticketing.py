"""Ticketing, feed, affiliates, payouts, claims, subscriptions."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4

import calendar
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Json
from sqlalchemy import text
from starlette.responses import Response

from eventflow.entrypoints.api.schemas import (
    AdminClaimResolveRequest,
    AdminClaimRow,
    AdminModerateResponse,
    AdminOrderRow,
    AdminPayoutRow,
    AdminProcessPayoutResponse,
    AdminResolveResponse,
    AdminVideoRow,
    CheckInResponse,
    ClaimCreateRequest,
    ClaimResponse,
    DashboardResponse,
    DashboardListingRow,
    FeedVideoPublishRequest,
    FeedVideoResponse,
    FeedWatchResponse,
    OrderResponse,
    OrderTicketRow,
    PayoutRequest,
    PayoutRequestResponse,
    PayoutSettingsResponse,
    PayoutResponse,
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
    PointsResponse,
    ProductCreateRequest,
    ProductEventLinkApproveRequest,
    ProductEventLinkRequest,
    ProductEventLinkResponse,
    ProductResponse,
    PurchaseRequest,
    PurchaseResponse,
    RedeemPointsRequest,
    SalesDetailRow,
    SubscriptionResponse,
    TapPackBuyRequest,
    TapPackResponse,
    TicketLookupResponse,
    TicketResendResponse,
    TicketTypeBulkRequest,
    TicketTypeResponse,
    VideoModerationRequest,
    WatchQuotaResponse,
)
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, require_admin_user

router = APIRouter(tags=["Ticketing"])


def _assert_listing_owner(session, community_event_id: UUID, user_id: UUID) -> None:
    row = session.execute(
        text("SELECT user_id FROM community_events WHERE id = :id LIMIT 1"),
        {"id": str(community_event_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail="Not your listing")


def _assert_business_owner(session, business_id: UUID, user_id: UUID) -> None:
    row = session.execute(
        text("SELECT owner_user_id FROM businesses WHERE id = :id LIMIT 1"),
        {"id": str(business_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Business not found")
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail="Not your business")


def _get_platform_setting(session, key: str) -> dict:
    row = session.execute(
        text("SELECT value FROM platform_settings WHERE key = :k LIMIT 1"),
        {"k": key},
    ).first()
    return dict(row[0]) if row and row[0] else {}


def _generate_short_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "EVT-" + "".join(secrets.choice(alphabet) for _ in range(4))


# ─── Ticket Types ────────────────────────────────────────────────────────


@router.get(
    "/listings/{community_event_id}/ticket-types",
    status_code=status.HTTP_200_OK,
    response_model=list[TicketTypeResponse],
)
async def list_ticket_types(
    community_event_id: UUID,
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text(
            """
            SELECT id, name, description, price_minor_units, currency,
                   quantity_available, quantity_sold, sale_start, sale_end,
                   refundable_until, is_active, sort_order
            FROM ticket_types
            WHERE community_event_id = :ce AND is_active = true
            ORDER BY sort_order ASC, created_at ASC
            """
        ),
        {"ce": str(community_event_id)},
    ).fetchall()
    return [
        TicketTypeResponse(
            ticket_type_id=r[0],
            name=r[1],
            description=r[2],
            price_minor_units=r[3],
            currency=r[4],
            quantity_available=r[5],
            quantity_sold=r[6],
            sale_start=r[7],
            sale_end=r[8],
            refundable_until=r[9],
            is_active=r[10],
            sort_order=r[11],
        )
        for r in rows
    ]


@router.put(
    "/listings/{community_event_id}/ticket-types",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def bulk_set_ticket_types(
    community_event_id: UUID,
    body: TicketTypeBulkRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_listing_owner(session, community_event_id, user_id)

    now = datetime.now(timezone.utc)

    # Deactivate existing types not in the new set
    if body.types:
        keep_ids = [t.ticket_type_id for t in body.types if t.ticket_type_id]
        if keep_ids:
            session.execute(
                text(
                    """
                    UPDATE ticket_types SET is_active = false, updated_at = :now
                    WHERE community_event_id = :ce AND id != ALL(:keep)
                    """
                ),
                {"ce": str(community_event_id), "keep": keep_ids, "now": now},
            )
    else:
        session.execute(
            text(
                "UPDATE ticket_types SET is_active = false, updated_at = :now "
                "WHERE community_event_id = :ce"
            ),
            {"ce": str(community_event_id), "now": now},
        )

    for idx, t in enumerate(body.types):
        if t.ticket_type_id:
            # Update existing
            session.execute(
                text(
                    """
                    UPDATE ticket_types
                    SET name = :name, description = :desc, price_minor_units = :price,
                        quantity_available = :qty, sale_start = :ss, sale_end = :se,
                        refundable_until = :ru, sort_order = :so, updated_at = :now
                    WHERE id = :id AND community_event_id = :ce
                    """
                ),
                {
                    "id": str(t.ticket_type_id),
                    "ce": str(community_event_id),
                    "name": t.name,
                    "desc": t.description,
                    "price": t.price_minor_units,
                    "qty": t.quantity_available,
                    "ss": t.sale_start,
                    "se": t.sale_end,
                    "ru": t.refundable_until,
                    "so": idx,
                    "now": now,
                },
            )
        else:
            # Create new
            tid = uuid4()
            session.execute(
                text(
                    """
                    INSERT INTO ticket_types (id, community_event_id, name, description,
                        price_minor_units, quantity_available, sale_start, sale_end,
                        refundable_until, sort_order, created_at, updated_at)
                    VALUES (:id, :ce, :name, :desc, :price, :qty, :ss, :se, :ru, :so, :now, :now)
                    """
                ),
                {
                    "id": tid,
                    "ce": str(community_event_id),
                    "name": t.name,
                    "desc": t.description,
                    "price": t.price_minor_units,
                    "qty": t.quantity_available,
                    "ss": t.sale_start,
                    "se": t.sale_end,
                    "ru": t.refundable_until,
                    "so": idx,
                    "now": now,
                },
            )

    session.execute(
        text("UPDATE community_events SET has_ticketing = true WHERE id = :ce"),
        {"ce": str(community_event_id)},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Purchase Flow ───────────────────────────────────────────────────────


@router.post("/tickets/purchase", status_code=status.HTTP_201_CREATED, response_model=PurchaseResponse)
async def purchase_tickets(
    body: PurchaseRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Validate event exists
    event = session.execute(
        text(
            "SELECT id, title, start_time FROM community_events WHERE id = :ce LIMIT 1"
        ),
        {"ce": str(body.community_event_id)},
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    now = datetime.now(timezone.utc)
    total_minor = 0
    order_items_data: list[dict] = []

    for item in body.items:
        tt = session.execute(
            text(
                """
                SELECT id, name, price_minor_units, quantity_available, quantity_sold,
                       sale_start, sale_end, is_active
                FROM ticket_types WHERE id = :id AND community_event_id = :ce LIMIT 1
                FOR UPDATE
                """
            ),
            {"id": str(item.ticket_type_id), "ce": str(body.community_event_id)},
        ).first()
        if tt is None:
            raise HTTPException(status_code=404, detail=f"Ticket type {item.ticket_type_id} not found")
        if not tt[7]:
            raise HTTPException(status_code=400, detail=f"Ticket type {tt[1]} is not active")
        if tt[5] and tt[5] > now:
            raise HTTPException(status_code=400, detail=f"Sale for {tt[1]} has not started")
        if tt[6] and tt[6] < now:
            raise HTTPException(status_code=400, detail=f"Sale for {tt[1]} has ended")
        if tt[3] is not None and tt[4] + item.quantity > tt[3]:
            raise HTTPException(status_code=400, detail=f"Not enough {tt[1]} tickets available")

        subtotal = tt[2] * item.quantity
        total_minor += subtotal
        order_items_data.append({
            "ticket_type_id": tt[0],
            "name": tt[1],
            "quantity": item.quantity,
            "unit_price": tt[2],
            "subtotal": subtotal,
        })

    # Calculate fees
    fee_config = _get_platform_setting(session, "platform_fee")
    fee_percent = fee_config.get("ticket_percent", 8)
    platform_fee = int(total_minor * fee_percent / 100)
    business_net = total_minor - platform_fee

    # Create order
    oid = uuid4()
    receipt_num = f"EVT-{now.strftime('%y%m')}-{secrets.randbelow(900000) + 100000}"
    session.execute(
        text(
            """
            INSERT INTO orders (id, community_event_id, user_id, status, type,
                total_minor_units, platform_fee_minor_units, business_net_minor_units,
                currency, payment_provider, payment_provider_transaction_id,
                paid_at, receipt_number, points_earned, created_at, updated_at)
            VALUES (:id, :ce, :uid, :status, 'ticket',
                :total, :fee, :net,
                'KES', :provider, :txn,
                :paid, :receipt, :pts, :now, :now)
            """
        ),
        {
            "id": oid,
            "ce": str(body.community_event_id),
            "uid": user_id,
            "status": "confirmed",
            "total": total_minor,
            "fee": platform_fee,
            "net": business_net,
            "provider": body.payment_provider or "stripe",
            "txn": f"sim_{secrets.token_hex(8)}",
            "paid": now,
            "receipt": receipt_num,
            "pts": max(1, total_minor // 10000),  # 1 point per KES 100 spent
            "now": now,
        },
    )

    # Create order items and tickets
    ticket_codes: list[str] = []
    for od in order_items_data:
        oi_id = uuid4()
        session.execute(
            text(
                """
                INSERT INTO order_items (id, order_id, ticket_type_id, quantity,
                    unit_price_minor_units, subtotal_minor_units)
                VALUES (:id, :oid, :ttid, :qty, :price, :sub)
                """
            ),
            {
                "id": oi_id,
                "oid": oid,
                "ttid": str(od["ticket_type_id"]),
                "qty": od["quantity"],
                "price": od["unit_price"],
                "sub": od["subtotal"],
            },
        )

        # Update quantity_sold
        session.execute(
            text(
                "UPDATE ticket_types SET quantity_sold = quantity_sold + :qty WHERE id = :id"
            ),
            {"qty": od["quantity"], "id": str(od["ticket_type_id"])},
        )

        # Generate individual tickets
        for _ in range(od["quantity"]):
            tid = uuid4()
            code = _generate_short_code()
            session.execute(
                text(
                    """
                    INSERT INTO tickets (id, short_code, order_id, ticket_type_id,
                        community_event_id, user_id, status, created_at)
                    VALUES (:id, :code, :oid, :ttid, :ce, :uid, 'active', :now)
                    """
                ),
                {
                    "id": tid,
                    "code": code,
                    "oid": oid,
                    "ttid": str(od["ticket_type_id"]),
                    "ce": str(body.community_event_id),
                    "uid": user_id,
                    "now": now,
                },
            )
            ticket_codes.append(code)

    # Add points to user
    pts_earned = max(1, total_minor // 10000)
    session.execute(
        text(
            """
            INSERT INTO user_points (user_id, balance, lifetime_earned, last_activity, created_at)
            VALUES (:uid, :pts, :pts, :now, :now)
            ON CONFLICT (user_id) DO UPDATE SET
                balance = user_points.balance + :pts2,
                lifetime_earned = user_points.lifetime_earned + :pts2,
                last_activity = :now
            """
        ),
        {"uid": user_id, "pts": pts_earned, "pts2": pts_earned, "now": now},
    )

    session.commit()

    return PurchaseResponse(
        order_id=oid,
        receipt_number=receipt_num,
        total_minor_units=total_minor,
        platform_fee_minor_units=platform_fee,
        payment_provider=body.payment_provider or "stripe",
        ticket_codes=ticket_codes,
        points_earned=pts_earned,
    )


@router.get("/tickets/orders", status_code=status.HTTP_200_OK, response_model=list[OrderResponse])
async def list_orders(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT o.id, o.community_event_id, ce.title, o.status, o.type,
                   o.total_minor_units, o.platform_fee_minor_units, o.business_net_minor_units,
                   o.currency, o.payment_provider, o.receipt_number, o.points_earned,
                   o.paid_at, o.created_at
            FROM orders o
            JOIN community_events ce ON ce.id = o.community_event_id
            WHERE o.user_id = :uid
            ORDER BY o.created_at DESC
            """
        ),
        {"uid": user_id},
    ).fetchall()
    return [
        OrderResponse(
            order_id=r[0],
            community_event_id=r[1],
            event_title=r[2],
            status=r[3],
            type=r[4],
            total_minor_units=r[5],
            platform_fee_minor_units=r[6],
            business_net_minor_units=r[7],
            currency=r[8],
            payment_provider=r[9],
            receipt_number=r[10],
            points_earned=r[11],
            paid_at=r[12],
            created_at=r[13],
        )
        for r in rows
    ]


@router.get("/tickets/orders/{order_id}", status_code=status.HTTP_200_OK, response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text(
            """
            SELECT o.id, o.community_event_id, ce.title, o.status, o.type,
                   o.total_minor_units, o.platform_fee_minor_units, o.business_net_minor_units,
                   o.currency, o.payment_provider, o.receipt_number, o.points_earned,
                   o.paid_at, o.created_at
            FROM orders o
            JOIN community_events ce ON ce.id = o.community_event_id
            WHERE o.id = :oid AND o.user_id = :uid
            LIMIT 1
            """
        ),
        {"oid": str(order_id), "uid": user_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")

    ticket_rows = session.execute(
        text(
            """
            SELECT t.id, t.short_code, tt.name, t.status, t.checked_in_at
            FROM tickets t
            JOIN ticket_types tt ON tt.id = t.ticket_type_id
            WHERE t.order_id = :oid
            ORDER BY t.created_at ASC
            """
        ),
        {"oid": str(order_id)},
    ).fetchall()

    return OrderResponse(
        order_id=row[0],
        community_event_id=row[1],
        event_title=row[2],
        status=row[3],
        type=row[4],
        total_minor_units=row[5],
        platform_fee_minor_units=row[6],
        business_net_minor_units=row[7],
        currency=row[8],
        payment_provider=row[9],
        receipt_number=row[10],
        points_earned=row[11],
        paid_at=row[12],
        created_at=row[13],
        tickets=[
            OrderTicketRow(ticket_id=t[0], short_code=t[1], ticket_type_name=t[2], status=t[3], checked_in_at=t[4])
            for t in ticket_rows
        ],
    )


@router.post("/tickets/orders/{order_id}/resend", status_code=status.HTTP_200_OK, response_model=TicketResendResponse)
async def resend_tickets(
    order_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text("SELECT id FROM orders WHERE id = :oid AND user_id = :uid LIMIT 1"),
        {"oid": str(order_id), "uid": user_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    tickets = session.execute(
        text("SELECT short_code FROM tickets WHERE order_id = :oid AND status = 'active'"),
        {"oid": str(order_id)},
    ).fetchall()
    return {"tickets": [t[0] for t in tickets]}


@router.get("/tickets/{short_code}", status_code=status.HTTP_200_OK, response_model=TicketLookupResponse)
async def get_ticket(
    short_code: str,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text(
            """
            SELECT t.id, t.short_code, tt.name as ticket_type, ce.title as event_title,
                   ce.start_time, ce.venue, t.status, t.checked_in_at
            FROM tickets t
            JOIN ticket_types tt ON tt.id = t.ticket_type_id
            JOIN community_events ce ON ce.id = t.community_event_id
            WHERE t.short_code = :code
            LIMIT 1
            """
        ),
        {"code": short_code},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "ticket_id": str(row[0]),
        "short_code": row[1],
        "ticket_type": row[2],
        "event_title": row[3],
        "start_time": row[4],
        "venue": row[5],
        "status": row[6],
        "checked_in_at": row[7],
    }


# ─── Check-in ────────────────────────────────────────────────────────────


@router.post("/business/check-in/{short_code}", status_code=status.HTTP_200_OK, response_model=CheckInResponse)
async def check_in_ticket(
    short_code: str,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    ticket = session.execute(
        text(
            """
            SELECT t.id, t.status, ce.user_id as owner_id
            FROM tickets t
            JOIN community_events ce ON ce.id = t.community_event_id
            WHERE t.short_code = :code LIMIT 1
            """
        ),
        {"code": short_code},
    ).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket[1] != "active":
        raise HTTPException(status_code=400, detail=f"Ticket is {ticket[1]}")

    # Verify the user is the event organizer
    if ticket[2] != user_id:
        raise HTTPException(status_code=403, detail="Only the event organizer can check in")

    session.execute(
        text("UPDATE tickets SET status = 'used', checked_in_at = :now, checked_in_by = :uid WHERE id = :id"),
        {"now": now, "uid": user_id, "id": str(ticket[0])},
    )
    session.commit()
    return {"ok": True, "checked_in_at": now}


# ─── Business Dashboard ──────────────────────────────────────────────────


@router.get("/business/dashboard", status_code=status.HTTP_200_OK, response_model=DashboardResponse)
async def business_dashboard(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id, name, tap_balance, tap_plan FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="No business found for this user")

    biz_id = biz[0]

    # Aggregate sales
    sales = session.execute(
        text(
            """
            SELECT ce.id, ce.title, ce.start_time,
                   COUNT(DISTINCT t.id) as tickets_sold,
                   COALESCE(SUM(o.total_minor_units), 0) as revenue,
                   COALESCE(SUM(o.platform_fee_minor_units), 0) as fees,
                   COUNT(DISTINCT CASE WHEN t.checked_in_at IS NOT NULL THEN t.id END) as checked_in
            FROM community_events ce
            LEFT JOIN tickets t ON t.community_event_id = ce.id AND t.status = 'active'
            LEFT JOIN orders o ON o.id = t.order_id
            WHERE ce.user_id = :uid
            GROUP BY ce.id, ce.title, ce.start_time
            ORDER BY ce.start_time DESC
            LIMIT 50
            """
        ),
        {"uid": user_id},
    ).fetchall()

    total_revenue = sum(r[4] or 0 for r in sales)
    total_fees = sum(r[5] or 0 for r in sales)
    total_tickets = sum(r[3] or 0 for r in sales)

    # Affiliate earnings
    aff_earnings = session.execute(
        text(
            "SELECT COALESCE(SUM(earned_minor_units), 0) FROM affiliate_earnings WHERE affiliate_business_id = :bid"
        ),
        {"bid": str(biz_id)},
    ).scalar_one()

    # Payout available
    payouts_done = session.execute(
        text(
            "SELECT COALESCE(SUM(net_payout_minor_units), 0) FROM business_payouts WHERE business_id = :bid AND status = 'paid'"
        ),
        {"bid": str(biz_id)},
    ).scalar_one()
    available = (total_revenue - total_fees) + aff_earnings - payouts_done

    return DashboardResponse(
        business_id=biz_id,
        business_name=biz[1],
        total_revenue_minor=total_revenue,
        total_fees_minor=total_fees,
        net_available_minor=max(0, available),
        total_tickets_sold=total_tickets,
        tap_balance=biz[2],
        tap_plan=biz[3],
        affiliate_earnings_minor=aff_earnings,
        listings=[
            DashboardListingRow(
                community_event_id=r[0],
                title=r[1],
                start_time=r[2],
                tickets_sold=r[3] or 0,
                revenue_minor=r[4] or 0,
                fees_minor=r[5] or 0,
                checked_in=r[6] or 0,
            )
            for r in sales
        ],
    )


@router.get("/business/events/{community_event_id}/sales", status_code=status.HTTP_200_OK, response_model=list[SalesDetailRow])
async def event_sales_detail(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_listing_owner(session, community_event_id, user_id)

    rows = session.execute(
        text(
            """
            SELECT tt.name, tt.price_minor_units, tt.quantity_sold,
                   COUNT(t.id) FILTER (WHERE t.status = 'active') as active_tickets,
                   COUNT(t.id) FILTER (WHERE t.checked_in_at IS NOT NULL) as checked_in
            FROM ticket_types tt
            LEFT JOIN tickets t ON t.ticket_type_id = tt.id
            WHERE tt.community_event_id = :ce AND tt.is_active = true
            GROUP BY tt.id, tt.name, tt.price_minor_units, tt.quantity_sold
            ORDER BY tt.sort_order ASC
            """
        ),
        {"ce": str(community_event_id)},
    ).fetchall()
    return [
        {
            "name": r[0],
            "price_minor_units": r[1],
            "sold": r[2],
            "active": r[3],
            "checked_in": r[4],
        }
        for r in rows
    ]


# ─── Tap Packs ───────────────────────────────────────────────────────────


@router.get("/business/taps", status_code=status.HTTP_200_OK, response_model=TapPackResponse)
async def tap_status(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id, name, tap_balance, tap_plan FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    pricing = _get_platform_setting(session, "tap_pricing")
    return TapPackResponse(
        business_id=biz[0],
        tap_balance=biz[2],
        tap_plan=biz[3],
        pricing=pricing,
    )


@router.post("/business/taps/buy", status_code=status.HTTP_200_OK, response_model=TapPackResponse)
async def buy_tap_pack(
    body: TapPackBuyRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    pricing = _get_platform_setting(session, "tap_pricing")
    plan_info = pricing.get(body.plan)
    if not plan_info:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    taps = plan_info.get("taps")

    if body.plan == "unlimited":
        session.execute(
            text(
                "UPDATE businesses SET tap_plan = 'unlimited', tap_balance = 999999 WHERE id = :id"
            ),
            {"id": str(biz[0])},
        )
    else:
        session.execute(
            text(
                "UPDATE businesses SET tap_plan = :plan, tap_balance = tap_balance + :taps WHERE id = :id"
            ),
            {"plan": body.plan, "taps": taps, "id": str(biz[0])},
        )
    session.commit()
    return await tap_status(user_id=user_id, session=session)


# ─── Feed Videos ─────────────────────────────────────────────────────────


@router.post("/feed/videos", status_code=status.HTTP_201_CREATED, response_model=FeedVideoResponse)
async def publish_feed_video(
    body: FeedVideoPublishRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    if body.community_event_id:
        attached = session.execute(
            text(
                "SELECT 1 FROM business_listing_attachments WHERE community_event_id = :ce AND business_id = :bid LIMIT 1"
            ),
            {"ce": str(body.community_event_id), "bid": str(biz[0])},
        ).first()
        if attached is None:
            raise HTTPException(status_code=403, detail="Event not attached to your business")

    vid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO feed_videos (id, business_id, community_event_id, title,
                video_uri, thumbnail_uri, video_type, countdown_target,
                moderation_status, is_paid, sort_order, created_at)
            VALUES (:id, :bid, :ce, :title, :uri, :thumb, :vtype, :ct,
                'pending', :paid, :so, :now)
            """
        ),
        {
            "id": vid,
            "bid": str(biz[0]),
            "ce": str(body.community_event_id) if body.community_event_id else None,
            "title": body.title,
            "uri": body.video_uri,
            "thumb": body.thumbnail_uri,
            "vtype": body.video_type or "promo",
            "ct": body.countdown_target,
            "paid": body.is_paid or False,
            "so": body.sort_order or 0,
            "now": now,
        },
    )
    session.commit()
    return FeedVideoResponse(video_id=vid, moderation_status="pending")


@router.get("/feed/videos", status_code=status.HTTP_200_OK, response_model=list[FeedVideoResponse])
async def list_my_feed_videos(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT id, title, video_uri, thumbnail_uri, video_type, moderation_status,
                   views, whatsapp_taps, created_at
            FROM feed_videos WHERE business_id = :bid ORDER BY created_at DESC
            """
        ),
        {"bid": str(biz[0])},
    ).fetchall()
    return [
        FeedVideoResponse(
            video_id=r[0],
            title=r[1],
            video_uri=r[2],
            thumbnail_uri=r[3],
            video_type=r[4],
            moderation_status=r[5],
            views=r[6],
            whatsapp_taps=r[7],
            created_at=r[8],
        )
        for r in rows
    ]


# ─── Discovery Feed (user-facing) ────────────────────────────────────────


@router.get("/feed/discover", status_code=status.HTTP_200_OK, response_model=list[FeedVideoResponse])
async def discover_feed(
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT fv.id, fv.title, fv.video_uri, fv.thumbnail_uri, fv.video_type,
                   fv.moderation_status, fv.views, fv.whatsapp_taps, fv.created_at,
                   b.name as business_name, ce.title as event_title, ce.id as event_id
            FROM feed_videos fv
            JOIN businesses b ON b.id = fv.business_id
            LEFT JOIN community_events ce ON ce.id = fv.community_event_id
            WHERE fv.moderation_status = 'approved' AND fv.is_paid = true
            ORDER BY fv.sort_order ASC, fv.created_at DESC
            LIMIT 100
            """
        ),
    ).fetchall()
    return [
        FeedVideoResponse(
            video_id=r[0],
            title=r[1],
            video_uri=r[2],
            thumbnail_uri=r[3],
            video_type=r[4],
            moderation_status=r[5],
            views=r[6],
            whatsapp_taps=r[7],
            created_at=r[8],
            business_name=r[9],
            event_title=r[10],
            community_event_id=r[11],
        )
        for r in rows
    ]


@router.post("/feed/watch", status_code=status.HTTP_200_OK, response_model=FeedWatchResponse)
async def log_video_watch(
    video_id: UUID,
    completed: bool = Query(default=True),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)

    # Log watch
    log_id = uuid4()
    points = 1 if completed else 0
    session.execute(
        text(
            """
            INSERT INTO feed_watch_log (id, user_id, feed_video_id, watched_seconds,
                completed, points_earned, watched_at)
            VALUES (:id, :uid, :vid, :sec, :comp, :pts, :now)
            """
        ),
        {
            "id": log_id,
            "uid": user_id,
            "vid": str(video_id),
            "sec": 30 if completed else 5,
            "comp": completed,
            "pts": points,
            "now": now,
        },
    )

    # Update video view count
    session.execute(
        text(
            "UPDATE feed_videos SET views = views + 1, completion_rate = "
            "(SELECT COUNT(*) FROM feed_watch_log WHERE feed_video_id = :vid AND completed = true)::numeric / "
            "GREATEST(views + 1, 1) WHERE id = :vid"
        ),
        {"vid": str(video_id)},
    )

    # Add points to user
    if points > 0:
        session.execute(
            text(
                """
                INSERT INTO user_points (user_id, balance, lifetime_earned, last_activity, created_at)
                VALUES (:uid, :pts, :pts, :now, :now)
                ON CONFLICT (user_id) DO UPDATE SET
                    balance = user_points.balance + :pts2,
                    lifetime_earned = user_points.lifetime_earned + :pts2,
                    last_activity = :now
                """
            ),
            {"uid": user_id, "pts": points, "pts2": points, "now": now},
        )

    session.commit()
    return FeedWatchResponse(points_earned=points)


@router.get("/feed/status", status_code=status.HTTP_200_OK, response_model=WatchQuotaResponse)
async def feed_watch_status(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    quota = _get_platform_setting(session, "user_watch_quota")
    daily_limit = quota.get("videos_per_day", 10)
    premium_price = quota.get("premium_price_minor", 30000)

    # Check if user is premium
    sub = session.execute(
        text(
            "SELECT status FROM user_subscriptions WHERE user_id = :uid AND status = 'active' AND current_period_end > :now LIMIT 1"
        ),
        {"uid": user_id, "now": now},
    ).first()

    if sub:
        return WatchQuotaResponse(
            is_premium=True,
            videos_watched_today=0,
            videos_remaining=0,
            daily_limit=daily_limit,
            premium_price_minor=premium_price,
        )

    watched_today = session.execute(
        text(
            "SELECT COUNT(*) FROM feed_watch_log WHERE user_id = :uid AND watched_at >= :today AND completed = true"
        ),
        {"uid": user_id, "today": today_start},
    ).scalar_one()

    return WatchQuotaResponse(
        is_premium=False,
        videos_watched_today=watched_today,
        videos_remaining=max(0, daily_limit - watched_today),
        daily_limit=daily_limit,
        premium_price_minor=premium_price,
    )


# ─── Affiliate Products ──────────────────────────────────────────────────


@router.post("/business/products", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
async def create_product(
    body: ProductCreateRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    pid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO products (id, business_id, title, description, price_minor_units,
                currency, image_uri, created_at, updated_at)
            VALUES (:id, :bid, :title, :desc, :price, 'KES', :img, :now, :now)
            """
        ),
        {
            "id": pid,
            "bid": str(biz[0]),
            "title": body.title,
            "desc": body.description,
            "price": body.price_minor_units,
            "img": body.image_uri,
            "now": now,
        },
    )
    session.commit()
    return ProductResponse(
        product_id=pid,
        title=body.title,
        description=body.description,
        price_minor_units=body.price_minor_units,
        image_uri=body.image_uri,
        is_active=True,
    )


@router.get("/business/products", status_code=status.HTTP_200_OK, response_model=list[ProductResponse])
async def list_my_products(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        return []
    rows = session.execute(
        text(
            "SELECT id, title, description, price_minor_units, image_uri, is_active "
            "FROM products WHERE business_id = :bid ORDER BY created_at DESC"
        ),
        {"bid": str(biz[0])},
    ).fetchall()
    return [
        ProductResponse(product_id=r[0], title=r[1], description=r[2], price_minor_units=r[3], image_uri=r[4], is_active=r[5])
        for r in rows
    ]


@router.put(
    "/events/{community_event_id}/products/link",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def link_product_to_event(
    community_event_id: UUID,
    body: ProductEventLinkRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Get the event owner's business
    event_owner = session.execute(
        text("SELECT user_id FROM community_events WHERE id = :ce LIMIT 1"),
        {"ce": str(community_event_id)},
    ).first()
    if event_owner is None:
        raise HTTPException(status_code=404, detail="Event not found")

    owner_biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": event_owner[0]},
    ).first()

    # Verify product belongs to requester's business
    product = session.execute(
        text("SELECT id, business_id FROM products WHERE id = :pid LIMIT 1"),
        {"pid": str(body.product_id)},
    ).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product_biz = session.execute(
        text("SELECT owner_user_id FROM businesses WHERE id = :bid LIMIT 1"),
        {"bid": str(product[1])},
    ).first()
    if product_biz is None or product_biz[0] != user_id:
        raise HTTPException(status_code=403, detail="Not your product")

    # Auto-approve if the product owner is also the event owner
    status_val = "approved" if (owner_biz and product[1] == owner_biz[0]) else "pending"

    now = datetime.now(timezone.utc)
    link_id = uuid4()
    session.execute(
        text(
            """
            INSERT INTO product_event_links (id, product_id, community_event_id,
                seller_business_id, event_owner_business_id,
                commission_seller_percent, commission_owner_percent, commission_platform_percent,
                status, approved_at, created_at)
            VALUES (:id, :pid, :ce, :seller, :owner, :cs, :co, :cp, :st,
                CASE WHEN :st = 'approved' THEN :now ELSE NULL END, :now)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": link_id,
            "pid": str(body.product_id),
            "ce": str(community_event_id),
            "seller": str(product[1]),
            "owner": str(owner_biz[0]) if owner_biz else product[1],
            "cs": body.commission_seller_percent or 80,
            "co": body.commission_owner_percent or 10,
            "cp": body.commission_platform_percent or 10,
            "st": status_val,
            "now": now,
        },
    )
    session.execute(
        text("UPDATE community_events SET has_products = true WHERE id = :ce"),
        {"ce": str(community_event_id)},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/events/{community_event_id}/products",
    status_code=status.HTTP_200_OK,
    response_model=list[ProductEventLinkResponse],
)
async def get_event_products(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    """Visible only to users who have bought a ticket to this event."""
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Verify user bought a ticket
    has_ticket = session.execute(
        text(
            "SELECT 1 FROM tickets WHERE community_event_id = :ce AND user_id = :uid AND status = 'active' LIMIT 1"
        ),
        {"ce": str(community_event_id), "uid": user_id},
    ).first()
    if has_ticket is None:
        raise HTTPException(status_code=403, detail="Buy a ticket first to see affiliate products")

    rows = session.execute(
        text(
            """
            SELECT pel.id, p.id, p.title, p.description, p.price_minor_units, p.image_uri,
                   b.name as seller_name, pel.status
            FROM product_event_links pel
            JOIN products p ON p.id = pel.product_id
            JOIN businesses b ON b.id = p.business_id
            WHERE pel.community_event_id = :ce AND pel.status = 'approved' AND p.is_active = true
            ORDER BY pel.created_at ASC
            """
        ),
        {"ce": str(community_event_id)},
    ).fetchall()
    return [
        ProductEventLinkResponse(
            link_id=r[0],
            product_id=r[1],
            title=r[2],
            description=r[3],
            price_minor_units=r[4],
            image_uri=r[5],
            seller_name=r[6],
        )
        for r in rows
    ]


@router.get(
    "/business/affiliate-requests",
    status_code=status.HTTP_200_OK,
    response_model=list[ProductEventLinkResponse],
)
async def list_affiliate_requests(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT pel.id, p.id, p.title, p.description, p.price_minor_units, p.image_uri,
                   b.name as seller_name, pel.status, pel.commission_seller_percent,
                   pel.commission_owner_percent, pel.commission_platform_percent
            FROM product_event_links pel
            JOIN products p ON p.id = pel.product_id
            JOIN businesses b ON b.id = p.business_id
            WHERE pel.event_owner_business_id = :bid AND pel.status = 'pending'
            ORDER BY pel.created_at DESC
            """
        ),
        {"bid": str(biz[0])},
    ).fetchall()
    return [
        ProductEventLinkResponse(
            link_id=r[0],
            product_id=r[1],
            title=r[2],
            description=r[3],
            price_minor_units=r[4],
            image_uri=r[5],
            seller_name=r[6],
            status=r[7],
            commission_seller_percent=r[8],
            commission_owner_percent=r[9],
            commission_platform_percent=r[10],
        )
        for r in rows
    ]


@router.post(
    "/business/affiliate-requests/{link_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def approve_affiliate_request(
    link_id: UUID,
    body: ProductEventLinkApproveRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            UPDATE product_event_links
            SET status = 'approved', approved_at = :now,
                commission_seller_percent = :cs,
                commission_owner_percent = :co,
                commission_platform_percent = :cp
            WHERE id = :id AND event_owner_business_id = :bid AND status = 'pending'
            """
        ),
        {
            "id": str(link_id),
            "bid": str(biz[0]),
            "cs": body.commission_seller_percent,
            "co": body.commission_owner_percent,
            "cp": body.commission_platform_percent,
            "now": now,
        },
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Payouts ─────────────────────────────────────────────────────────────


@router.get("/business/payout-settings", status_code=status.HTTP_200_OK, response_model=PayoutSettingsResponse)
async def get_payout_settings(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")
    row = session.execute(
        text("SELECT * FROM business_payout_settings WHERE business_id = :bid LIMIT 1"),
        {"bid": str(biz[0])},
    ).first()
    if row is None:
        return {
            "payout_method": "mpesa_till",
            "mpesa_till_number": None,
            "mpesa_paybill_number": None,
            "bank_name": None,
            "payout_frequency": "manual",
            "minimum_payout_minor": 50000,
        }
    return dict(row._mapping)


@router.put("/business/payout-settings", status_code=status.HTTP_204_NO_CONTENT)
async def update_payout_settings(
    body: PayoutRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO business_payout_settings (business_id, payout_method,
                mpesa_till_number, mpesa_paybill_number, mpesa_account_ref,
                bank_name, bank_account_name, bank_account_number, bank_branch_code,
                payout_frequency, minimum_payout_minor, updated_at)
            VALUES (:bid, :method, :till, :paybill, :ref, :bank, :bank_name, :bank_acct, :branch,
                :freq, :min, :now)
            ON CONFLICT (business_id) DO UPDATE SET
                payout_method = :method2,
                mpesa_till_number = :till2,
                mpesa_paybill_number = :paybill2,
                mpesa_account_ref = :ref2,
                bank_name = :bank2,
                bank_account_name = :bank_name2,
                bank_account_number = :bank_acct2,
                bank_branch_code = :branch2,
                payout_frequency = :freq2,
                minimum_payout_minor = :min2,
                updated_at = :now
            """
        ),
        {
            "bid": str(biz[0]),
            "method": body.payout_method,
            "till": body.mpesa_till_number,
            "paybill": body.mpesa_paybill_number,
            "ref": body.mpesa_account_ref,
            "bank": body.bank_name,
            "bank_name": body.bank_account_name,
            "bank_acct": body.bank_account_number,
            "branch": body.bank_branch_code,
            "freq": body.payout_frequency,
            "min": body.minimum_payout_minor,
            "now": now,
            "method2": body.payout_method,
            "till2": body.mpesa_till_number,
            "paybill2": body.mpesa_paybill_number,
            "ref2": body.mpesa_account_ref,
            "bank2": body.bank_name,
            "bank_name2": body.bank_account_name,
            "bank_acct2": body.bank_account_number,
            "branch2": body.bank_branch_code,
            "freq2": body.payout_frequency,
            "min2": body.minimum_payout_minor,
        },
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/business/payouts", status_code=status.HTTP_200_OK, response_model=list[PayoutResponse])
async def list_payouts(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    biz = session.execute(
        text("SELECT id FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT id, period_start, period_end, gross_minor_units, platform_fees_minor_units,
                   net_payout_minor_units, status, payment_reference, paid_at, created_at
            FROM business_payouts WHERE business_id = :bid ORDER BY created_at DESC
            """
        ),
        {"bid": str(biz[0])},
    ).fetchall()
    return [
        PayoutResponse(
            payout_id=r[0],
            period_start=r[1],
            period_end=r[2],
            gross_minor_units=r[3],
            fees_minor_units=r[4],
            net_minor_units=r[5],
            status=r[6],
            payment_reference=r[7],
            paid_at=r[8],
            created_at=r[9],
        )
        for r in rows
    ]


@router.post("/business/payouts/request", status_code=status.HTTP_201_CREATED, response_model=PayoutRequestResponse)
async def request_payout(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    biz = session.execute(
        text("SELECT id, name FROM businesses WHERE owner_user_id = :uid LIMIT 1"),
        {"uid": user_id},
    ).first()
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    # Available balance (lock settings to serialize concurrent payout requests)
    settings = session.execute(
        text("SELECT * FROM business_payout_settings WHERE business_id = :bid LIMIT 1 FOR UPDATE"),
        {"bid": str(biz[0])},
    ).first()

    sales = session.execute(
        text(
            """
            SELECT COALESCE(SUM(o.total_minor_units), 0) as total,
                   COALESCE(SUM(o.platform_fee_minor_units), 0) as fees
            FROM community_events ce
            JOIN orders o ON o.community_event_id = ce.id
            WHERE ce.user_id = :uid AND o.status = 'confirmed'
            """
        ),
        {"uid": user_id},
    ).first()

    aff = session.execute(
        text(
            "SELECT COALESCE(SUM(earned_minor_units), 0) FROM affiliate_earnings "
            "WHERE affiliate_business_id = :bid AND paid = false"
        ),
        {"bid": str(biz[0])},
    ).scalar_one()

    paid_out = session.execute(
        text(
            "SELECT COALESCE(SUM(net_payout_minor_units), 0) FROM business_payouts "
            "WHERE business_id = :bid AND status = 'paid'"
        ),
        {"bid": str(biz[0])},
    ).scalar_one()

    gross = (sales[0] or 0) + aff
    fees = sales[1] or 0
    net = gross - fees - paid_out

    min_payout = settings.minimum_payout_minor if settings else 50000
    if net < min_payout:
        raise HTTPException(status_code=400, detail=f"Minimum payout is KES {min_payout/100:.0f}. Available: KES {net/100:.0f}")

    now = datetime.now(timezone.utc)
    pid = uuid4()
    session.execute(
        text(
            """
            INSERT INTO business_payouts (id, business_id, period_start, period_end,
                gross_minor_units, platform_fees_minor_units, net_payout_minor_units,
                type, currency, status, payout_method_snapshot, created_at)
            VALUES (:id, :bid, :ps, :pe, :gross, :fees, :net, 'ticket_sales', 'KES', 'pending',
                :snapshot, :now)
            """
        ),
        {
            "id": pid,
            "bid": str(biz[0]),
            "ps": now.replace(day=1),
            "pe": now,
            "gross": gross,
            "fees": fees,
            "net": net,
            "snapshot": Json(dict(settings._mapping) if settings else {}),
            "now": now,
        },
    )
    session.commit()
    return {"payout_id": pid, "amount_minor": net, "status": "pending"}


# ─── Claims ──────────────────────────────────────────────────────────────


@router.post("/tickets/claims", status_code=status.HTTP_201_CREATED, response_model=ClaimResponse)
async def submit_claim(
    body: ClaimCreateRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Verify order belongs to user
    order = session.execute(
        text(
            "SELECT id, community_event_id, status, total_minor_units FROM orders WHERE id = :oid AND user_id = :uid LIMIT 1"
        ),
        {"oid": str(body.order_id), "uid": user_id},
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check existing open claim
    existing = session.execute(
        text("SELECT 1 FROM claims WHERE order_id = :oid AND status = 'open' LIMIT 1"),
        {"oid": str(body.order_id)},
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have an open claim for this order")

    cid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO claims (id, order_id, user_id, claim_type, reason, status, created_at)
            VALUES (:id, :oid, :uid, :type, :reason, 'open', :now)
            """
        ),
        {
            "id": cid,
            "oid": str(body.order_id),
            "uid": user_id,
            "type": body.claim_type,
            "reason": body.reason,
            "now": now,
        },
    )
    session.commit()
    return ClaimResponse(claim_id=cid, status="open", created_at=now)


@router.get("/tickets/claims", status_code=status.HTTP_200_OK, response_model=list[ClaimResponse])
async def list_my_claims(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text(
            "SELECT id, order_id, claim_type, reason, status, admin_notes, created_at, resolved_at "
            "FROM claims WHERE user_id = :uid ORDER BY created_at DESC"
        ),
        {"uid": user_id},
    ).fetchall()
    return [
        ClaimResponse(claim_id=r[0], order_id=r[1], claim_type=r[2], reason=r[3], status=r[4], admin_notes=r[5], created_at=r[6], resolved_at=r[7])
        for r in rows
    ]


# ─── Points & Subscriptions ──────────────────────────────────────────────


@router.get("/points", status_code=status.HTTP_200_OK, response_model=PointsResponse)
async def get_points(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return PointsResponse(balance=0, lifetime_earned=0, lifetime_redeemed=0)
    row = session.execute(
        text(
            "SELECT balance, lifetime_earned, lifetime_redeemed, last_activity "
            "FROM user_points WHERE user_id = :uid LIMIT 1"
        ),
        {"uid": user_id},
    ).first()
    if row is None:
        return PointsResponse(balance=0, lifetime_earned=0, lifetime_redeemed=0)
    return PointsResponse(balance=row[0], lifetime_earned=row[1], lifetime_redeemed=row[2], last_activity=row[3])


@router.post("/points/redeem", status_code=status.HTTP_200_OK, response_model=PointsResponse)
async def redeem_points(
    body: RedeemPointsRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text("SELECT balance FROM user_points WHERE user_id = :uid LIMIT 1 FOR UPDATE"),
        {"uid": user_id},
    ).first()
    current_balance = row[0] if row else 0
    if current_balance < body.points:
        raise HTTPException(status_code=400, detail=f"Not enough points. You have {current_balance}.")
    now = datetime.now(timezone.utc)
    discount_minor = body.points * 500
    session.execute(
        text(
            """
            INSERT INTO user_points (user_id, balance, lifetime_earned, lifetime_redeemed, last_activity, created_at)
            VALUES (:uid, 0, 0, 0, :now, :now)
            ON CONFLICT (user_id) DO UPDATE SET
                balance = user_points.balance - :pts,
                lifetime_redeemed = user_points.lifetime_redeemed + :pts,
                last_activity = :now
            """
        ),
        {"uid": user_id, "pts": body.points, "now": now},
    )
    session.commit()
    return PointsResponse(
        balance=current_balance - body.points,
        discount_code=f"PTS-{secrets.token_hex(4).upper()}",
        discount_minor=discount_minor,
    )


@router.post("/subscriptions/create", status_code=status.HTTP_201_CREATED, response_model=SubscriptionResponse)
async def create_subscription(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    y = now.year + (now.month // 12)
    m = (now.month % 12) + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(now.day, last_day)
    period_end = now.replace(year=y, month=m, day=day, hour=23, minute=59, second=59, microsecond=999999)
    sid = uuid4()
    session.execute(
        text(
            """
            INSERT INTO user_subscriptions (id, user_id, plan, status, current_period_start, current_period_end, created_at)
            VALUES (:id, :uid, 'premium', 'active', :now, :pe, :now)
            ON CONFLICT (user_id) DO UPDATE SET
                status = 'active', current_period_start = :now2, current_period_end = :pe2, plan = 'premium'
            """
        ),
        {"id": sid, "uid": user_id, "now": now, "pe": period_end, "now2": now, "pe2": period_end},
    )
    session.commit()
    return SubscriptionResponse(subscription_id=sid, plan="premium", status="active", current_period_end=period_end)


@router.get("/subscriptions", status_code=status.HTTP_200_OK, response_model=SubscriptionResponse | None)
async def get_subscription(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return None
    now = datetime.now(timezone.utc)
    row = session.execute(
        text(
            "SELECT id, plan, status, current_period_end, created_at "
            "FROM user_subscriptions WHERE user_id = :uid AND status = 'active' AND current_period_end > :now LIMIT 1"
        ),
        {"uid": user_id, "now": now},
    ).first()
    if row is None:
        return None
    return SubscriptionResponse(subscription_id=row[0], plan=row[1], status=row[2], current_period_end=row[3], created_at=row[4])


@router.delete("/subscriptions/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    session.execute(
        text("UPDATE user_subscriptions SET status = 'cancelled' WHERE user_id = :uid"),
        {"uid": user_id},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Admin Endpoints ──────────────────────────────────────────────────────


@router.get("/admin/console/orders", status_code=status.HTTP_200_OK, response_model=list[AdminOrderRow])
async def admin_list_orders(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text(
            """
            SELECT o.id, o.user_id, ce.title, o.status, o.total_minor_units,
                   o.platform_fee_minor_units, o.payment_provider, o.created_at
            FROM orders o
            JOIN community_events ce ON ce.id = o.community_event_id
            ORDER BY o.created_at DESC LIMIT :lim OFFSET :off
            """
        ),
        {"lim": limit, "off": offset},
    ).fetchall()
    return [
        {
            "order_id": str(r[0]),
            "user_id": str(r[1]),
            "event_title": r[2],
            "status": r[3],
            "total_minor": r[4],
            "fee_minor": r[5],
            "payment_provider": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


@router.get("/admin/console/claims", status_code=status.HTTP_200_OK, response_model=list[AdminClaimRow])
async def admin_list_claims(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    where = ""
    params = {"lim": limit, "off": offset}
    if status_filter:
        where = "WHERE c.status = :st"
        params["st"] = status_filter
    rows = session.execute(
        text(
            f"""
            SELECT c.id, c.order_id, c.user_id, c.claim_type, c.reason, c.status,
                   c.admin_notes, c.created_at, c.resolved_at
            FROM claims c {where}
            ORDER BY c.created_at DESC LIMIT :lim OFFSET :off
            """
        ),
        params,
    ).fetchall()
    return [
        {
            "claim_id": str(r[0]),
            "order_id": str(r[1]),
            "user_id": str(r[2]),
            "claim_type": r[3],
            "reason": r[4],
            "status": r[5],
            "admin_notes": r[6],
            "created_at": r[7],
            "resolved_at": r[8],
        }
        for r in rows
    ]


@router.patch("/admin/console/claims/{claim_id}", status_code=status.HTTP_200_OK, response_model=AdminResolveResponse)
async def admin_resolve_claim(
    claim_id: UUID,
    body: AdminClaimResolveRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    claim = session.execute(
        text("SELECT id, order_id, status FROM claims WHERE id = :id LIMIT 1"),
        {"id": str(claim_id)},
    ).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim[2] != "open":
        raise HTTPException(status_code=400, detail="Claim already resolved")

    new_status = body.claim_type

    if new_status == "resolved_approved":
        session.execute(
            text("UPDATE orders SET status = 'refunded', updated_at = :now WHERE id = :oid"),
            {"now": now, "oid": str(claim[1])},
        )
        session.execute(
            text("UPDATE tickets SET status = 'refunded' WHERE order_id = :oid"),
            {"oid": str(claim[1])},
        )

    session.execute(
        text(
            "UPDATE claims SET status = :st, admin_notes = :notes, resolved_by = :admin, resolved_at = :now WHERE id = :id"
        ),
        {
            "st": new_status,
            "notes": body.admin_notes,
            "admin": _admin,
            "now": now,
            "id": str(claim[0]),
        },
    )
    session.commit()
    return {"ok": True, "status": new_status}


@router.get("/admin/console/payouts", status_code=status.HTTP_200_OK, response_model=list[AdminPayoutRow])
async def admin_list_payouts(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text(
            """
            SELECT bp.id, b.name, bp.gross_minor_units, bp.platform_fees_minor_units,
                   bp.net_payout_minor_units, bp.status, bp.payment_reference, bp.created_at
            FROM business_payouts bp
            JOIN businesses b ON b.id = bp.business_id
            ORDER BY bp.created_at DESC LIMIT :lim OFFSET :off
            """
        ),
        {"lim": limit, "off": offset},
    ).fetchall()
    return [
        {
            "payout_id": str(r[0]),
            "business_name": r[1],
            "gross_minor": r[2],
            "fees_minor": r[3],
            "net_minor": r[4],
            "status": r[5],
            "reference": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


@router.post("/admin/console/payouts/{payout_id}/process", status_code=status.HTTP_200_OK, response_model=AdminProcessPayoutResponse)
async def admin_process_payout(
    payout_id: UUID,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            "UPDATE business_payouts SET status = 'paid', paid_at = :now, payment_reference = :ref WHERE id = :id AND status = 'pending'"
        ),
        {"now": now, "ref": f"ADMIN-{secrets.token_hex(4).upper()}", "id": str(payout_id)},
    )
    session.commit()
    return {"ok": True}


@router.get("/admin/console/platform-settings", status_code=status.HTTP_200_OK, response_model=list[PlatformSettingsResponse])
async def admin_get_platform_settings(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text("SELECT key, value, updated_at FROM platform_settings ORDER BY key ASC")
    ).fetchall()
    return [PlatformSettingsResponse(key=r[0], value=r[1], updated_at=r[2]) for r in rows]


@router.put("/admin/console/platform-settings", status_code=status.HTTP_204_NO_CONTENT)
async def admin_update_platform_setting(
    body: PlatformSettingsUpdateRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            "INSERT INTO platform_settings (key, value, updated_at) VALUES (:k, :v, :now) "
            "ON CONFLICT (key) DO UPDATE SET value = :v2, updated_at = :now"
        ),
        {"k": body.key, "v": Json(body.value), "v2": Json(body.value), "now": now},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/console/videos", status_code=status.HTTP_200_OK, response_model=list[AdminVideoRow])
async def admin_list_videos(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text(
            """
            SELECT fv.id, fv.title, b.name, fv.moderation_status, fv.views, fv.created_at
            FROM feed_videos fv
            JOIN businesses b ON b.id = fv.business_id
            ORDER BY fv.created_at DESC LIMIT :lim OFFSET :off
            """
        ),
        {"lim": limit, "off": offset},
    ).fetchall()
    return [
        {
            "video_id": str(r[0]),
            "title": r[1],
            "business_name": r[2],
            "moderation_status": r[3],
            "views": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


@router.patch("/admin/console/videos/{video_id}/moderation", status_code=status.HTTP_200_OK, response_model=AdminModerateResponse)
async def admin_moderate_video(
    video_id: UUID,
    body: VideoModerationRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    session.execute(
        text("UPDATE feed_videos SET moderation_status = :st WHERE id = :id"),
        {"st": body.moderation_status, "id": str(video_id)},
    )
    session.commit()
    return {"ok": True, "status": body.moderation_status}
