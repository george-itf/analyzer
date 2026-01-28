"""Brand tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from src.core.models import Brand, ScoreResult

from .context_menu import TableContextMenu
from .detail_dialog import DetailDialog
from .widgets import ScoreRingDelegate, SparklineDelegate


def profit_color(profit: float) -> QColor:
    """Return color based on profit value - green for positive, red for negative."""
    if profit >= 10:
        return QColor(200, 255, 200)  # Strong green
    elif profit >= 5:
        return QColor(220, 255, 220)  # Light green
    elif profit >= 0:
        return QColor(240, 255, 240)  # Very light green
    elif profit >= -5:
        return QColor(255, 240, 240)  # Very light red
    else:
        return QColor(255, 200, 200)  # Red


def margin_color(margin: float) -> QColor:
    """Return color based on margin value."""
    if margin >= 0.20:
        return QColor(200, 255, 200)  # Strong green
    elif margin >= 0.15:
        return QColor(220, 255, 220)  # Light green
    elif margin >= 0.10:
        return QColor(240, 255, 240)  # Very light green
    elif margin >= 0:
        return QColor(255, 255, 240)  # Light yellow
    else:
        return QColor(255, 220, 220)  # Light red


COLUMN_TOOLTIPS = {
    "score": "Overall opportunity score (0-100). Higher is better.",
    "trend": "Profit trend over recent calculations.",
    "part_number": "Supplier part/SKU number.",
    "asin": "Amazon Standard Identification Number.",
    "title": "Product title from Amazon.",
    "cost_1": "Your cost for 1 unit (ex VAT).",
    "cost_5plus": "Your cost for 5+ units (ex VAT).",
    "sell_gross": "Safe selling price including VAT.",
    "profit": "Net profit per unit (ex VAT).",
    "margin": "Net profit margin (ex VAT).",
    "sales": "Estimated monthly sales (Keepa rank drops).",
    "offers": "Number of competing offers.",
    "amazon": "Is Amazon selling this product?",
    "restricted": "Is this product restricted for you?",
    "scenario": "Which cost scenario wins (1 or 5+).",
    "flags": "Warning flags (e.g., LOW_MARGIN, VOLATILE).",
    "updated": "When this score was last calculated.",
}


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
            # Profit/margin color gradients
            winning = (
                result.scenario_cost_1
                if result.winning_scenario == "cost_1"
                else result.scenario_cost_5plus
            )
            if col_key == "profit":
                return profit_color(float(winning.profit_net))
            if col_key == "margin":
                return margin_color(float(winning.margin_net))

        if role == Qt.ItemDataRole.ToolTipRole:
            tooltip = COLUMN_TOOLTIPS.get(col_key, "")
            if col_key == "flags" and result.flags:
                flag_details = "\n".join(f"• {f.code}: {f.description}" for f in result.flags)
                tooltip = f"{tooltip}\n\n{flag_details}" if tooltip else flag_details
            return tooltip if tooltip else None

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

    # Signal emitted when selection changes: (count, total_profit, avg_score)
    selection_changed = pyqtSignal(int, float, float)

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

        # Quick filters
        self.filter_restricted = QCheckBox("Hide Restricted")
        self.filter_restricted.stateChanged.connect(self._apply_filters)
        toolbar.addWidget(self.filter_restricted)

        self.filter_amazon = QCheckBox("Hide Amazon")
        self.filter_amazon.stateChanged.connect(self._apply_filters)
        toolbar.addWidget(self.filter_amazon)

        # Count label
        self.count_label = QLabel("0 items")
        toolbar.addWidget(self.count_label)

        # Column visibility button
        columns_btn = QToolButton()
        columns_btn.setText("Columns ▾")
        columns_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.columns_menu = QMenu(columns_btn)
        columns_btn.setMenu(self.columns_menu)
        toolbar.addWidget(columns_btn)

        # Bulk actions button
        bulk_btn = QToolButton()
        bulk_btn.setText("Bulk Actions ▾")
        bulk_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bulk_menu = QMenu(bulk_btn)
        bulk_btn.setMenu(self.bulk_menu)
        toolbar.addWidget(bulk_btn)

        # Setup bulk actions menu
        copy_asins_action = QAction("📋 Copy ASINs", self)
        copy_asins_action.triggered.connect(self._bulk_copy_asins)
        self.bulk_menu.addAction(copy_asins_action)

        copy_parts_action = QAction("📋 Copy Part Numbers", self)
        copy_parts_action.triggered.connect(self._bulk_copy_parts)
        self.bulk_menu.addAction(copy_parts_action)

        self.bulk_menu.addSeparator()

        open_amazon_action = QAction("🌐 Open All on Amazon (max 10)", self)
        open_amazon_action.triggered.connect(self._bulk_open_amazon)
        self.bulk_menu.addAction(open_amazon_action)

        self.bulk_menu.addSeparator()

        export_selected_action = QAction("💾 Export Selected", self)
        export_selected_action.triggered.connect(self._bulk_export)
        self.bulk_menu.addAction(export_selected_action)

        # Export button
        export_btn = QPushButton("Export All")
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
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)  # Multi-select
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

        # Connect double-click, context menu, and selection
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Empty state label (hidden by default)
        self.empty_label = QLabel("No items to display.\n\nImport a supplier CSV to get started.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #6c757d; font-size: 14px; padding: 40px;")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        # Setup column visibility menu
        self._setup_column_menu()

        # Sort by score descending by default
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _setup_column_menu(self) -> None:
        """Setup the column visibility menu."""
        self.column_actions: dict[int, QAction] = {}

        for i, (name, key) in enumerate(ScoreTableModel.COLUMNS):
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(i)
            action.triggered.connect(self._on_column_toggle)
            self.columns_menu.addAction(action)
            self.column_actions[i] = action

        # Hide some columns by default
        default_hidden = {"cost_5plus", "scenario", "updated"}
        for i, (name, key) in enumerate(ScoreTableModel.COLUMNS):
            if key in default_hidden:
                self.table.setColumnHidden(i, True)
                self.column_actions[i].setChecked(False)

    def _on_column_toggle(self) -> None:
        """Handle column visibility toggle."""
        action = self.sender()
        if action:
            col_index = action.data()
            self.table.setColumnHidden(col_index, not action.isChecked())

    def _on_context_menu(self, pos) -> None:
        """Show context menu for table row."""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        result = self.model.get_result(source_index.row())
        if result:
            menu = TableContextMenu(result, self)
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _apply_filters(self) -> None:
        """Apply all active filters."""
        # This is a simplified filter - for production, use a custom QSortFilterProxyModel
        # that checks multiple conditions
        self._on_filter_changed(self.filter_input.text())

    def _on_selection_changed(self) -> None:
        """Handle table selection change."""
        selected = self._get_selected_results()
        if not selected:
            self.selection_changed.emit(0, 0.0, 0.0)
            return

        total_profit = sum(
            float(
                r.scenario_cost_1.profit_net
                if r.winning_scenario == "cost_1"
                else r.scenario_cost_5plus.profit_net
            )
            for r in selected
        )
        avg_score = sum(r.score for r in selected) / len(selected)

        self.selection_changed.emit(len(selected), total_profit, avg_score)

    def _get_selected_results(self) -> list[ScoreResult]:
        """Get all selected ScoreResult objects."""
        results = []
        selection = self.table.selectionModel().selectedRows()

        for proxy_index in selection:
            source_index = self.proxy_model.mapToSource(proxy_index)
            result = self.model.get_result(source_index.row())
            if result:
                results.append(result)

        return results

    def _bulk_copy_asins(self) -> None:
        """Copy all selected ASINs to clipboard."""
        selected = self._get_selected_results()
        if not selected:
            return

        asins = [r.asin for r in selected]
        text = "\n".join(asins)

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _bulk_copy_parts(self) -> None:
        """Copy all selected part numbers to clipboard."""
        selected = self._get_selected_results()
        if not selected:
            return

        parts = [r.part_number for r in selected]
        text = "\n".join(parts)

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _bulk_open_amazon(self) -> None:
        """Open selected items on Amazon (max 10)."""
        import webbrowser

        selected = self._get_selected_results()[:10]  # Limit to 10
        if not selected:
            return

        if len(selected) > 5:
            reply = QMessageBox.question(
                self,
                "Open Multiple Tabs",
                f"This will open {len(selected)} browser tabs. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for result in selected:
            url = f"https://www.amazon.co.uk/dp/{result.asin}"
            webbrowser.open(url)

    def _bulk_export(self) -> None:
        """Export selected items to file."""
        from src.utils.export import Exporter

        selected = self._get_selected_results()
        if not selected:
            return

        default_name = Exporter.generate_filename(f"{self.brand.value}_selected", "xlsx")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Selected Data",
            default_name,
            "Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if file_path:
            if file_path.endswith(".csv"):
                Exporter.export_to_csv(selected, file_path)
            else:
                Exporter.export_to_xlsx(selected, file_path)

    def update_results(
        self,
        results: list[ScoreResult],
        titles: dict[str, str] | None = None,
        profit_history: dict[int, list[float]] | None = None,
    ) -> None:
        """Update the table with new results."""
        self.model.set_results(results, titles, profit_history)
        self.count_label.setText(f"{len(results)} items")

        # Show/hide empty state
        has_data = len(results) > 0
        self.table.setVisible(has_data)
        self.empty_label.setVisible(not has_data)

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
