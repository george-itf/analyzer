"""Detail dialog for score breakdown and candidate details."""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.models import ProfitScenario, ScoreResult

from .widgets import FlagLabel, ScoreRingWidget


class DetailDialog(QDialog):
    """Dialog showing detailed score breakdown for a candidate."""

    def __init__(
        self,
        result: ScoreResult,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result = result
        self.setWindowTitle(f"Score Details - {result.part_number} / {result.asin}")
        self.setMinimumSize(750, 650)
        self._build_ui(title)

    def _build_ui(self, title: str) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Header
        header = self._build_header(title)
        content_layout.addWidget(header)

        # Score breakdown
        breakdown = self._build_breakdown()
        content_layout.addWidget(breakdown)

        # Scenarios side by side
        scenarios = self._build_scenarios()
        content_layout.addWidget(scenarios)

        # Flags
        flags = self._build_flags()
        content_layout.addWidget(flags)

        # Data sources
        data_info = self._build_data_info()
        content_layout.addWidget(data_info)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton("Export This Row")
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _build_header(self, title: str) -> QWidget:
        """Build the header section."""
        group = QGroupBox("Overview")
        layout = QHBoxLayout(group)

        # Score ring
        ring = ScoreRingWidget()
        ring.score = self.result.score
        layout.addWidget(ring)

        # Info
        info_layout = QVBoxLayout()

        label = QLabel(f"<b>{self.result.part_number}</b> - {self.result.asin}")
        label.setFont(QFont("", 14))
        info_layout.addWidget(label)

        if title:
            info_layout.addWidget(QLabel(title))

        info_layout.addWidget(QLabel(
            f"Brand: {self.result.brand.value} | Supplier: {self.result.supplier}"
        ))

        info_layout.addWidget(QLabel(
            f"Winning scenario: <b>{self.result.winning_scenario}</b> | "
            f"Confidence: {self.result.mapping_confidence:.0%}"
        ))

        layout.addLayout(info_layout, stretch=1)
        return group

    def _build_breakdown(self) -> QWidget:
        """Build the score breakdown section."""
        group = QGroupBox("Score Breakdown")
        layout = QGridLayout(group)

        b = self.result.breakdown

        headers = ["Component", "Raw (0-100)", "Weight", "Weighted"]
        for col, h in enumerate(headers):
            label = QLabel(f"<b>{h}</b>")
            layout.addWidget(label, 0, col)

        rows = [
            ("Velocity", b.velocity_raw, "0.45", b.velocity_weighted),
            ("Profit", b.profit_raw, "0.20", b.profit_weighted),
            ("Margin", b.margin_raw, "0.20", b.margin_weighted),
            ("Stability", b.stability_raw, "0.10", b.stability_weighted),
            ("Viability", b.viability_raw, "0.05", b.viability_weighted),
        ]

        for i, (name, raw, weight, weighted) in enumerate(rows, start=1):
            layout.addWidget(QLabel(name), i, 0)
            layout.addWidget(QLabel(f"{raw:.1f}"), i, 1)
            layout.addWidget(QLabel(weight), i, 2)
            layout.addWidget(QLabel(f"{weighted:.1f}"), i, 3)

        # Totals
        row = len(rows) + 1
        layout.addWidget(QLabel("<b>Weighted Sum</b>"), row, 0)
        layout.addWidget(QLabel(f"<b>{b.weighted_sum:.1f}</b>"), row, 3)

        row += 1
        layout.addWidget(QLabel("<b>Penalties</b>"), row, 0)
        layout.addWidget(QLabel(f"<b>-{b.total_penalties:.1f}</b>"), row, 3)

        row += 1
        layout.addWidget(QLabel("<b>Final Score</b>"), row, 0)
        label = QLabel(f"<b>{self.result.score}</b>")
        label.setFont(QFont("", 14))
        layout.addWidget(label, row, 3)

        return group

    def _build_scenarios(self) -> QWidget:
        """Build the cost scenarios comparison."""
        group = QGroupBox("Profit Scenarios")
        layout = QHBoxLayout(group)

        # Scenario 1
        s1 = self._scenario_box("Cost 1 (Single Unit)", self.result.scenario_cost_1)
        layout.addWidget(s1)

        # Scenario 5+
        s5 = self._scenario_box("Cost 5+ (Bulk)", self.result.scenario_cost_5plus)
        layout.addWidget(s5)

        return group

    def _scenario_box(self, title: str, scenario: ProfitScenario) -> QWidget:
        """Build a scenario details box."""
        group = QGroupBox(title)
        layout = QGridLayout(group)

        is_winner = scenario.scenario_name == self.result.winning_scenario
        if is_winner:
            group.setStyleSheet("QGroupBox { border: 2px solid #28a745; }")

        rows = [
            ("Cost ExVAT", f"£{scenario.cost_ex_vat:.2f}"),
            ("Sell Gross (safe)", f"£{scenario.sell_gross_safe:.2f}"),
            ("Sell Net (exVAT)", f"£{scenario.sell_net:.2f}"),
            ("Fees Gross", f"£{scenario.fees_gross:.2f}"),
            ("Fees Net (exVAT)", f"£{scenario.fees_net:.2f}"),
            ("Shipping Cost", f"£{scenario.shipping_cost:.2f}"),
            ("", ""),
            ("Profit Net", f"£{scenario.profit_net:.2f}"),
            ("Margin Net", f"{scenario.margin_net:.1%}"),
        ]

        for i, (label, value) in enumerate(rows):
            if not label:
                continue
            layout.addWidget(QLabel(label), i, 0)
            v_label = QLabel(f"<b>{value}</b>")
            if label in ("Profit Net", "Margin Net"):
                color = "#28a745" if scenario.is_profitable else "#dc3545"
                v_label.setStyleSheet(f"color: {color};")
            layout.addWidget(v_label, i, 1)

        if is_winner:
            layout.addWidget(QLabel("<b>* WINNING SCENARIO</b>"), len(rows), 0, 1, 2)

        return group

    def _build_flags(self) -> QWidget:
        """Build the flags section."""
        group = QGroupBox("Flags & Reasons")
        layout = QVBoxLayout(group)

        if not self.result.flags:
            layout.addWidget(QLabel("No flags"))
            return group

        for flag in self.result.flags:
            h = QHBoxLayout()
            flag_widget = FlagLabel(flag.code)
            h.addWidget(flag_widget)
            h.addWidget(QLabel(f"{flag.description} (penalty: -{flag.penalty:.0f})"), stretch=1)
            if flag.is_critical:
                h.addWidget(QLabel("<b>CRITICAL</b>"))
            layout.addLayout(h)

        return group

    def _build_data_info(self) -> QWidget:
        """Build the data sources info."""
        group = QGroupBox("Data Sources")
        layout = QGridLayout(group)

        rows = [
            ("Sales Proxy 30d", str(self.result.sales_proxy_30d) if self.result.sales_proxy_30d else "N/A"),
            ("Offer Count", str(self.result.offer_count) if self.result.offer_count else "N/A"),
            ("Amazon Present", "Yes" if self.result.amazon_present else "No"),
            ("Restricted", "Yes" if self.result.is_restricted else "No"),
            ("Weight (kg)", f"{self.result.weight_kg:.2f}" if self.result.weight_kg else "Unknown"),
            ("Keepa Data Time", self.result.keepa_data_time.strftime("%Y-%m-%d %H:%M") if self.result.keepa_data_time else "No data"),
            ("SP-API Data Time", self.result.spapi_data_time.strftime("%Y-%m-%d %H:%M") if self.result.spapi_data_time else "No data"),
        ]

        for i, (label, value) in enumerate(rows):
            layout.addWidget(QLabel(label), i, 0)
            layout.addWidget(QLabel(f"<b>{value}</b>"), i, 1)

        return group

    def _on_export(self) -> None:
        """Export this row."""
        from PyQt6.QtWidgets import QFileDialog

        from src.utils.export import Exporter

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Row",
            f"score_{self.result.part_number}_{self.result.asin}.csv",
            "CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if file_path:
            if file_path.endswith(".xlsx"):
                Exporter.export_to_xlsx([self.result], file_path)
            else:
                Exporter.export_to_csv([self.result], file_path)
