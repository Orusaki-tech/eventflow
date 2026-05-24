"""v3: ticketing, monetization, feed, affiliates, payouts

Revision ID: a0b1c2d3e4f5
Revises: e4f5a6b7c8d9
Create Date: 2026-05-24

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # --- Ticket types ---
    op.create_table(
        "ticket_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_minor_units", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("quantity_available", sa.Integer(), nullable=True),
        sa.Column("quantity_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sale_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refundable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_event_id"], ["community_events.id"],
            name="fk_ticket_types_community_event", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_types"),
    )
    op.create_index("ix_ticket_types_community_event", "ticket_types", ["community_event_id"])

    # --- Orders ---
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("type", sa.String(length=8), nullable=False, server_default="ticket"),
        sa.Column("total_minor_units", sa.Integer(), nullable=False),
        sa.Column("platform_fee_minor_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_net_minor_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affiliate_net_minor_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("payment_provider", sa.String(length=8), nullable=True),
        sa.Column("payment_provider_transaction_id", sa.String(length=256), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_number", sa.String(length=32), nullable=True),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_redeemed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_event_id"], ["community_events.id"],
            name="fk_orders_community_event",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
    )

    # --- Order items ---
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor_units", sa.Integer(), nullable=False),
        sa.Column("subtotal_minor_units", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_order_items_order", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_type_id"], ["ticket_types.id"],
            name="fk_order_items_ticket_type", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_order_items"),
    )

    # --- Tickets (individual scannable tickets) ---
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_code", sa.String(length=8), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_tickets_order", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_type_id"], ["ticket_types.id"],
            name="fk_tickets_ticket_type", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["community_event_id"], ["community_events.id"],
            name="fk_tickets_community_event", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("short_code", name="uq_tickets_short_code"),
    )
    op.create_index("ix_tickets_community_event", "tickets", ["community_event_id"])
    op.create_index("ix_tickets_user_status", "tickets", ["user_id", "status"])

    # --- Products (for affiliate marketplace) ---
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_minor_units", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("image_uri", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"],
            name="fk_products_business", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
    )
    op.create_index("ix_products_business", "products", ["business_id"])

    # --- Product-event links (affiliate connections) ---
    op.create_table(
        "product_event_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_owner_business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commission_seller_percent", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("commission_owner_percent", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("commission_platform_percent", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_product_event_links"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_pel_product", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["community_event_id"], ["community_events.id"],
            name="fk_pel_community_event", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seller_business_id"], ["businesses.id"],
            name="fk_pel_seller_business", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_owner_business_id"], ["businesses.id"],
            name="fk_pel_owner_business", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_pel_community_event", "product_event_links", ["community_event_id"])

    # --- Business payout settings ---
    op.create_table(
        "business_payout_settings",
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_method", sa.String(length=16), nullable=False, server_default="mpesa_till"),
        sa.Column("mpesa_till_number", sa.String(length=16), nullable=True),
        sa.Column("mpesa_paybill_number", sa.String(length=16), nullable=True),
        sa.Column("mpesa_account_ref", sa.String(length=64), nullable=True),
        sa.Column("bank_name", sa.String(length=128), nullable=True),
        sa.Column("bank_account_name", sa.String(length=128), nullable=True),
        sa.Column("bank_account_number", sa.String(length=64), nullable=True),
        sa.Column("bank_branch_code", sa.String(length=16), nullable=True),
        sa.Column("stripe_connect_account_id", sa.String(length=128), nullable=True),
        sa.Column("payout_frequency", sa.String(length=8), nullable=False, server_default="manual"),
        sa.Column("minimum_payout_minor", sa.Integer(), nullable=False, server_default="50000"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("business_id", name="pk_business_payout_settings"),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"],
            name="fk_bps_business", ondelete="CASCADE",
        ),
    )

    # --- Business payouts ---
    op.create_table(
        "business_payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gross_minor_units", sa.Integer(), nullable=False),
        sa.Column("platform_fees_minor_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_payout_minor_units", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=24), nullable=False, server_default="ticket_sales"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="KES"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("payout_method_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payment_reference", sa.String(length=256), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_business_payouts"),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"],
            name="fk_bp_business", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_business_payouts_business", "business_payouts", ["business_id"])
    op.create_index("ix_business_payouts_status", "business_payouts", ["status"])

    # --- Affiliate earnings ---
    op.create_table(
        "affiliate_earnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("affiliate_business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("gross_minor_units", sa.Integer(), nullable=False),
        sa.Column("commission_percent", sa.Integer(), nullable=False),
        sa.Column("earned_minor_units", sa.Integer(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_affiliate_earnings"),
        sa.ForeignKeyConstraint(
            ["affiliate_business_id"], ["businesses.id"],
            name="fk_ae_affiliate_business", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_ae_order", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ae_affiliate_business", "affiliate_earnings", ["affiliate_business_id"])

    # --- Claims ---
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_type", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_claims"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_claims_order", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_claims_status", "claims", ["status"])

    # --- Feed videos (discovery feed) ---
    op.create_table(
        "feed_videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("video_uri", sa.String(length=1024), nullable=False),
        sa.Column("thumbnail_uri", sa.String(length=1024), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("video_type", sa.String(length=16), nullable=False, server_default="promo"),
        sa.Column("countdown_target", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderation_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("whatsapp_taps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_videos"),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"],
            name="fk_feed_videos_business", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_feed_videos_moderation", "feed_videos", ["moderation_status"])

    # --- Feed watch log (user video consumption) ---
    op.create_table(
        "feed_watch_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("watched_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("watched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feed_watch_log"),
        sa.ForeignKeyConstraint(
            ["feed_video_id"], ["feed_videos.id"],
            name="fk_fwl_video", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_fwl_user", "feed_watch_log", ["user_id"])

    # --- User points ---
    op.create_table(
        "user_points",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_redeemed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_points"),
    )

    # --- User subscriptions ---
    op.create_table(
        "user_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True, unique=True),
        sa.Column("plan", sa.String(length=16), nullable=False, server_default="premium"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_subscriptions"),
    )

    # --- Referral links (WhatsApp tap tracking) ---
    op.create_table(
        "referral_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("affiliate_business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("commission_percent", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("total_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_taps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_earned_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_referral_links"),
        sa.ForeignKeyConstraint(
            ["affiliate_business_id"], ["businesses.id"],
            name="fk_rl_affiliate_business", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["community_event_id"], ["community_events.id"],
            name="fk_rl_community_event", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("code", name="uq_referral_links_code"),
    )
    op.create_index("ix_rl_affiliate_business", "referral_links", ["affiliate_business_id"])

    # --- Platform settings (key-value config) ---
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_platform_settings"),
    )

    # --- Existing table modifications ---
    op.add_column("businesses", sa.Column("kra_receipt_counter", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("businesses", sa.Column("tap_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("businesses", sa.Column("tap_plan", sa.String(length=16), nullable=False, server_default="none"))

    op.add_column("community_events", sa.Column("has_ticketing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("community_events", sa.Column("has_products", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column("listing_analytics_events", sa.Column("referral_link_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("listing_analytics_events", sa.Column("tap_fee_minor_units", sa.Integer(), nullable=True))
    op.create_index("ix_analytics_referral_link", "listing_analytics_events", ["referral_link_id"])

    # --- Seed default platform settings ---
    op.execute(
        """
        INSERT INTO platform_settings (key, value, updated_at) VALUES
        ('platform_fee', '{"type": "percentage", "ticket_percent": 8, "product_percent": 10}', NOW()),
        ('tap_pricing', '{"starter": {"taps": 10, "price_minor": 20000}, "growth": {"taps": 50, "price_minor": 75000}, "pro": {"taps": 200, "price_minor": 250000}, "unlimited": {"taps": null, "price_minor": 500000, "period": "month"}}', NOW()),
        ('affiliate_commission', '{"tap_percent": 30, "ticket_percent": 5, "product_percent": 10}', NOW()),
        ('user_watch_quota', '{"videos_per_day": 10, "premium_price_minor": 30000, "currency": "KES", "period": "month"}', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM platform_settings WHERE key IN ('platform_fee', 'tap_pricing', 'affiliate_commission', 'user_watch_quota')")

    op.drop_index("ix_analytics_referral_link", table_name="listing_analytics_events")
    op.drop_column("listing_analytics_events", "tap_fee_minor_units")
    op.drop_column("listing_analytics_events", "referral_link_id")

    op.drop_column("community_events", "has_products")
    op.drop_column("community_events", "has_ticketing")

    op.drop_column("businesses", "tap_plan")
    op.drop_column("businesses", "tap_balance")
    op.drop_column("businesses", "kra_receipt_counter")

    op.drop_table("platform_settings")
    op.drop_table("referral_links")
    op.drop_table("user_subscriptions")
    op.drop_table("user_points")
    op.drop_table("feed_watch_log")
    op.drop_table("feed_videos")
    op.drop_table("claims")
    op.drop_table("affiliate_earnings")
    op.drop_table("business_payouts")
    op.drop_table("business_payout_settings")
    op.drop_table("product_event_links")
    op.drop_table("products")
    op.drop_table("tickets")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("ticket_types")
