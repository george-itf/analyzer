"""Repository pattern for database operations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, desc, func, select, update
from sqlalchemy.orm import Session

from src.core.models import (
    AsinCandidate,
    Brand,
    CandidateSource,
    KeepaSnapshot,
    ScoreHistory,
    ScoreResult,
    SpApiSnapshot,
    SupplierItem,
)

from .models import (
    ApiLogDB,
    AsinCandidateDB,
    GlobalSettingsDB,
    KeepaSnapshotDB,
    ScoreHistoryDB,
    SpApiSnapshotDB,
    SupplierItemDB,
)
from .session import session_scope


class Repository:
    """Data access repository for all database operations."""

    def __init__(self, session: Session | None = None) -> None:
        """Initialize with optional session (creates new if not provided)."""
        self._external_session = session

    def _get_session(self) -> Session:
        """Get the session to use."""
        if self._external_session:
            return self._external_session
        from .session import get_session
        return get_session()

    # ==================== Supplier Items ====================

    def save_supplier_item(self, item: SupplierItem) -> SupplierItem:
        """Save a supplier item to the database."""
        with session_scope() as session:
            db_item = SupplierItemDB(
                brand=item.brand.value,
                supplier=item.supplier,
                part_number=item.part_number,
                description=item.description,
                ean=item.ean,
                mpn=item.mpn,
                asin_hint=item.asin_hint,
                cost_ex_vat_1=item.cost_ex_vat_1,
                cost_ex_vat_5plus=item.cost_ex_vat_5plus,
                pack_qty=item.pack_qty,
                cost_per_unit_ex_vat_1=item.cost_per_unit_ex_vat_1,
                cost_per_unit_ex_vat_5plus=item.cost_per_unit_ex_vat_5plus,
                import_date=item.import_date,
                import_batch_id=item.import_batch_id,
                is_active=item.is_active,
            )
            session.add(db_item)
            session.flush()
            item.id = db_item.id
            return item

    def save_supplier_items_batch(self, items: list[SupplierItem]) -> list[SupplierItem]:
        """Save multiple supplier items efficiently."""
        with session_scope() as session:
            db_items = []
            for item in items:
                db_item = SupplierItemDB(
                    brand=item.brand.value,
                    supplier=item.supplier,
                    part_number=item.part_number,
                    description=item.description,
                    ean=item.ean,
                    mpn=item.mpn,
                    asin_hint=item.asin_hint,
                    cost_ex_vat_1=item.cost_ex_vat_1,
                    cost_ex_vat_5plus=item.cost_ex_vat_5plus,
                    pack_qty=item.pack_qty,
                    cost_per_unit_ex_vat_1=item.cost_per_unit_ex_vat_1,
                    cost_per_unit_ex_vat_5plus=item.cost_per_unit_ex_vat_5plus,
                    import_date=item.import_date,
                    import_batch_id=item.import_batch_id,
                    is_active=item.is_active,
                )
                db_items.append(db_item)
                session.add(db_item)

            session.flush()

            for item, db_item in zip(items, db_items):
                item.id = db_item.id

            return items

    def get_supplier_items_by_brand(self, brand: Brand, active_only: bool = True) -> list[SupplierItem]:
        """Get all supplier items for a brand."""
        with session_scope() as session:
            query = select(SupplierItemDB).where(SupplierItemDB.brand == brand.value)
            if active_only:
                query = query.where(SupplierItemDB.is_active == True)
            query = query.order_by(SupplierItemDB.part_number)

            result = session.execute(query).scalars().all()
            return [self._db_to_supplier_item(db) for db in result]

    def get_supplier_item_by_id(self, item_id: int) -> SupplierItem | None:
        """Get a supplier item by ID."""
        with session_scope() as session:
            db_item = session.get(SupplierItemDB, item_id)
            if db_item:
                return self._db_to_supplier_item(db_item)
            return None

    def get_supplier_item_by_key(
        self, brand: Brand, supplier: str, part_number: str
    ) -> SupplierItem | None:
        """Get a supplier item by unique key."""
        with session_scope() as session:
            query = select(SupplierItemDB).where(
                and_(
                    SupplierItemDB.brand == brand.value,
                    SupplierItemDB.supplier == supplier,
                    SupplierItemDB.part_number == part_number,
                    SupplierItemDB.is_active == True,
                )
            )
            db_item = session.execute(query).scalar_one_or_none()
            if db_item:
                return self._db_to_supplier_item(db_item)
            return None

    def deactivate_supplier_items_for_batch(self, brand: Brand, batch_id: str) -> int:
        """Deactivate all supplier items from a previous batch (not the current one)."""
        with session_scope() as session:
            stmt = (
                update(SupplierItemDB)
                .where(
                    and_(
                        SupplierItemDB.brand == brand.value,
                        SupplierItemDB.import_batch_id != batch_id,
                        SupplierItemDB.is_active == True,
                    )
                )
                .values(is_active=False, updated_at=datetime.now())
            )
            result = session.execute(stmt)
            return result.rowcount

    def _db_to_supplier_item(self, db: SupplierItemDB) -> SupplierItem:
        """Convert database model to domain model."""
        return SupplierItem(
            id=db.id,
            brand=Brand.from_string(db.brand),
            supplier=db.supplier,
            part_number=db.part_number,
            description=db.description,
            ean=db.ean,
            mpn=db.mpn,
            asin_hint=db.asin_hint,
            cost_ex_vat_1=db.cost_ex_vat_1,
            cost_ex_vat_5plus=db.cost_ex_vat_5plus,
            pack_qty=db.pack_qty,
            cost_per_unit_ex_vat_1=db.cost_per_unit_ex_vat_1,
            cost_per_unit_ex_vat_5plus=db.cost_per_unit_ex_vat_5plus,
            import_date=db.import_date,
            import_batch_id=db.import_batch_id,
            is_active=db.is_active,
            created_at=db.created_at,
            updated_at=db.updated_at,
        )

    # ==================== ASIN Candidates ====================

    def save_asin_candidate(self, candidate: AsinCandidate) -> AsinCandidate:
        """Save an ASIN candidate."""
        with session_scope() as session:
            db_candidate = AsinCandidateDB(
                supplier_item_id=candidate.supplier_item_id,
                brand=candidate.brand.value,
                supplier=candidate.supplier,
                part_number=candidate.part_number,
                asin=candidate.asin,
                title=candidate.title,
                amazon_brand=candidate.amazon_brand,
                match_reason=candidate.match_reason,
                confidence_score=candidate.confidence_score,
                source=candidate.source.value,
                is_active=candidate.is_active,
                is_primary=candidate.is_primary,
                is_locked=candidate.is_locked,
            )
            session.add(db_candidate)
            session.flush()
            candidate.id = db_candidate.id
            return candidate

    def save_asin_candidates_batch(self, candidates: list[AsinCandidate]) -> list[AsinCandidate]:
        """Save multiple ASIN candidates efficiently."""
        with session_scope() as session:
            db_candidates = []
            for candidate in candidates:
                db_candidate = AsinCandidateDB(
                    supplier_item_id=candidate.supplier_item_id,
                    brand=candidate.brand.value,
                    supplier=candidate.supplier,
                    part_number=candidate.part_number,
                    asin=candidate.asin,
                    title=candidate.title,
                    amazon_brand=candidate.amazon_brand,
                    match_reason=candidate.match_reason,
                    confidence_score=candidate.confidence_score,
                    source=candidate.source.value,
                    is_active=candidate.is_active,
                    is_primary=candidate.is_primary,
                    is_locked=candidate.is_locked,
                )
                db_candidates.append(db_candidate)
                session.add(db_candidate)

            session.flush()

            for candidate, db_candidate in zip(candidates, db_candidates):
                candidate.id = db_candidate.id

            return candidates

    def get_candidates_by_supplier_item(
        self, supplier_item_id: int, active_only: bool = True
    ) -> list[AsinCandidate]:
        """Get all ASIN candidates for a supplier item."""
        with session_scope() as session:
            query = select(AsinCandidateDB).where(
                AsinCandidateDB.supplier_item_id == supplier_item_id
            )
            if active_only:
                query = query.where(AsinCandidateDB.is_active == True)
            query = query.order_by(desc(AsinCandidateDB.confidence_score))

            result = session.execute(query).scalars().all()
            return [self._db_to_asin_candidate(db) for db in result]

    def get_candidates_by_brand(self, brand: Brand, active_only: bool = True) -> list[AsinCandidate]:
        """Get all ASIN candidates for a brand."""
        with session_scope() as session:
            query = select(AsinCandidateDB).where(AsinCandidateDB.brand == brand.value)
            if active_only:
                query = query.where(AsinCandidateDB.is_active == True)
            query = query.order_by(AsinCandidateDB.part_number, desc(AsinCandidateDB.confidence_score))

            result = session.execute(query).scalars().all()
            return [self._db_to_asin_candidate(db) for db in result]

    def get_candidates_by_batch(self, batch_id: str, active_only: bool = True) -> list[AsinCandidate]:
        """Get all ASIN candidates for items in a specific import batch."""
        with session_scope() as session:
            # First get supplier item IDs for the batch
            item_query = select(SupplierItemDB.id).where(
                SupplierItemDB.import_batch_id == batch_id
            )
            item_ids = session.execute(item_query).scalars().all()

            if not item_ids:
                return []

            # Get candidates for those items
            query = select(AsinCandidateDB).where(
                AsinCandidateDB.supplier_item_id.in_(item_ids)
            )
            if active_only:
                query = query.where(AsinCandidateDB.is_active == True)

            result = session.execute(query).scalars().all()
            return [self._db_to_asin_candidate(db) for db in result]

    def get_candidate_by_asin(
        self, supplier_item_id: int, asin: str
    ) -> AsinCandidate | None:
        """Get a specific ASIN candidate."""
        with session_scope() as session:
            query = select(AsinCandidateDB).where(
                and_(
                    AsinCandidateDB.supplier_item_id == supplier_item_id,
                    AsinCandidateDB.asin == asin,
                )
            )
            db_candidate = session.execute(query).scalar_one_or_none()
            if db_candidate:
                return self._db_to_asin_candidate(db_candidate)
            return None

    def get_primary_candidate(self, supplier_item_id: int) -> AsinCandidate | None:
        """Get the primary ASIN candidate for a supplier item."""
        with session_scope() as session:
            query = select(AsinCandidateDB).where(
                and_(
                    AsinCandidateDB.supplier_item_id == supplier_item_id,
                    AsinCandidateDB.is_primary == True,
                    AsinCandidateDB.is_active == True,
                )
            )
            db_candidate = session.execute(query).scalar_one_or_none()
            if db_candidate:
                return self._db_to_asin_candidate(db_candidate)
            return None

    def update_candidate_status(
        self,
        candidate_id: int,
        is_active: bool | None = None,
        is_primary: bool | None = None,
        is_locked: bool | None = None,
    ) -> None:
        """Update candidate status flags."""
        with session_scope() as session:
            values: dict[str, Any] = {"updated_at": datetime.now()}
            if is_active is not None:
                values["is_active"] = is_active
            if is_primary is not None:
                values["is_primary"] = is_primary
            if is_locked is not None:
                values["is_locked"] = is_locked

            stmt = (
                update(AsinCandidateDB)
                .where(AsinCandidateDB.id == candidate_id)
                .values(**values)
            )
            session.execute(stmt)

    def set_primary_candidate(self, supplier_item_id: int, candidate_id: int) -> None:
        """Set a candidate as primary and unset others."""
        with session_scope() as session:
            # Unset all primaries for this supplier item
            stmt = (
                update(AsinCandidateDB)
                .where(AsinCandidateDB.supplier_item_id == supplier_item_id)
                .values(is_primary=False, updated_at=datetime.now())
            )
            session.execute(stmt)

            # Set the new primary
            stmt = (
                update(AsinCandidateDB)
                .where(AsinCandidateDB.id == candidate_id)
                .values(is_primary=True, updated_at=datetime.now())
            )
            session.execute(stmt)

    def update_candidate_title(
        self,
        candidate_id: int,
        title: str,
        amazon_brand: str | None = None,
    ) -> None:
        """Update the title (and optionally brand) of a candidate from Keepa data."""
        with session_scope() as session:
            values: dict[str, Any] = {"updated_at": datetime.now()}
            if title:
                values["title"] = title
            if amazon_brand:
                values["amazon_brand"] = amazon_brand

            if len(values) > 1:  # More than just updated_at
                stmt = (
                    update(AsinCandidateDB)
                    .where(AsinCandidateDB.id == candidate_id)
                    .values(**values)
                )
                session.execute(stmt)

    def get_all_active_candidates(self) -> list[AsinCandidate]:
        """Get all active ASIN candidates across all brands."""
        with session_scope() as session:
            query = (
                select(AsinCandidateDB)
                .where(AsinCandidateDB.is_active == True)
                .order_by(AsinCandidateDB.brand, AsinCandidateDB.part_number)
            )
            result = session.execute(query).scalars().all()
            return [self._db_to_asin_candidate(db) for db in result]

    def _db_to_asin_candidate(self, db: AsinCandidateDB) -> AsinCandidate:
        """Convert database model to domain model."""
        return AsinCandidate(
            id=db.id,
            supplier_item_id=db.supplier_item_id,
            brand=Brand.from_string(db.brand),
            supplier=db.supplier,
            part_number=db.part_number,
            asin=db.asin,
            title=db.title,
            amazon_brand=db.amazon_brand,
            match_reason=db.match_reason,
            confidence_score=db.confidence_score,
            source=CandidateSource(db.source),
            is_active=db.is_active,
            is_primary=db.is_primary,
            is_locked=db.is_locked,
            created_at=db.created_at,
            updated_at=db.updated_at,
        )

    # ==================== Keepa Snapshots ====================

    def save_keepa_snapshot(self, candidate_id: int, snapshot: KeepaSnapshot) -> KeepaSnapshot:
        """Save a Keepa snapshot."""
        with session_scope() as session:
            db_snapshot = KeepaSnapshotDB(
                candidate_id=candidate_id,
                asin=snapshot.asin,
                snapshot_time=snapshot.snapshot_time,
                fbm_price_current=snapshot.fbm_price_current,
                fbm_price_median_30d=snapshot.fbm_price_median_30d,
                fbm_price_mean_30d=snapshot.fbm_price_mean_30d,
                fbm_price_min_30d=snapshot.fbm_price_min_30d,
                fbm_price_max_30d=snapshot.fbm_price_max_30d,
                sales_rank_drops_30d=snapshot.sales_rank_drops_30d,
                sales_rank_current=snapshot.sales_rank_current,
                offer_count_fbm=snapshot.offer_count_fbm,
                offer_count_fba=snapshot.offer_count_fba,
                offer_count_trend=snapshot.offer_count_trend,
                buy_box_price=snapshot.buy_box_price,
                buy_box_is_fba=snapshot.buy_box_is_fba,
                buy_box_is_amazon=snapshot.buy_box_is_amazon,
                amazon_on_listing=snapshot.amazon_on_listing,
                price_volatility_cv=snapshot.price_volatility_cv,
                tokens_consumed=snapshot.tokens_consumed,
                raw_json=snapshot.raw_json,
            )
            session.add(db_snapshot)
            session.flush()
            snapshot.id = db_snapshot.id
            return snapshot

    def get_latest_keepa_snapshot(self, candidate_id: int) -> KeepaSnapshot | None:
        """Get the most recent Keepa snapshot for a candidate."""
        with session_scope() as session:
            query = (
                select(KeepaSnapshotDB)
                .where(KeepaSnapshotDB.candidate_id == candidate_id)
                .order_by(desc(KeepaSnapshotDB.snapshot_time))
                .limit(1)
            )
            db_snapshot = session.execute(query).scalar_one_or_none()
            if db_snapshot:
                return self._db_to_keepa_snapshot(db_snapshot)
            return None

    def get_keepa_snapshots(
        self, candidate_id: int, since: datetime | None = None, limit: int = 100
    ) -> list[KeepaSnapshot]:
        """Get Keepa snapshots for a candidate."""
        with session_scope() as session:
            query = select(KeepaSnapshotDB).where(KeepaSnapshotDB.candidate_id == candidate_id)
            if since:
                query = query.where(KeepaSnapshotDB.snapshot_time >= since)
            query = query.order_by(desc(KeepaSnapshotDB.snapshot_time)).limit(limit)

            result = session.execute(query).scalars().all()
            return [self._db_to_keepa_snapshot(db) for db in result]

    def _db_to_keepa_snapshot(self, db: KeepaSnapshotDB) -> KeepaSnapshot:
        """Convert database model to domain model."""
        return KeepaSnapshot(
            id=db.id,
            asin=db.asin,
            snapshot_time=db.snapshot_time,
            fbm_price_current=db.fbm_price_current,
            fbm_price_median_30d=db.fbm_price_median_30d,
            fbm_price_mean_30d=db.fbm_price_mean_30d,
            fbm_price_min_30d=db.fbm_price_min_30d,
            fbm_price_max_30d=db.fbm_price_max_30d,
            sales_rank_drops_30d=db.sales_rank_drops_30d,
            sales_rank_current=db.sales_rank_current,
            offer_count_fbm=db.offer_count_fbm,
            offer_count_fba=db.offer_count_fba,
            offer_count_trend=db.offer_count_trend,
            buy_box_price=db.buy_box_price,
            buy_box_is_fba=db.buy_box_is_fba,
            buy_box_is_amazon=db.buy_box_is_amazon,
            amazon_on_listing=db.amazon_on_listing,
            price_volatility_cv=db.price_volatility_cv,
            tokens_consumed=db.tokens_consumed,
            raw_json=db.raw_json,
            created_at=db.created_at,
        )

    # ==================== SP-API Snapshots ====================

    def save_spapi_snapshot(self, candidate_id: int, snapshot: SpApiSnapshot) -> SpApiSnapshot:
        """Save an SP-API snapshot."""
        with session_scope() as session:
            db_snapshot = SpApiSnapshotDB(
                candidate_id=candidate_id,
                asin=snapshot.asin,
                snapshot_time=snapshot.snapshot_time,
                sell_price_used=snapshot.sell_price_used,
                is_restricted=snapshot.is_restricted,
                restriction_reasons=snapshot.restriction_reasons,
                fee_total_gross=snapshot.fee_total_gross,
                fee_referral=snapshot.fee_referral,
                fee_fba=snapshot.fee_fba,
                fee_variable_closing=snapshot.fee_variable_closing,
                weight_kg=snapshot.weight_kg,
                weight_source=snapshot.weight_source,
                product_title=snapshot.product_title,
                product_brand=snapshot.product_brand,
                product_category=snapshot.product_category,
                raw_json=snapshot.raw_json,
            )
            session.add(db_snapshot)
            session.flush()
            snapshot.id = db_snapshot.id
            return snapshot

    def get_latest_spapi_snapshot(
        self, candidate_id: int, sell_price: Decimal | None = None, ttl_minutes: int = 60
    ) -> SpApiSnapshot | None:
        """Get a cached SP-API snapshot if still valid."""
        with session_scope() as session:
            query = select(SpApiSnapshotDB).where(SpApiSnapshotDB.candidate_id == candidate_id)

            if sell_price is not None:
                # Match exact sell price for fee cache
                query = query.where(SpApiSnapshotDB.sell_price_used == sell_price)

            # Check TTL
            cutoff = datetime.now() - timedelta(minutes=ttl_minutes)
            query = query.where(SpApiSnapshotDB.snapshot_time >= cutoff)
            query = query.order_by(desc(SpApiSnapshotDB.snapshot_time)).limit(1)

            db_snapshot = session.execute(query).scalar_one_or_none()
            if db_snapshot:
                return self._db_to_spapi_snapshot(db_snapshot)
            return None

    def _db_to_spapi_snapshot(self, db: SpApiSnapshotDB) -> SpApiSnapshot:
        """Convert database model to domain model."""
        return SpApiSnapshot(
            id=db.id,
            asin=db.asin,
            snapshot_time=db.snapshot_time,
            sell_price_used=db.sell_price_used,
            is_restricted=db.is_restricted,
            restriction_reasons=db.restriction_reasons,
            fee_total_gross=db.fee_total_gross,
            fee_referral=db.fee_referral,
            fee_fba=db.fee_fba,
            fee_variable_closing=db.fee_variable_closing,
            weight_kg=db.weight_kg,
            weight_source=db.weight_source,
            product_title=db.product_title,
            product_brand=db.product_brand,
            product_category=db.product_category,
            raw_json=db.raw_json,
            created_at=db.created_at,
        )

    # ==================== Score History ====================

    def save_score_history(self, candidate_id: int, result: ScoreResult) -> ScoreHistory:
        """Save a score result to history."""
        with session_scope() as session:
            # Serialize breakdown and flags
            breakdown_json = json.dumps({
                "velocity_raw": str(result.breakdown.velocity_raw),
                "velocity_weighted": str(result.breakdown.velocity_weighted),
                "profit_raw": str(result.breakdown.profit_raw),
                "profit_weighted": str(result.breakdown.profit_weighted),
                "margin_raw": str(result.breakdown.margin_raw),
                "margin_weighted": str(result.breakdown.margin_weighted),
                "stability_raw": str(result.breakdown.stability_raw),
                "stability_weighted": str(result.breakdown.stability_weighted),
                "viability_raw": str(result.breakdown.viability_raw),
                "viability_weighted": str(result.breakdown.viability_weighted),
                "weighted_sum": str(result.breakdown.weighted_sum),
                "total_penalties": str(result.breakdown.total_penalties),
                "score_raw": str(result.breakdown.score_raw),
            })

            flags_json = json.dumps([
                {
                    "code": f.code,
                    "description": f.description,
                    "penalty": str(f.penalty),
                    "is_critical": f.is_critical,
                }
                for f in result.flags
            ])

            db_history = ScoreHistoryDB(
                candidate_id=candidate_id,
                asin=result.asin,
                score=result.score,
                winning_scenario=result.winning_scenario,
                profit_net=result.get_best_profit(),
                margin_net=result.get_best_margin(),
                sales_proxy_30d=result.sales_proxy_30d,
                breakdown_json=breakdown_json,
                flags_json=flags_json,
                keepa_snapshot_id=result.keepa_snapshot_id,
                spapi_snapshot_id=result.spapi_snapshot_id,
                calculated_at=result.calculated_at,
            )
            session.add(db_history)
            session.flush()

            return ScoreHistory(
                id=db_history.id,
                asin_candidate_id=candidate_id,
                asin=result.asin,
                score=result.score,
                profit_net=result.get_best_profit(),
                margin_net=result.get_best_margin(),
                sales_proxy_30d=result.sales_proxy_30d,
                flags_json=flags_json,
                calculated_at=result.calculated_at,
            )

    def get_score_history(
        self, candidate_id: int, limit: int = 100
    ) -> list[ScoreHistory]:
        """Get score history for a candidate."""
        with session_scope() as session:
            query = (
                select(ScoreHistoryDB)
                .where(ScoreHistoryDB.candidate_id == candidate_id)
                .order_by(desc(ScoreHistoryDB.calculated_at))
                .limit(limit)
            )
            result = session.execute(query).scalars().all()
            return [
                ScoreHistory(
                    id=db.id,
                    asin_candidate_id=db.candidate_id,
                    asin=db.asin,
                    score=db.score,
                    profit_net=db.profit_net,
                    margin_net=db.margin_net,
                    sales_proxy_30d=db.sales_proxy_30d,
                    flags_json=db.flags_json,
                    calculated_at=db.calculated_at,
                )
                for db in result
            ]

    def get_latest_score(self, candidate_id: int) -> ScoreHistory | None:
        """Get the most recent score for a candidate."""
        history = self.get_score_history(candidate_id, limit=1)
        return history[0] if history else None

    # ==================== API Logs ====================

    def save_api_log(
        self,
        api_name: str,
        endpoint: str,
        method: str,
        request_params: str,
        response_status: int,
        response_size: int,
        tokens_consumed: int,
        duration_ms: int,
        success: bool,
        error_message: str = "",
    ) -> None:
        """Save an API call log entry."""
        with session_scope() as session:
            db_log = ApiLogDB(
                api_name=api_name,
                endpoint=endpoint,
                method=method,
                request_params=request_params,
                response_status=response_status,
                response_size_bytes=response_size,
                tokens_consumed=tokens_consumed,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )
            session.add(db_log)

    def get_api_logs(
        self,
        api_name: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get API logs with optional filtering."""
        with session_scope() as session:
            query = select(ApiLogDB)
            if api_name:
                query = query.where(ApiLogDB.api_name == api_name)
            if since:
                query = query.where(ApiLogDB.created_at >= since)
            query = query.order_by(desc(ApiLogDB.created_at)).limit(limit)

            result = session.execute(query).scalars().all()
            return [
                {
                    "id": db.id,
                    "api_name": db.api_name,
                    "endpoint": db.endpoint,
                    "method": db.method,
                    "response_status": db.response_status,
                    "tokens_consumed": db.tokens_consumed,
                    "duration_ms": db.duration_ms,
                    "success": db.success,
                    "error_message": db.error_message,
                    "created_at": db.created_at.isoformat(),
                }
                for db in result
            ]

    def get_token_usage_stats(self, hours: int = 24) -> dict:
        """Get token usage statistics for the past N hours."""
        with session_scope() as session:
            since = datetime.now() - timedelta(hours=hours)
            query = (
                select(
                    func.sum(ApiLogDB.tokens_consumed).label("total_tokens"),
                    func.count(ApiLogDB.id).label("total_calls"),
                    func.sum(case((ApiLogDB.success == True, 1), else_=0)).label("success_count"),
                )
                .where(
                    and_(
                        ApiLogDB.api_name == "keepa",
                        ApiLogDB.created_at >= since,
                    )
                )
            )
            result = session.execute(query).one()
            return {
                "total_tokens": result.total_tokens or 0,
                "total_calls": result.total_calls or 0,
                "success_count": result.success_count or 0,
                "failure_count": (result.total_calls or 0) - (result.success_count or 0),
            }

    # ==================== Settings ====================

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Get a global setting by key."""
        with session_scope() as session:
            db_setting = session.execute(
                select(GlobalSettingsDB).where(GlobalSettingsDB.key == key)
            ).scalar_one_or_none()

            if db_setting is None:
                return default

            value_type = db_setting.value_type
            value = db_setting.value

            if value_type == "int":
                return int(value)
            elif value_type == "decimal":
                return Decimal(value)
            elif value_type == "bool":
                return value.lower() in ("true", "1", "yes")
            elif value_type == "json":
                return json.loads(value)
            return value

    def set_global_setting(self, key: str, value: Any, value_type: str = "string") -> None:
        """Set a global setting."""
        with session_scope() as session:
            str_value = str(value) if value_type != "json" else json.dumps(value)

            db_setting = session.execute(
                select(GlobalSettingsDB).where(GlobalSettingsDB.key == key)
            ).scalar_one_or_none()

            if db_setting:
                db_setting.value = str_value
                db_setting.value_type = value_type
                db_setting.updated_at = datetime.now()
            else:
                db_setting = GlobalSettingsDB(key=key, value=str_value, value_type=value_type)
                session.add(db_setting)

    # ==================== Statistics ====================

    def get_item_counts_by_brand(self) -> dict[str, int]:
        """Get count of active supplier items by brand."""
        with session_scope() as session:
            query = (
                select(
                    SupplierItemDB.brand,
                    func.count(SupplierItemDB.id).label("count"),
                )
                .where(SupplierItemDB.is_active == True)
                .group_by(SupplierItemDB.brand)
            )
            result = session.execute(query).all()
            return {row.brand: row.count for row in result}

    def get_candidate_counts_by_brand(self) -> dict[str, int]:
        """Get count of active candidates by brand."""
        with session_scope() as session:
            query = (
                select(
                    AsinCandidateDB.brand,
                    func.count(AsinCandidateDB.id).label("count"),
                )
                .where(AsinCandidateDB.is_active == True)
                .group_by(AsinCandidateDB.brand)
            )
            result = session.execute(query).all()
            return {row.brand: row.count for row in result}
