"""Competitors tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.competitors import CompetitorOffer, CompetitorSnapshot, CompetitorTracker


class CompetitorTableModel(QAbstractTableModel):
    """Table model for displaying competitor offers."""

    COLUMNS = [
        ("Seller", "seller_name"),
        ("Price", "price"),
        ("Shipping", "shipping"),
        ("Total", "total_price"),
        ("FBA", "is_fba"),
        ("Amazon", "is_amazon"),
        ("Buy Box", "is_buy_box"),
        ("Rating", "rating"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._offers: list[CompetitorOffer] = []

    def set_offers(self, offers: list[CompetitorOffer]) -> None:
        """Update the offers data."""
        self.beginResetModel()
        self._offers = offers
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._offers)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._offers):
            return None

        offer = self._offers[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            match col_key:
                case "seller_name":
                    name = offer.seller_name or offer.seller_id
                    return name[:30] + "..." if len(name) > 30 else name
                case "price":
                    return f"£{offer.price:.2f}"
                case "shipping":
                    return f"£{offer.shipping:.2f}" if offer.shipping else "Free"
                case "total_price":
                    return f"£{offer.total_price:.2f}"
                case "is_fba":
                    return "FBA" if offer.is_fba else "FBM"
                case "is_amazon":
                    return "Yes" if offer.is_amazon else ""
                case "is_buy_box":
                    return "✓" if offer.is_buy_box else ""
                case "rating":
                    if offer.rating:
                        return f"{offer.rating:.1f}% ({offer.rating_count or 0})"
                    return "—"
            return ""

        if role == Qt.ItemDataRole.BackgroundRole:
            if offer.is_buy_box:
                return QColor(200, 255, 200)  # Light green for buy box
            if offer.is_amazon:
                return QColor(255, 220, 200)  # Light orange for Amazon
            if offer.is_fba:
                return QColor(230, 240, 255)  # Light blue for FBA

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("price", "shipping", "total_price"):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None


class CompetitorsTab(QWidget):
    """Tab widget for viewing competitor data."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracker = CompetitorTracker()
        self._current_asin: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ASIN selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("ASIN:"))

        self.asin_combo = QComboBox()
        self.asin_combo.setMinimumWidth(150)
        self.asin_combo.setEditable(True)
        self.asin_combo.currentTextChanged.connect(self._on_asin_changed)
        selector_layout.addWidget(self.asin_combo)

        selector_layout.addStretch()

        # Summary labels
        self.summary_label = QLabel("No data")
        selector_layout.addWidget(self.summary_label)

        layout.addLayout(selector_layout)

        # Summary stats
        stats_group = QGroupBox("Summary")
        stats_layout = QHBoxLayout(stats_group)

        self.total_offers_label = QLabel("Total: —")
        self.fba_offers_label = QLabel("FBA: —")
        self.fbm_offers_label = QLabel("FBM: —")
        self.buy_box_label = QLabel("Buy Box: —")
        self.lowest_price_label = QLabel("Lowest: —")

        stats_layout.addWidget(self.total_offers_label)
        stats_layout.addWidget(self.fba_offers_label)
        stats_layout.addWidget(self.fbm_offers_label)
        stats_layout.addWidget(self.buy_box_label)
        stats_layout.addWidget(self.lowest_price_label)
        stats_layout.addStretch()

        layout.addWidget(stats_group)

        # Offers table
        self.model = CompetitorTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Column widths
        self.table.setColumnWidth(0, 200)  # Seller
        self.table.setColumnWidth(1, 80)   # Price
        self.table.setColumnWidth(2, 80)   # Shipping
        self.table.setColumnWidth(3, 80)   # Total
        self.table.setColumnWidth(4, 50)   # FBA
        self.table.setColumnWidth(5, 60)   # Amazon
        self.table.setColumnWidth(6, 60)   # Buy Box

        layout.addWidget(self.table)

    def _on_asin_changed(self, asin: str) -> None:
        """Handle ASIN selection change."""
        self._current_asin = asin.strip().upper()
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display for the current ASIN."""
        if not self._current_asin:
            self.model.set_offers([])
            self._clear_stats()
            return

        snapshot = self._tracker.get_latest_snapshot(self._current_asin)
        if not snapshot:
            self.model.set_offers([])
            self._clear_stats()
            self.summary_label.setText("No data for this ASIN")
            return

        # Update table
        self.model.set_offers(snapshot.offers)

        # Update stats
        self.total_offers_label.setText(f"Total: {snapshot.total_offers}")
        self.fba_offers_label.setText(f"FBA: {snapshot.fba_offers}")
        self.fbm_offers_label.setText(f"FBM: {snapshot.fbm_offers}")

        if snapshot.buy_box_price:
            self.buy_box_label.setText(f"Buy Box: £{snapshot.buy_box_price:.2f}")
        else:
            self.buy_box_label.setText("Buy Box: —")

        if snapshot.lowest_price:
            self.lowest_price_label.setText(f"Lowest: £{snapshot.lowest_price:.2f}")
        else:
            self.lowest_price_label.setText("Lowest: —")

        self.summary_label.setText(f"Last updated: {snapshot.snapshot_time.strftime('%H:%M:%S')}")

    def _clear_stats(self) -> None:
        """Clear all stat labels."""
        self.total_offers_label.setText("Total: —")
        self.fba_offers_label.setText("FBA: —")
        self.fbm_offers_label.setText("FBM: —")
        self.buy_box_label.setText("Buy Box: —")
        self.lowest_price_label.setText("Lowest: —")
        self.summary_label.setText("No data")

    def add_snapshot(self, snapshot: CompetitorSnapshot) -> None:
        """Add a competitor snapshot and refresh if it's the current ASIN."""
        self._tracker.add_snapshot(snapshot)

        # Update ASIN combo
        asins = self._tracker.get_all_asins()
        current_text = self.asin_combo.currentText()
        self.asin_combo.clear()
        self.asin_combo.addItems(asins)
        if current_text:
            self.asin_combo.setCurrentText(current_text)

        # Refresh if this is the current ASIN
        if snapshot.asin == self._current_asin:
            self._refresh_display()

    def set_asin(self, asin: str) -> None:
        """Set the current ASIN to display."""
        self.asin_combo.setCurrentText(asin)
