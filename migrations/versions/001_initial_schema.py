"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supplier items table
    op.create_table(
        "supplier_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("supplier", sa.String(200), nullable=False),
        sa.Column("part_number", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("ean", sa.String(20), default=""),
        sa.Column("mpn", sa.String(100), default=""),
        sa.Column("asin_hint", sa.String(20), default=""),
        sa.Column("cost_ex_vat_1", sa.Numeric(10, 4), default=0),
        sa.Column("cost_ex_vat_5plus", sa.Numeric(10, 4), default=0),
        sa.Column("pack_qty", sa.Integer(), default=1),
        sa.Column("cost_per_unit_ex_vat_1", sa.Numeric(10, 4), default=0),
        sa.Column("cost_per_unit_ex_vat_5plus", sa.Numeric(10, 4), default=0),
        sa.Column("import_date", sa.DateTime(), nullable=True),
        sa.Column("import_batch_id", sa.String(50), default=""),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_items_brand", "supplier_items", ["brand"])
    op.create_index("ix_supplier_items_supplier", "supplier_items", ["supplier"])
    op.create_index("ix_supplier_items_part_number", "supplier_items", ["part_number"])
    op.create_index("ix_supplier_items_ean", "supplier_items", ["ean"])
    op.create_index("ix_supplier_items_import_batch_id", "supplier_items", ["import_batch_id"])
    op.create_index("ix_supplier_items_is_active", "supplier_items", ["is_active"])
    op.create_index("ix_supplier_items_brand_active", "supplier_items", ["brand", "is_active"])

    # ASIN candidates table
    op.create_table(
        "asin_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_item_id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(50), nullable=False),
        sa.Column("supplier", sa.String(200), nullable=False),
        sa.Column("part_number", sa.String(100), nullable=False),
        sa.Column("asin", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), default=""),
        sa.Column("amazon_brand", sa.String(200), default=""),
        sa.Column("match_reason", sa.Text(), default=""),
        sa.Column("confidence_score", sa.Numeric(5, 4), default=0.5),
        sa.Column("source", sa.String(50), default="spapi_keyword"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_primary", sa.Boolean(), default=False),
        sa.Column("is_locked", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["supplier_item_id"], ["supplier_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_asin_candidates_supplier_item_id", "asin_candidates", ["supplier_item_id"])
    op.create_index("ix_asin_candidates_brand", "asin_candidates", ["brand"])
    op.create_index("ix_asin_candidates_part_number", "asin_candidates", ["part_number"])
    op.create_index("ix_asin_candidates_asin", "asin_candidates", ["asin"])
    op.create_index("ix_asin_candidates_is_active", "asin_candidates", ["is_active"])
    op.create_index("ix_asin_candidates_is_primary", "asin_candidates", ["is_primary"])
    op.create_index("ix_asin_candidates_part_asin", "asin_candidates", ["part_number", "asin"])

    # Keepa snapshots table
    op.create_table(
        "keepa_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("asin", sa.String(20), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(), nullable=True),
        sa.Column("fbm_price_current", sa.Numeric(10, 2), nullable=True),
        sa.Column("fbm_price_median_30d", sa.Numeric(10, 2), nullable=True),
        sa.Column("fbm_price_mean_30d", sa.Numeric(10, 2), nullable=True),
        sa.Column("fbm_price_min_30d", sa.Numeric(10, 2), nullable=True),
        sa.Column("fbm_price_max_30d", sa.Numeric(10, 2), nullable=True),
        sa.Column("sales_rank_drops_30d", sa.Integer(), nullable=True),
        sa.Column("sales_rank_current", sa.Integer(), nullable=True),
        sa.Column("offer_count_fbm", sa.Integer(), nullable=True),
        sa.Column("offer_count_fba", sa.Integer(), nullable=True),
        sa.Column("offer_count_trend", sa.String(20), default=""),
        sa.Column("buy_box_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("buy_box_is_fba", sa.Boolean(), nullable=True),
        sa.Column("buy_box_is_amazon", sa.Boolean(), nullable=True),
        sa.Column("amazon_on_listing", sa.Boolean(), default=False),
        sa.Column("price_volatility_cv", sa.Numeric(6, 4), nullable=True),
        sa.Column("tokens_consumed", sa.Integer(), default=0),
        sa.Column("raw_json", sa.Text(), default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["asin_candidates.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_keepa_snapshots_candidate_id", "keepa_snapshots", ["candidate_id"])
    op.create_index("ix_keepa_snapshots_asin", "keepa_snapshots", ["asin"])
    op.create_index("ix_keepa_snapshots_snapshot_time", "keepa_snapshots", ["snapshot_time"])
    op.create_index("ix_keepa_snapshots_asin_time", "keepa_snapshots", ["asin", "snapshot_time"])

    # SP-API snapshots table
    op.create_table(
        "spapi_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("asin", sa.String(20), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(), nullable=True),
        sa.Column("sell_price_used", sa.Numeric(10, 2), default=0),
        sa.Column("is_restricted", sa.Boolean(), default=False),
        sa.Column("restriction_reasons", sa.Text(), default=""),
        sa.Column("fee_total_gross", sa.Numeric(10, 4), nullable=True),
        sa.Column("fee_referral", sa.Numeric(10, 4), nullable=True),
        sa.Column("fee_fba", sa.Numeric(10, 4), nullable=True),
        sa.Column("fee_variable_closing", sa.Numeric(10, 4), nullable=True),
        sa.Column("weight_kg", sa.Numeric(8, 4), nullable=True),
        sa.Column("weight_source", sa.String(50), default=""),
        sa.Column("product_title", sa.Text(), default=""),
        sa.Column("product_brand", sa.String(200), default=""),
        sa.Column("product_category", sa.String(200), default=""),
        sa.Column("raw_json", sa.Text(), default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["asin_candidates.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_spapi_snapshots_candidate_id", "spapi_snapshots", ["candidate_id"])
    op.create_index("ix_spapi_snapshots_asin", "spapi_snapshots", ["asin"])
    op.create_index("ix_spapi_snapshots_snapshot_time", "spapi_snapshots", ["snapshot_time"])
    op.create_index("ix_spapi_snapshots_asin_time", "spapi_snapshots", ["asin", "snapshot_time"])

    # Score history table
    op.create_table(
        "score_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("asin", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), default=0),
        sa.Column("winning_scenario", sa.String(20), default=""),
        sa.Column("profit_net", sa.Numeric(10, 4), default=0),
        sa.Column("margin_net", sa.Numeric(6, 4), default=0),
        sa.Column("sales_proxy_30d", sa.Integer(), nullable=True),
        sa.Column("breakdown_json", sa.Text(), default=""),
        sa.Column("flags_json", sa.Text(), default=""),
        sa.Column("keepa_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("spapi_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["asin_candidates.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_score_history_candidate_id", "score_history", ["candidate_id"])
    op.create_index("ix_score_history_asin", "score_history", ["asin"])
    op.create_index("ix_score_history_calculated_at", "score_history", ["calculated_at"])
    op.create_index("ix_score_history_candidate_time", "score_history", ["candidate_id", "calculated_at"])

    # Brand settings table
    op.create_table(
        "brand_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("brand", sa.String(50), nullable=False, unique=True),
        sa.Column("min_sales_proxy_30d", sa.Integer(), default=20),
        sa.Column("min_margin_ex_vat", sa.Numeric(6, 4), default=0.10),
        sa.Column("min_profit_ex_vat_gbp", sa.Numeric(10, 4), default=5.00),
        sa.Column("safe_price_buffer_pct", sa.Numeric(6, 4), default=0.03),
        sa.Column("vat_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("weights_json", sa.Text(), default="{}"),
        sa.Column("penalties_json", sa.Text(), default="{}"),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Global settings table
    op.create_table(
        "global_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value", sa.Text(), default=""),
        sa.Column("value_type", sa.String(20), default="string"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # API logs table
    op.create_table(
        "api_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("api_name", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(200), default=""),
        sa.Column("method", sa.String(10), default="GET"),
        sa.Column("request_params", sa.Text(), default=""),
        sa.Column("response_status", sa.Integer(), default=0),
        sa.Column("response_size_bytes", sa.Integer(), default=0),
        sa.Column("tokens_consumed", sa.Integer(), default=0),
        sa.Column("duration_ms", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), default=""),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_logs_api_name", "api_logs", ["api_name"])
    op.create_index("ix_api_logs_created_at", "api_logs", ["created_at"])
    op.create_index("ix_api_logs_api_time", "api_logs", ["api_name", "created_at"])


def downgrade() -> None:
    op.drop_table("api_logs")
    op.drop_table("global_settings")
    op.drop_table("brand_settings")
    op.drop_table("score_history")
    op.drop_table("spapi_snapshots")
    op.drop_table("keepa_snapshots")
    op.drop_table("asin_candidates")
    op.drop_table("supplier_items")
