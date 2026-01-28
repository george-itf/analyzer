"""Alert management for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from .models import Alert, AlertType, ScoreHistory, ScoreResult

if TYPE_CHECKING:
    from .config import AlertConfig

logger = logging.getLogger(__name__)


class AlertManager(QObject):
    """Manages alerts for score and profit changes."""

    # Signal emitted when a new alert is created
    alert_triggered = pyqtSignal(object)  # Alert object

    def __init__(self, config: AlertConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._alerts: deque[Alert] = deque(maxlen=100)  # Keep last 100 alerts
        self._previous_scores: dict[int, ScoreHistory] = {}  # candidate_id -> last score

    @property
    def alerts(self) -> list[Alert]:
        """Get all alerts."""
        return list(self._alerts)

    @property
    def unread_count(self) -> int:
        """Get count of unread alerts."""
        return sum(1 for a in self._alerts if not a.is_read and not a.is_dismissed)

    def update_previous_score(self, candidate_id: int, score: ScoreHistory) -> None:
        """Update the cached previous score for a candidate."""
        self._previous_scores[candidate_id] = score

    def check_for_alerts(
        self,
        result: ScoreResult,
        previous: ScoreHistory | None = None,
        is_new: bool = False,
    ) -> list[Alert]:
        """Check if a score result should trigger any alerts.

        Args:
            result: The new score result
            previous: The previous score (if known)
            is_new: Whether this is a newly discovered item

        Returns:
            List of alerts triggered
        """
        if not self.config.enabled:
            return []

        alerts: list[Alert] = []

        # Check for new opportunity
        if is_new and result.score >= self.config.new_opportunity_min_score:
            alert = Alert(
                alert_type=AlertType.NEW_OPPORTUNITY,
                asin=result.asin,
                part_number=result.part_number,
                brand=result.brand.value,
                message=f"New opportunity: {result.part_number} scores {result.score}",
                new_value=Decimal(str(result.score)),
                created_at=datetime.now(),
            )
            alerts.append(alert)

        # Check for score changes vs previous
        if previous:
            score_change = result.score - previous.score
            profit_change = result.get_best_profit() - previous.profit_net

            # Score increase alert
            if score_change >= self.config.score_increase_threshold:
                alert = Alert(
                    alert_type=AlertType.SCORE_INCREASE,
                    asin=result.asin,
                    part_number=result.part_number,
                    brand=result.brand.value,
                    message=f"Score increased: {result.part_number} {previous.score} → {result.score} (+{score_change})",
                    old_value=Decimal(str(previous.score)),
                    new_value=Decimal(str(result.score)),
                    created_at=datetime.now(),
                )
                alerts.append(alert)

            # Score decrease alert
            if score_change <= -self.config.score_decrease_threshold:
                alert = Alert(
                    alert_type=AlertType.SCORE_DECREASE,
                    asin=result.asin,
                    part_number=result.part_number,
                    brand=result.brand.value,
                    message=f"Score decreased: {result.part_number} {previous.score} → {result.score} ({score_change})",
                    old_value=Decimal(str(previous.score)),
                    new_value=Decimal(str(result.score)),
                    created_at=datetime.now(),
                )
                alerts.append(alert)

            # Score crosses above threshold
            if previous.score < self.config.score_above_threshold <= result.score:
                alert = Alert(
                    alert_type=AlertType.SCORE_THRESHOLD,
                    asin=result.asin,
                    part_number=result.part_number,
                    brand=result.brand.value,
                    message=f"Score above threshold: {result.part_number} now {result.score} (was {previous.score})",
                    old_value=Decimal(str(previous.score)),
                    new_value=Decimal(str(result.score)),
                    created_at=datetime.now(),
                )
                alerts.append(alert)

            # Profit increase alert
            if profit_change >= self.config.profit_increase_threshold:
                alert = Alert(
                    alert_type=AlertType.PROFIT_INCREASE,
                    asin=result.asin,
                    part_number=result.part_number,
                    brand=result.brand.value,
                    message=f"Profit increased: {result.part_number} £{previous.profit_net:.2f} → £{result.get_best_profit():.2f}",
                    old_value=previous.profit_net,
                    new_value=result.get_best_profit(),
                    created_at=datetime.now(),
                )
                alerts.append(alert)

            # Restriction status change
            if hasattr(previous, 'is_restricted') and previous.is_restricted != result.is_restricted:
                status = "now restricted" if result.is_restricted else "no longer restricted"
                alert = Alert(
                    alert_type=AlertType.RESTRICTION_CHANGE,
                    asin=result.asin,
                    part_number=result.part_number,
                    brand=result.brand.value,
                    message=f"Restriction change: {result.part_number} is {status}",
                    created_at=datetime.now(),
                )
                alerts.append(alert)

        # Store alerts and emit signals
        for alert in alerts:
            self._alerts.append(alert)
            self.alert_triggered.emit(alert)
            logger.info(f"Alert: {alert.message}")

        return alerts

    def mark_read(self, alert: Alert) -> None:
        """Mark an alert as read."""
        alert.is_read = True

    def mark_all_read(self) -> None:
        """Mark all alerts as read."""
        for alert in self._alerts:
            alert.is_read = True

    def dismiss(self, alert: Alert) -> None:
        """Dismiss an alert."""
        alert.is_dismissed = True

    def clear_all(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()
        self._previous_scores.clear()

    def get_recent_alerts(self, limit: int = 20) -> list[Alert]:
        """Get recent alerts."""
        return list(self._alerts)[-limit:]

    def get_unread_alerts(self) -> list[Alert]:
        """Get all unread alerts."""
        return [a for a in self._alerts if not a.is_read and not a.is_dismissed]
