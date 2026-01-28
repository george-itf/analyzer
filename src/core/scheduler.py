"""Background refresh scheduler for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from PyQt6.QtCore import QMutex, QObject, QThread, QTimer, pyqtSignal

from src.api.keepa import KeepaClient, KeepaRateLimitError
from src.api.spapi import SpApiClient, SpApiRateLimitError
from src.core.alerts import AlertManager
from src.core.config import Settings, get_settings
from src.core.models import (
    AsinCandidate,
    Brand,
    KeepaSnapshot,
    ScoreResult,
    SpApiSnapshot,
    SupplierItem,
    TokenStatus,
)
from src.core.scoring import ScoringEngine
from src.db.repository import Repository

logger = logging.getLogger(__name__)


class RefreshWorker(QObject):
    """Worker object that runs in a background thread to refresh data."""

    # Signals
    token_status_updated = pyqtSignal(int, int, int)  # tokensLeft, refillRate, refillIn
    score_updated = pyqtSignal(str, str, int)  # brand, asin, score
    batch_completed = pyqtSignal(str, int, int)  # pass_name, success_count, fail_count
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)
    alert_triggered = pyqtSignal(object)  # Alert object

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.repo = Repository()
        self.keepa = KeepaClient(settings)
        self.spapi = SpApiClient(settings)
        self.scoring = ScoringEngine(settings)
        self.alert_manager = AlertManager(settings.alerts)

        # Forward alert signals
        self.alert_manager.alert_triggered.connect(self.alert_triggered)

        self._running = False
        self._paused = False
        self._mutex = QMutex()
        self._priority_queue: deque[str] = deque()  # ASINs to refresh immediately
        self._retry_queue: deque[tuple[str, int, datetime]] = deque()  # (ASIN, retry_count, next_retry_time)
        self._max_retries = 3
        self._retry_delays = [30, 120, 300]  # Seconds to wait before retry attempts

    def start_refresh(self) -> None:
        """Start the refresh loop."""
        self._running = True
        self._paused = False
        self._run_loop()

    def stop_refresh(self) -> None:
        """Stop the refresh loop."""
        self._running = False

    def pause_refresh(self) -> None:
        """Pause the refresh loop."""
        self._paused = True

    def resume_refresh(self) -> None:
        """Resume the refresh loop."""
        self._paused = False

    def queue_priority_refresh(self, asins: list[str]) -> None:
        """Add ASINs to the priority queue for immediate refresh."""
        self._mutex.lock()
        try:
            for asin in asins:
                if asin not in self._priority_queue:
                    self._priority_queue.append(asin)
            self.log_message.emit(f"Queued {len(asins)} ASINs for priority refresh")
        finally:
            self._mutex.unlock()

    def _save_score_and_check_alerts(
        self,
        candidate: AsinCandidate,
        result: ScoreResult,
        is_new: bool = False,
    ) -> None:
        """Save score history and check for alerts."""
        if not candidate.id:
            return

        # Get previous score for comparison
        previous = self.repo.get_latest_score(candidate.id)

        # Save new score
        self.repo.save_score_history(candidate.id, result)

        # Emit score update signal
        self.score_updated.emit(
            candidate.brand.value,
            candidate.asin,
            result.score,
        )

        # Check for alerts
        self.alert_manager.check_for_alerts(result, previous, is_new=is_new)

    def _add_to_retry_queue(self, asin: str, current_retry: int = 0) -> None:
        """Add an ASIN to the retry queue with exponential backoff."""
        if current_retry >= self._max_retries:
            self.log_message.emit(f"Max retries reached for {asin}, giving up")
            return

        delay = self._retry_delays[min(current_retry, len(self._retry_delays) - 1)]
        next_retry = datetime.now() + timedelta(seconds=delay)

        self._mutex.lock()
        try:
            # Check if already in retry queue
            for item in self._retry_queue:
                if item[0] == asin:
                    return  # Already queued
            self._retry_queue.append((asin, current_retry + 1, next_retry))
            self.log_message.emit(f"Queued {asin} for retry #{current_retry + 1} in {delay}s")
        finally:
            self._mutex.unlock()

    def _process_retry_queue(self) -> bool:
        """Process items ready for retry. Returns True if items were processed."""
        now = datetime.now()
        ready_items: list[tuple[str, int]] = []

        self._mutex.lock()
        try:
            # Find items ready for retry
            remaining: deque[tuple[str, int, datetime]] = deque()
            while self._retry_queue:
                asin, retry_count, next_time = self._retry_queue.popleft()
                if next_time <= now:
                    ready_items.append((asin, retry_count))
                else:
                    remaining.append((asin, retry_count, next_time))
            self._retry_queue = remaining
        finally:
            self._mutex.unlock()

        if not ready_items:
            return False

        self.log_message.emit(f"Retrying {len(ready_items)} failed ASINs...")

        # Get candidates for these ASINs
        candidates = self.repo.get_all_active_candidates()
        asin_to_candidates: dict[str, list[AsinCandidate]] = {}
        asin_to_retry_count: dict[str, int] = {}
        for asin, retry_count in ready_items:
            asin_to_retry_count[asin] = retry_count

        for c in candidates:
            if c.asin in asin_to_retry_count:
                asin_to_candidates.setdefault(c.asin, []).append(c)

        if not asin_to_candidates:
            return True

        try:
            wait_time = self.keepa.wait_for_tokens(len(asin_to_candidates))
            if wait_time > 0:
                # Put items back in queue
                for asin, retry_count in ready_items:
                    self._retry_queue.append((asin, retry_count, now + timedelta(seconds=wait_time)))
                return False

            snapshots, response = self.keepa.fetch_and_parse(
                list(asin_to_candidates.keys()), days=90, include_buy_box=False
            )

            ts = response.token_status
            self.token_status_updated.emit(ts.tokens_left, ts.refill_rate, ts.refill_in_seconds)

            # Track which ASINs succeeded
            succeeded_asins = {s.asin for s in snapshots}

            for snapshot in snapshots:
                asin = snapshot.asin
                candidates_for_asin = asin_to_candidates.get(asin, [])

                for candidate in candidates_for_asin:
                    if candidate.id:
                        self.repo.save_keepa_snapshot(candidate.id, snapshot)
                        spapi_snapshot = self._get_spapi_data(candidate, snapshot)

                        item = self.repo.get_supplier_item_by_id(candidate.supplier_item_id)
                        if item:
                            result = self.scoring.calculate(item, candidate, snapshot, spapi_snapshot)
                            self._save_score_and_check_alerts(candidate, result)

            # Re-queue failed ASINs
            for asin in asin_to_candidates:
                if asin not in succeeded_asins:
                    self._add_to_retry_queue(asin, asin_to_retry_count[asin])

            self.log_message.emit(f"Retry completed: {len(succeeded_asins)} succeeded, {len(asin_to_candidates) - len(succeeded_asins)} failed again")

        except Exception as e:
            logger.exception("Retry processing error")
            # Re-queue all items
            for asin, retry_count in ready_items:
                self._add_to_retry_queue(asin, retry_count)
            self.error_occurred.emit(f"Retry error: {e}")

        return True

    def _process_priority_queue(self) -> bool:
        """Process priority queue items. Returns True if items were processed."""
        self._mutex.lock()
        try:
            if not self._priority_queue:
                return False
            # Get up to 20 ASINs from priority queue
            batch = []
            while self._priority_queue and len(batch) < 20:
                batch.append(self._priority_queue.popleft())
        finally:
            self._mutex.unlock()

        if not batch:
            return False

        self.log_message.emit(f"Priority refresh: Processing {len(batch)} ASINs...")

        # Get candidates for these ASINs
        candidates = self.repo.get_all_active_candidates()
        asin_to_candidates: dict[str, list[AsinCandidate]] = {}
        for c in candidates:
            if c.asin in batch:
                asin_to_candidates.setdefault(c.asin, []).append(c)

        if not asin_to_candidates:
            return True

        try:
            # Check token availability
            wait_time = self.keepa.wait_for_tokens(len(batch))
            if wait_time > 0:
                self.log_message.emit(f"Priority refresh: Waiting {wait_time:.0f}s for tokens...")
                time.sleep(min(wait_time, 30))

            snapshots, response = self.keepa.fetch_and_parse(
                list(asin_to_candidates.keys()), days=90, include_buy_box=False
            )

            ts = response.token_status
            self.token_status_updated.emit(ts.tokens_left, ts.refill_rate, ts.refill_in_seconds)

            # Build a map of ASIN -> product for title extraction
            asin_to_product: dict[str, dict] = {}
            for product in response.products:
                asin_to_product[product.get("asin", "")] = product

            success_count = 0
            for snapshot in snapshots:
                asin = snapshot.asin
                candidates_for_asin = asin_to_candidates.get(asin, [])

                product = asin_to_product.get(asin, {})
                keepa_title = KeepaClient.get_product_title(product)
                keepa_brand = KeepaClient.get_product_brand(product)

                for candidate in candidates_for_asin:
                    if candidate.id:
                        if keepa_title and not candidate.title:
                            self.repo.update_candidate_title(
                                candidate.id,
                                title=keepa_title,
                                amazon_brand=keepa_brand if keepa_brand else None,
                            )

                        self.repo.save_keepa_snapshot(candidate.id, snapshot)
                        spapi_snapshot = self._get_spapi_data(candidate, snapshot)

                        item = self.repo.get_supplier_item_by_id(candidate.supplier_item_id)
                        if item:
                            result = self.scoring.calculate(item, candidate, snapshot, spapi_snapshot)
                            self._save_score_and_check_alerts(candidate, result, is_new=True)
                            success_count += 1

            self.batch_completed.emit("priority", success_count, 0)
            self.log_message.emit(f"Priority refresh: Completed {success_count} items")

        except Exception as e:
            logger.exception("Priority refresh error")
            self.error_occurred.emit(f"Priority refresh error: {e}")

        return True

    def _run_loop(self) -> None:
        """Main refresh loop."""
        pass1_counter = 0
        pass2_counter = 0
        pass1_interval = self.settings.refresh.pass1_interval_seconds
        pass2_interval = self.settings.refresh.pass2_interval_seconds

        while self._running:
            if self._paused:
                time.sleep(1)
                continue

            try:
                # Priority queue takes precedence - process immediately
                if self._process_priority_queue():
                    continue  # Check again for more priority items

                # Process retry queue
                if self._process_retry_queue():
                    continue  # Check for more retry items

                # Pass 1: Continuous wide scan
                if pass1_counter <= 0:
                    self._run_pass1()
                    pass1_counter = pass1_interval

                # Pass 2: Narrow scan of top candidates
                if pass2_counter <= 0:
                    self._run_pass2()
                    pass2_counter = pass2_interval

                # Sleep 1 second and decrement counters
                time.sleep(1)
                pass1_counter -= 1
                pass2_counter -= 1

            except Exception as e:
                logger.exception("Refresh loop error")
                self.error_occurred.emit(str(e))
                time.sleep(5)  # Back off on error

    def _run_pass1(self) -> None:
        """Run Pass 1: wide scan of all active candidates."""
        self.log_message.emit("Pass 1: Starting wide scan...")

        # Get all active candidates
        candidates = self.repo.get_all_active_candidates()
        if not candidates:
            self.log_message.emit("Pass 1: No active candidates to scan")
            return

        # Collect unique ASINs
        asin_to_candidates: dict[str, list[AsinCandidate]] = {}
        for c in candidates:
            asin_to_candidates.setdefault(c.asin, []).append(c)

        asins = list(asin_to_candidates.keys())
        success_count = 0
        fail_count = 0

        # Process in batches based on available tokens
        batch_size = min(20, len(asins))  # Keepa allows up to 100 but use smaller batches
        i = 0

        while i < len(asins) and self._running and not self._paused:
            # Check token availability
            wait_time = self.keepa.wait_for_tokens(batch_size)
            if wait_time > 0:
                self.log_message.emit(f"Pass 1: Waiting {wait_time:.0f}s for tokens...")
                self.token_status_updated.emit(
                    self.keepa.token_status.tokens_left,
                    self.keepa.token_status.refill_rate,
                    int(wait_time),
                )
                time.sleep(min(wait_time, 30))  # Wait but cap at 30s to check status
                continue

            batch_asins = asins[i : i + batch_size]
            try:
                snapshots, response = self.keepa.fetch_and_parse(
                    batch_asins, days=90, include_buy_box=False
                )

                # Update token status
                ts = response.token_status
                self.token_status_updated.emit(ts.tokens_left, ts.refill_rate, ts.refill_in_seconds)

                # Build a map of ASIN -> product for title extraction
                asin_to_product: dict[str, dict] = {}
                for product in response.products:
                    asin_to_product[product.get("asin", "")] = product

                # Save snapshots and compute scores
                for snapshot in snapshots:
                    asin = snapshot.asin
                    candidates_for_asin = asin_to_candidates.get(asin, [])

                    # Extract title from Keepa product data
                    product = asin_to_product.get(asin, {})
                    keepa_title = KeepaClient.get_product_title(product)
                    keepa_brand = KeepaClient.get_product_brand(product)

                    for candidate in candidates_for_asin:
                        if candidate.id:
                            # Update candidate title if we have one from Keepa and candidate doesn't have one
                            if keepa_title and not candidate.title:
                                self.repo.update_candidate_title(
                                    candidate.id,
                                    title=keepa_title,
                                    amazon_brand=keepa_brand if keepa_brand else None,
                                )

                            # Save Keepa snapshot
                            self.repo.save_keepa_snapshot(candidate.id, snapshot)

                            # Get SP-API data (from cache or fresh)
                            spapi_snapshot = self._get_spapi_data(candidate, snapshot)

                            # Get supplier item
                            item = self.repo.get_supplier_item_by_id(candidate.supplier_item_id)
                            if item:
                                # Compute score
                                result = self.scoring.calculate(item, candidate, snapshot, spapi_snapshot)

                                # Save score and check alerts
                                self._save_score_and_check_alerts(candidate, result)
                                success_count += 1

                # Log API call
                self.repo.save_api_log(
                    api_name="keepa",
                    endpoint="product",
                    method="GET",
                    request_params=f"asins={','.join(batch_asins)}",
                    response_status=200 if response.success else 0,
                    response_size=len(response.raw_json),
                    tokens_consumed=ts.tokens_consumed_last,
                    duration_ms=0,
                    success=response.success,
                    error_message=response.error_message,
                )

            except KeepaRateLimitError:
                self.log_message.emit("Pass 1: Rate limited, backing off...")
                time.sleep(self.keepa.token_status.refill_in_seconds)
                continue
            except Exception as e:
                logger.exception(f"Pass 1 error for batch starting at {i}")
                fail_count += len(batch_asins)
                self.error_occurred.emit(f"Pass 1 error: {e}")
                # Add failed ASINs to retry queue
                for asin in batch_asins:
                    self._add_to_retry_queue(asin)

            i += batch_size

        self.batch_completed.emit("pass1", success_count, fail_count)
        self.log_message.emit(f"Pass 1: Completed. Success: {success_count}, Failed: {fail_count}")

    def _run_pass2(self) -> None:
        """Run Pass 2: narrow scan of top candidates with buy box data."""
        self.log_message.emit("Pass 2: Starting shortlist scan...")

        shortlist_size = self.settings.refresh.pass2_shortlist_size

        # Get top candidates by recent score
        # We need to query score_history for top-scoring candidates
        candidates = self.repo.get_all_active_candidates()
        if not candidates:
            return

        # Get latest scores and sort
        scored: list[tuple[AsinCandidate, int]] = []
        for c in candidates:
            if c.id:
                latest = self.repo.get_latest_score(c.id)
                if latest:
                    scored.append((c, latest.score))
                else:
                    scored.append((c, 0))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored[:shortlist_size]

        # Collect ASINs
        asins = list({c.asin for c, _ in top_candidates})
        if not asins:
            return

        success_count = 0
        fail_count = 0

        # Fetch with buy box data
        batch_size = min(10, len(asins))
        i = 0

        while i < len(asins) and self._running and not self._paused:
            wait_time = self.keepa.wait_for_tokens(batch_size * 2)  # Buy box costs more
            if wait_time > 0:
                self.log_message.emit(f"Pass 2: Waiting {wait_time:.0f}s for tokens...")
                time.sleep(min(wait_time, 30))
                continue

            batch_asins = asins[i : i + batch_size]
            try:
                snapshots, response = self.keepa.fetch_and_parse(
                    batch_asins, days=90, include_buy_box=True
                )

                ts = response.token_status
                self.token_status_updated.emit(ts.tokens_left, ts.refill_rate, ts.refill_in_seconds)

                for snapshot in snapshots:
                    success_count += 1

                self.repo.save_api_log(
                    api_name="keepa",
                    endpoint="product (pass2+buybox)",
                    method="GET",
                    request_params=f"asins={','.join(batch_asins)}",
                    response_status=200 if response.success else 0,
                    response_size=len(response.raw_json),
                    tokens_consumed=ts.tokens_consumed_last,
                    duration_ms=0,
                    success=response.success,
                    error_message=response.error_message,
                )

            except Exception as e:
                fail_count += len(batch_asins)
                self.error_occurred.emit(f"Pass 2 error: {e}")
                # Add failed ASINs to retry queue
                for asin in batch_asins:
                    self._add_to_retry_queue(asin)

            i += batch_size

        self.batch_completed.emit("pass2", success_count, fail_count)
        self.log_message.emit(f"Pass 2: Completed. Success: {success_count}, Failed: {fail_count}")

    def _get_spapi_data(
        self, candidate: AsinCandidate, keepa_snapshot: KeepaSnapshot
    ) -> SpApiSnapshot | None:
        """Get SP-API data for a candidate (cached or fresh)."""
        if not candidate.id:
            return None

        # Calculate sell price for fee query
        sell_gross = self.scoring.calculate_sell_gross_safe(
            keepa_snapshot.fbm_price_current,
            keepa_snapshot.fbm_price_median_30d,
            self.settings.get_brand_settings(candidate.brand.value).safe_price_buffer_pct,
        )

        if sell_gross <= 0:
            return None

        ttl = self.settings.refresh.spapi_cache_ttl_minutes

        # Check cache
        cached = self.repo.get_latest_spapi_snapshot(candidate.id, sell_price=sell_gross, ttl_minutes=ttl)
        if cached:
            return cached

        # Fetch fresh data
        try:
            snapshot = self.spapi.fetch_snapshot(candidate.asin, sell_gross)
            self.repo.save_spapi_snapshot(candidate.id, snapshot)

            self.repo.save_api_log(
                api_name="spapi",
                endpoint="fetch_snapshot",
                method="GET",
                request_params=f"asin={candidate.asin},price={sell_gross}",
                response_status=200,
                response_size=len(snapshot.raw_json),
                tokens_consumed=0,
                duration_ms=0,
                success=True,
            )

            return snapshot
        except Exception as e:
            self.repo.save_api_log(
                api_name="spapi",
                endpoint="fetch_snapshot",
                method="GET",
                request_params=f"asin={candidate.asin}",
                response_status=0,
                response_size=0,
                tokens_consumed=0,
                duration_ms=0,
                success=False,
                error_message=str(e),
            )
            return None

    def _batch_prefetch_spapi_fees(
        self,
        candidates: list[AsinCandidate],
        keepa_snapshots: dict[str, KeepaSnapshot],
    ) -> dict[str, dict]:
        """Batch prefetch SP-API fees for multiple candidates.

        Returns a dict mapping ASIN to fee response.
        """
        # Build list of (ASIN, price) pairs that need fee lookup
        items_needing_fees: list[tuple[str, Decimal]] = []
        asin_to_price: dict[str, Decimal] = {}
        ttl = self.settings.refresh.spapi_cache_ttl_minutes

        for candidate in candidates:
            if not candidate.id:
                continue

            keepa = keepa_snapshots.get(candidate.asin)
            if not keepa:
                continue

            sell_gross = self.scoring.calculate_sell_gross_safe(
                keepa.fbm_price_current,
                keepa.fbm_price_median_30d,
                self.settings.get_brand_settings(candidate.brand.value).safe_price_buffer_pct,
            )

            if sell_gross <= 0:
                continue

            # Check cache
            cached = self.repo.get_latest_spapi_snapshot(
                candidate.id, sell_price=sell_gross, ttl_minutes=ttl
            )
            if not cached:
                # Need to fetch
                if candidate.asin not in asin_to_price:
                    asin_to_price[candidate.asin] = sell_gross
                    items_needing_fees.append((candidate.asin, sell_gross))

        if not items_needing_fees:
            return {}

        self.log_message.emit(f"Batch fetching fees for {len(items_needing_fees)} ASINs...")

        try:
            fee_results = self.spapi.get_fees_estimates_batch(items_needing_fees, is_fba=False)

            self.repo.save_api_log(
                api_name="spapi",
                endpoint="batch_fees",
                method="POST",
                request_params=f"count={len(items_needing_fees)}",
                response_status=200,
                response_size=0,
                tokens_consumed=0,
                duration_ms=0,
                success=True,
            )

            return fee_results
        except Exception as e:
            self.repo.save_api_log(
                api_name="spapi",
                endpoint="batch_fees",
                method="POST",
                request_params=f"count={len(items_needing_fees)}",
                response_status=0,
                response_size=0,
                tokens_consumed=0,
                duration_ms=0,
                success=False,
                error_message=str(e),
            )
            self.log_message.emit(f"Batch fee fetch failed: {e}")
            return {}


class RefreshController(QObject):
    """Controls the background refresh thread."""

    # Forward signals
    token_status_updated = pyqtSignal(int, int, int)
    score_updated = pyqtSignal(str, str, int)
    batch_completed = pyqtSignal(str, int, int)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)
    alert_triggered = pyqtSignal(object)  # Alert object

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._thread: QThread | None = None
        self._worker: RefreshWorker | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Start the background refresh."""
        if self._is_running:
            return

        self._thread = QThread()
        self._worker = RefreshWorker(self.settings)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._worker.token_status_updated.connect(self.token_status_updated)
        self._worker.score_updated.connect(self.score_updated)
        self._worker.batch_completed.connect(self.batch_completed)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.log_message.connect(self.log_message)
        self._worker.alert_triggered.connect(self.alert_triggered)

        self._thread.started.connect(self._worker.start_refresh)
        self._thread.start()
        self._is_running = True

        logger.info("Refresh controller started")

    def stop(self) -> None:
        """Stop the background refresh."""
        if not self._is_running:
            return

        if self._worker:
            self._worker.stop_refresh()

        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)  # Wait up to 5 seconds

        self._is_running = False
        logger.info("Refresh controller stopped")

    def toggle(self) -> bool:
        """Toggle refresh on/off. Returns new state."""
        if self._is_running:
            self.stop()
        else:
            self.start()
        return self._is_running

    def queue_priority_refresh(self, asins: list[str]) -> None:
        """Add ASINs to the priority queue for immediate refresh."""
        if self._worker:
            self._worker.queue_priority_refresh(asins)
