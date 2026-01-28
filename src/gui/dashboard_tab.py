"""Dashboard tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Brand, ScoreResult
from src.db.repository import Repository

from .charts import BarChartWidget, DonutChartWidget, ScoreDistributionWidget


class StatCard(QFrame):
    """A card widget displaying a single statistic."""

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        color: QColor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            StatCard {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        self.setMinimumSize(150, 100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(title_label)

        # Value
        self.value_label = QLabel(value)
        style = "font-size: 28px; font-weight: bold;"
        if color:
            style += f" color: {color.name()};"
        else:
            style += " color: #212529;"
        self.value_label.setStyleSheet(style)
        layout.addWidget(self.value_label)

        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("color: #6c757d; font-size: 11px;")
            layout.addWidget(subtitle_label)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self.value_label.setText(value)


class BrandSummaryWidget(QFrame):
    """Widget showing summary stats for a brand."""

    def __init__(self, brand: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.brand = brand
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            BrandSummaryWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Brand name header
        header = QLabel(brand)
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(header)

        # Stats grid
        stats_layout = QGridLayout()
        stats_layout.setSpacing(8)

        self.items_label = QLabel("0")
        self.opportunities_label = QLabel("0")
        self.avg_score_label = QLabel("0")
        self.total_profit_label = QLabel("£0")

        stats_layout.addWidget(QLabel("Items:"), 0, 0)
        stats_layout.addWidget(self.items_label, 0, 1)
        stats_layout.addWidget(QLabel("Score 60+:"), 0, 2)
        stats_layout.addWidget(self.opportunities_label, 0, 3)
        stats_layout.addWidget(QLabel("Avg Score:"), 1, 0)
        stats_layout.addWidget(self.avg_score_label, 1, 1)
        stats_layout.addWidget(QLabel("Est. Profit:"), 1, 2)
        stats_layout.addWidget(self.total_profit_label, 1, 3)

        layout.addLayout(stats_layout)

    def update_stats(
        self,
        items: int,
        opportunities: int,
        avg_score: float,
        total_profit: Decimal,
    ) -> None:
        """Update the displayed statistics."""
        self.items_label.setText(str(items))
        self.opportunities_label.setText(str(opportunities))
        self.avg_score_label.setText(f"{avg_score:.0f}")
        self.total_profit_label.setText(f"£{total_profit:.2f}")


class TopMoversWidget(QFrame):
    """Widget showing top score movers (up and down)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            TopMoversWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Header
        header = QLabel(title)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #212529;")
        layout.addWidget(header)

        # Content area
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(4)
        layout.addLayout(self.content_layout)

        # Placeholder
        self.placeholder = QLabel("No data yet")
        self.placeholder.setStyleSheet("color: #6c757d;")
        self.content_layout.addWidget(self.placeholder)

        layout.addStretch()

    def set_items(self, items: list[tuple[str, str, int, int]]) -> None:
        """Set the items to display. Each item is (part_number, asin, old_score, new_score)."""
        # Clear existing
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not items:
            self.placeholder = QLabel("No data yet")
            self.placeholder.setStyleSheet("color: #6c757d;")
            self.content_layout.addWidget(self.placeholder)
            return

        for part_number, asin, old_score, new_score in items[:5]:
            change = new_score - old_score
            color = "#28a745" if change > 0 else "#dc3545"
            sign = "+" if change > 0 else ""

            row = QLabel(f"{part_number}: {old_score} → {new_score} ({sign}{change})")
            row.setStyleSheet(f"color: {color}; font-size: 11px;")
            self.content_layout.addWidget(row)


class DashboardTab(QWidget):
    """Dashboard tab showing summary statistics and key metrics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = Repository()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)

        # Top stats row
        stats_group = QGroupBox("Overview")
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setSpacing(16)

        self.total_items_card = StatCard("Total Items", "0", "across all brands")
        self.active_opportunities_card = StatCard(
            "Opportunities",
            "0",
            "score ≥ 60",
            QColor("#28a745"),
        )
        self.avg_score_card = StatCard("Avg Score", "0", "all active items")
        self.restricted_card = StatCard(
            "Restricted",
            "0",
            "items blocked",
            QColor("#dc3545"),
        )
        self.last_refresh_card = StatCard("Last Refresh", "—", "")

        stats_layout.addWidget(self.total_items_card)
        stats_layout.addWidget(self.active_opportunities_card)
        stats_layout.addWidget(self.avg_score_card)
        stats_layout.addWidget(self.restricted_card)
        stats_layout.addWidget(self.last_refresh_card)
        stats_layout.addStretch()

        content_layout.addWidget(stats_group)

        # Brand summaries
        brands_group = QGroupBox("By Brand")
        brands_layout = QHBoxLayout(brands_group)
        brands_layout.setSpacing(16)

        self.brand_widgets: dict[str, BrandSummaryWidget] = {}
        for brand_name in Brand.values():
            widget = BrandSummaryWidget(brand_name)
            brands_layout.addWidget(widget)
            self.brand_widgets[brand_name] = widget

        brands_layout.addStretch()
        content_layout.addWidget(brands_group)

        # Charts row
        charts_group = QGroupBox("Analytics")
        charts_layout = QHBoxLayout(charts_group)
        charts_layout.setSpacing(16)

        # Score distribution histogram
        self.score_distribution = ScoreDistributionWidget()
        charts_layout.addWidget(self.score_distribution)

        # Opportunities by brand (donut)
        self.brand_donut = DonutChartWidget("Opportunities by Brand")
        charts_layout.addWidget(self.brand_donut)

        # Profit by brand (bar)
        self.profit_bar = BarChartWidget("Est. Profit by Brand")
        charts_layout.addWidget(self.profit_bar)

        charts_layout.addStretch()
        content_layout.addWidget(charts_group)

        # Movers row
        movers_group = QGroupBox("Recent Changes")
        movers_layout = QHBoxLayout(movers_group)
        movers_layout.setSpacing(16)

        self.top_gainers = TopMoversWidget("🔼 Top Gainers")
        self.top_losers = TopMoversWidget("🔽 Top Losers")
        self.new_opportunities = TopMoversWidget("🆕 New Opportunities")

        movers_layout.addWidget(self.top_gainers)
        movers_layout.addWidget(self.top_losers)
        movers_layout.addWidget(self.new_opportunities)
        movers_layout.addStretch()

        content_layout.addWidget(movers_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def refresh_data(self) -> None:
        """Refresh dashboard data from the database."""
        total_items = 0
        total_opportunities = 0
        total_restricted = 0
        all_scores: list[int] = []
        brand_stats: dict[str, dict] = {}

        for brand in Brand:
            candidates = self._repo.get_candidates_by_brand(brand, active_only=True)
            items_count = len(candidates)
            opportunities = 0
            restricted = 0
            scores: list[int] = []
            total_profit = Decimal("0")

            for candidate in candidates:
                if candidate.id:
                    latest = self._repo.get_latest_score(candidate.id)
                    if latest:
                        scores.append(latest.score)
                        all_scores.append(latest.score)
                        if latest.score >= 60:
                            opportunities += 1
                        total_profit += latest.profit_net

                    # Check restriction from latest spapi snapshot
                    spapi = self._repo.get_latest_spapi_snapshot(candidate.id)
                    if spapi and spapi.is_restricted:
                        restricted += 1

            avg_score = sum(scores) / len(scores) if scores else 0

            brand_stats[brand.value] = {
                "items": items_count,
                "opportunities": opportunities,
                "avg_score": avg_score,
                "total_profit": total_profit,
            }

            total_items += items_count
            total_opportunities += opportunities
            total_restricted += restricted

        # Update overview cards
        self.total_items_card.set_value(str(total_items))
        self.active_opportunities_card.set_value(str(total_opportunities))
        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        self.avg_score_card.set_value(f"{overall_avg:.0f}")
        self.restricted_card.set_value(str(total_restricted))
        self.last_refresh_card.set_value(datetime.now().strftime("%H:%M:%S"))

        # Update brand widgets
        for brand_name, stats in brand_stats.items():
            widget = self.brand_widgets.get(brand_name)
            if widget:
                widget.update_stats(
                    stats["items"],
                    stats["opportunities"],
                    stats["avg_score"],
                    stats["total_profit"],
                )

        # Update charts
        self.score_distribution.set_scores(all_scores)

        # Opportunities by brand donut chart
        brand_colors = {
            "Makita": "#00a0e0",   # Makita teal
            "DeWalt": "#febd17",   # DeWalt yellow
            "Timco": "#e74c3c",    # Red
        }
        donut_data = [
            (name, stats["opportunities"], brand_colors.get(name, "#6c757d"))
            for name, stats in brand_stats.items()
            if stats["opportunities"] > 0
        ]
        self.brand_donut.set_data(donut_data)

        # Profit by brand bar chart
        bar_data = [
            (name, float(stats["total_profit"]), brand_colors.get(name, "#6c757d"))
            for name, stats in brand_stats.items()
        ]
        self.profit_bar.set_data(bar_data)

        # Update movers (would need score history comparison - simplified for now)
        # In a full implementation, we'd compare today's scores to yesterday's
