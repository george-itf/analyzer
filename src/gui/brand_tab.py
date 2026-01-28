"""Brand tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Brand, ScoreResult

from .detail_dialog import DetailDialog
from .widgets import ScoreRingDelegate, SparklineDelegate


class ScoreTableModel(QAbstractTableModel):
    """Table model for displaying score results."""

    COLUMNS = [
        ("Score", "score"),
        ("Trend", "trend"),
        ("Part Number", "part_number"),
        ("ASIN", "asin"),
        ("Title", "title"),
        ("Cost 1 ExVAT", "cost_1"),
        ("Cost 5+ ExVAT", "cost_5plus"),
        ("Sell Gross", "sell_gross"),
        ("Profit ExVAT", "profit"),
        ("Margin ExVAT", "margin"),
        ("Sales 30d", "sales"),
        ("Offers", "offers"),
        ("Amazon", "amazon"),
        ("Restricted", "restricted"),
        ("Scenario", "scenario"),
        ("Flags", "flags"),
        ("Updated", "updated"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[ScoreResult] = []
        self._titles: dict[str, str] = {}  # asin -> title
        self._profit_history: dict[int, list[float]] = {}  # candidate_id -> list of profit values

    def set_results(
        self,
        results: list[ScoreResult],
        titles: dict[str, str] | None = None,
        profit_history: dict[int, list[float]] | None = None,
    ) -> None:
        """Update the results data."""
        self.beginResetModel()
        self._results = results
        if titles:
            self._titles = titles
        if profit_history:
            self._profit_history = profit_history
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._results)

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
        if not index.isValid() or index.row() >= len(self._results):
            return None

        result = self._results[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(result, col_key)

        if role == Qt.ItemDataRole.UserRole:
            # For trend column, return the sparkline data
            if col_key == "trend":
                return self._profit_history.get(result.asin_candidate_id, [])
            return result

        if role == Qt.ItemDataRole.BackgroundRole:
            if col_key == "restricted" and result.is_restricted:
                return QColor(255, 200, 200)
            if col_key == "amazon" and result.amazon_present:
                return QColor(255, 230, 200)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("score", "trend", "cost_1", "cost_5plus", "sell_gross", "profit", "margin", "sales", "offers"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _get_display_value(self, result: ScoreResult, col_key: str) -> Any:
        """Get the display value for a column."""
        winning = (
            result.scenario_cost_1
            if result.winning_scenario == "cost_1"
            else result.scenario_cost_5plus
        )

        match col_key:
            case "score":
                return result.score
            case "trend":
                # Display value is empty - sparkline delegate handles rendering
                history = self._profit_history.get(result.asin_candidate_id, [])
                if len(history) < 2:
                    return "—"
                return ""
            case "part_number":
                return result.part_number
            case "asin":
                return result.asin
            case "title":
                return self._titles.get(result.asin, "")
            case "cost_1":
                return f"£{result.scenario_cost_1.cost_ex_vat:.2f}"
            case "cost_5plus":
                return f"£{result.scenario_cost_5plus.cost_ex_vat:.2f}"
            case "sell_gross":
                return f"£{winning.sell_gross_safe:.2f}"
            case "profit":
                return f"£{winning.profit_net:.2f}"
            case "margin":
                return f"{winning.margin_net:.1%}"
            case "sales":
                return result.sales_proxy_30d if result.sales_proxy_30d is not None else "—"
            case "offers":
                return result.offer_count if result.offer_count is not None else "—"
            case "amazon":
                return "Yes" if result.amazon_present else "No"
            case "restricted":
                return "Yes" if result.is_restricted else "No"
            case "scenario":
                return result.winning_scenario.replace("cost_", "")
            case "flags":
                return ", ".join(f.code for f in result.flags) if result.flags else ""
            case "updated":
                if result.calculated_at:
                    return result.calculated_at.strftime("%H:%M:%S")
                return "—"
            case _:
                return ""

    def get_result(self, row: int) -> ScoreResult | None:
        """Get the ScoreResult for a given row."""
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def get_all_results(self) -> list[ScoreResult]:
        """Get all current results."""
        return list(self._results)


class BrandTab(QWidget):
    """Tab widget for displaying brand-specific opportunity data."""

    def __init__(self, brand: Brand, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.brand = brand
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        toolbar = QHBoxLayout()

        # Search/filter
        toolbar.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search by part number, ASIN, or flags...")
        self.filter_input.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_input, stretch=1)

        # Score filter
        toolbar.addWidget(QLabel("Min Score:"))
        self.score_filter = QComboBox()
        self.score_filter.addItems(["All", "0+", "20+", "40+", "60+", "80+"])
        self.score_filter.currentTextChanged.connect(self._on_score_filter_changed)
        toolbar.addWidget(self.score_filter)

        # Count label
        self.count_label = QLabel("0 items")
        toolbar.addWidget(self.count_label)

        # Export button
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # Table
        self.model = ScoreTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Search all columns
        self.proxy_model.setSortRole(Qt.ItemDataRole.DisplayRole)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Score ring delegate for first column
        score_delegate = ScoreRingDelegate(self.table)
        self.table.setItemDelegateForColumn(0, score_delegate)

        # Sparkline delegate for trend column (column 1)
        sparkline_delegate = SparklineDelegate(self.table)
        self.table.setItemDelegateForColumn(1, sparkline_delegate)

        # Set column widths
        self.table.setColumnWidth(0, 65)  # Score ring
        self.table.setColumnWidth(1, 80)  # Trend sparkline
        self.table.setColumnWidth(2, 120)  # Part Number
        self.table.setColumnWidth(3, 120)  # ASIN
        self.table.setColumnWidth(4, 200)  # Title
        self.table.setColumnWidth(5, 90)  # Cost 1
        self.table.setColumnWidth(6, 90)  # Cost 5+
        self.table.setColumnWidth(7, 90)  # Sell
        self.table.setColumnWidth(8, 90)  # Profit
        self.table.setColumnWidth(9, 80)  # Margin

        # Set row height for score rings
        self.table.verticalHeader().setDefaultSectionSize(55)

        # Connect double-click
        self.table.doubleClicked.connect(self._on_row_double_clicked)

        layout.addWidget(self.table)

        # Sort by score descending by default
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def update_results(
        self,
        results: list[ScoreResult],
        titles: dict[str, str] | None = None,
        profit_history: dict[int, list[float]] | None = None,
    ) -> None:
        """Update the table with new results."""
        self.model.set_results(results, titles, profit_history)
        self.count_label.setText(f"{len(results)} items")

    def _on_filter_changed(self, text: str) -> None:
        """Handle filter text change."""
        self.proxy_model.setFilterFixedString(text)

    def _on_score_filter_changed(self, text: str) -> None:
        """Handle score filter change."""
        # Custom filtering would go here; using simple approach
        if text == "All":
            self.proxy_model.setFilterFixedString("")
        else:
            # Filter is applied across all columns, so just clear for now
            # In production, use custom filter
            pass

    def _on_row_double_clicked(self, index: QModelIndex) -> None:
        """Handle double-click on a row."""
        source_index = self.proxy_model.mapToSource(index)
        result = self.model.get_result(source_index.row())
        if result:
            title = self.model._titles.get(result.asin, "")
            dialog = DetailDialog(result, title=title, parent=self)
            dialog.exec()

    def _on_export(self) -> None:
        """Export current view to file."""
        from src.utils.export import Exporter

        results = self.model.get_all_results()
        if not results:
            return

        default_name = Exporter.generate_filename(self.brand.value, "xlsx")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            default_name,
            "Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if file_path:
            if file_path.endswith(".csv"):
                Exporter.export_to_csv(results, file_path)
            else:
                Exporter.export_to_xlsx(results, file_path)
