"""Context menu actions for table views."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

if TYPE_CHECKING:
    from src.core.models import ScoreResult


class TableContextMenu(QMenu):
    """Context menu for score result tables."""

    def __init__(self, result: ScoreResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result = result
        self._build_menu()

    def _build_menu(self) -> None:
        """Build the context menu actions."""
        # Copy actions
        copy_menu = self.addMenu("📋 Copy")

        copy_asin = QAction("ASIN", self)
        copy_asin.triggered.connect(lambda: self._copy_to_clipboard(self.result.asin))
        copy_menu.addAction(copy_asin)

        copy_part = QAction("Part Number", self)
        copy_part.triggered.connect(lambda: self._copy_to_clipboard(self.result.part_number))
        copy_menu.addAction(copy_part)

        copy_both = QAction("ASIN + Part Number", self)
        copy_both.triggered.connect(
            lambda: self._copy_to_clipboard(f"{self.result.asin}\t{self.result.part_number}")
        )
        copy_menu.addAction(copy_both)

        self.addSeparator()

        # Open on Amazon
        amazon_action = QAction("🌐 Open on Amazon UK", self)
        amazon_action.triggered.connect(self._open_amazon)
        self.addAction(amazon_action)

        # Open on Keepa
        keepa_action = QAction("📊 Open on Keepa", self)
        keepa_action.triggered.connect(self._open_keepa)
        self.addAction(keepa_action)

        self.addSeparator()

        # Info
        winning = (
            self.result.scenario_cost_1
            if self.result.winning_scenario == "cost_1"
            else self.result.scenario_cost_5plus
        )

        info_menu = self.addMenu("ℹ️ Quick Info")

        score_info = QAction(f"Score: {self.result.score}", self)
        score_info.setEnabled(False)
        info_menu.addAction(score_info)

        profit_info = QAction(f"Profit: £{winning.profit_net:.2f}", self)
        profit_info.setEnabled(False)
        info_menu.addAction(profit_info)

        margin_info = QAction(f"Margin: {winning.margin_net:.1%}", self)
        margin_info.setEnabled(False)
        info_menu.addAction(margin_info)

        if self.result.sales_proxy_30d:
            sales_info = QAction(f"Sales/30d: {self.result.sales_proxy_30d}", self)
            sales_info.setEnabled(False)
            info_menu.addAction(sales_info)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _open_amazon(self) -> None:
        """Open the product on Amazon UK."""
        url = f"https://www.amazon.co.uk/dp/{self.result.asin}"
        webbrowser.open(url)

    def _open_keepa(self) -> None:
        """Open the product on Keepa."""
        url = f"https://keepa.com/#!product/2-{self.result.asin}"
        webbrowser.open(url)
