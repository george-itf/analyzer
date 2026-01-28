"""Mappings tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.models import AsinCandidate, Brand, SupplierItem
from src.db.repository import Repository

logger = logging.getLogger(__name__)


class AsinSearchWorkerSingle(QThread):
    """Background worker to search for ASINs for selected items."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(int, int)  # items_with_matches, total_candidates
    error = pyqtSignal(str)

    def __init__(
        self,
        items: list[SupplierItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the search operation."""
        self._cancelled = True

    def run(self) -> None:
        """Run the ASIN search for selected items."""
        from src.api.spapi import SpApiClient
        from src.core.config import get_settings

        settings = get_settings()
        spapi = SpApiClient(settings)
        repo = Repository()

        total = len(self._items)
        total_candidates = 0
        items_with_matches = 0

        for i, item in enumerate(self._items):
            if self._cancelled:
                break

            self.progress.emit(i + 1, total, f"Searching {item.part_number}...")

            try:
                candidates = spapi.search_asins_for_item(
                    ean=item.ean,
                    mpn=item.mpn,
                    description=item.description,
                    brand=item.brand.value,
                )

                # Save candidates to database
                candidates_saved = 0
                for candidate in candidates:
                    # Check if this ASIN already exists for this item
                    existing = repo.get_candidate_by_asin(item.id, candidate.asin)
                    if not existing:
                        candidate.supplier_item_id = item.id
                        candidate.brand = item.brand
                        candidate.supplier = item.supplier
                        candidate.part_number = item.part_number
                        candidate.is_active = True
                        candidate.is_primary = candidates_saved == 0
                        repo.save_asin_candidate(candidate)
                        candidates_saved += 1

                if candidates_saved > 0:
                    total_candidates += candidates_saved
                    items_with_matches += 1

            except Exception as e:
                logger.warning(f"Failed to search ASINs for {item.part_number}: {e}")
                continue

        self.finished_signal.emit(items_with_matches, total_candidates)


class CandidateTableModel(QAbstractTableModel):
    """Table model for ASIN candidates."""

    COLUMNS = [
        ("ASIN", "asin"),
        ("Title", "title"),
        ("Confidence", "confidence"),
        ("Source", "source"),
        ("Active", "active"),
        ("Primary", "primary"),
        ("Locked", "locked"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._candidates: list[AsinCandidate] = []

    def set_candidates(self, candidates: list[AsinCandidate]) -> None:
        self.beginResetModel()
        self._candidates = candidates
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._candidates)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._candidates):
            return None

        c = self._candidates[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            match col_key:
                case "asin":
                    return c.asin
                case "title":
                    return c.title
                case "confidence":
                    return f"{c.confidence_score:.0%}"
                case "source":
                    return c.source.value
                case "active":
                    return "Yes" if c.is_active else "No"
                case "primary":
                    return "* PRIMARY" if c.is_primary else ""
                case "locked":
                    return "Locked" if c.is_locked else ""

        if role == Qt.ItemDataRole.BackgroundRole:
            if c.is_primary:
                return QColor(220, 255, 220)
            if not c.is_active:
                return QColor(240, 240, 240)

        if role == Qt.ItemDataRole.UserRole:
            return c

        return None

    def get_candidate(self, row: int) -> AsinCandidate | None:
        if 0 <= row < len(self._candidates):
            return self._candidates[row]
        return None


class MappingsTab(QWidget):
    """Tab widget for managing ASIN mappings."""

    mapping_updated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = Repository()
        self._search_worker: AsinSearchWorkerSingle | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Filter toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Brand:"))
        self.brand_filter = QComboBox()
        self.brand_filter.addItems(["All"] + Brand.values())
        self.brand_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.brand_filter)

        toolbar.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Part number or EAN...")
        self.search_input.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.search_input, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        self.search_asins_btn = QPushButton("Search ASINs")
        self.search_asins_btn.setToolTip("Search for ASINs for items without matches (uses SP-API)")
        self.search_asins_btn.clicked.connect(self._on_search_asins)
        toolbar.addWidget(self.search_asins_btn)

        layout.addLayout(toolbar)

        # Splitter: items tree on left, candidates on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: items tree
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Supplier Items"))

        self.items_tree = QTreeWidget()
        self.items_tree.setHeaderLabels(["Part Number", "Brand", "Supplier", "EAN", "MPN"])
        self.items_tree.setColumnWidth(0, 150)
        self.items_tree.currentItemChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.items_tree)
        splitter.addWidget(left_widget)

        # Right: candidates
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("ASIN Candidates"))

        self.candidate_model = CandidateTableModel(self)
        self.candidate_table = QTableView()
        self.candidate_table.setModel(self.candidate_model)
        self.candidate_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.candidate_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.candidate_table.setAlternatingRowColors(True)
        self.candidate_table.verticalHeader().setVisible(False)
        self.candidate_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.candidate_table)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.set_primary_btn = QPushButton("Set Primary")
        self.set_primary_btn.clicked.connect(self._on_set_primary)
        btn_layout.addWidget(self.set_primary_btn)

        self.toggle_active_btn = QPushButton("Toggle Active")
        self.toggle_active_btn.clicked.connect(self._on_toggle_active)
        btn_layout.addWidget(self.toggle_active_btn)

        self.lock_btn = QPushButton("Lock/Unlock")
        self.lock_btn.clicked.connect(self._on_toggle_lock)
        btn_layout.addWidget(self.lock_btn)

        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 500])

        layout.addWidget(splitter)

    def refresh_data(self) -> None:
        """Reload data from database."""
        self.items_tree.clear()

        brand_filter = self.brand_filter.currentText()
        search_text = self.search_input.text().lower()

        brands = Brand.values() if brand_filter == "All" else [brand_filter]

        for brand_name in brands:
            try:
                brand = Brand.from_string(brand_name)
            except ValueError:
                continue

            items = self._repo.get_supplier_items_by_brand(brand)

            for item in items:
                if search_text and search_text not in item.part_number.lower() and search_text not in item.ean.lower():
                    continue

                tree_item = QTreeWidgetItem([
                    item.part_number,
                    item.brand.value,
                    item.supplier,
                    item.ean,
                    item.mpn,
                ])
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item.id)
                self.items_tree.addTopLevelItem(tree_item)

    def _on_filter_changed(self) -> None:
        self.refresh_data()

    def _on_item_selected(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        """Handle item selection in the tree."""
        if not current:
            self.candidate_model.set_candidates([])
            return

        item_id = current.data(0, Qt.ItemDataRole.UserRole)
        if item_id:
            candidates = self._repo.get_candidates_by_supplier_item(item_id, active_only=False)
            self.candidate_model.set_candidates(candidates)

    def _get_selected_candidate(self) -> AsinCandidate | None:
        indexes = self.candidate_table.selectionModel().selectedRows()
        if indexes:
            return self.candidate_model.get_candidate(indexes[0].row())
        return None

    def _on_set_primary(self) -> None:
        candidate = self._get_selected_candidate()
        if candidate and candidate.id:
            self._repo.set_primary_candidate(candidate.supplier_item_id, candidate.id)
            self._refresh_candidates()
            self.mapping_updated.emit()

    def _on_toggle_active(self) -> None:
        candidate = self._get_selected_candidate()
        if candidate and candidate.id:
            self._repo.update_candidate_status(candidate.id, is_active=not candidate.is_active)
            self._refresh_candidates()
            self.mapping_updated.emit()

    def _on_toggle_lock(self) -> None:
        candidate = self._get_selected_candidate()
        if candidate and candidate.id:
            self._repo.update_candidate_status(candidate.id, is_locked=not candidate.is_locked)
            self._refresh_candidates()

    def _refresh_candidates(self) -> None:
        current = self.items_tree.currentItem()
        if current:
            self._on_item_selected(current, None)

    def _on_search_asins(self) -> None:
        """Search for ASINs for items without candidates."""
        # Get items that have no candidates
        brand_filter = self.brand_filter.currentText()
        brands = Brand.values() if brand_filter == "All" else [brand_filter]

        items_without_candidates: list[SupplierItem] = []

        for brand_name in brands:
            try:
                brand = Brand.from_string(brand_name)
            except ValueError:
                continue

            items = self._repo.get_supplier_items_by_brand(brand)
            for item in items:
                if item.id:
                    candidates = self._repo.get_candidates_by_supplier_item(item.id, active_only=False)
                    if not candidates:
                        items_without_candidates.append(item)

        if not items_without_candidates:
            QMessageBox.information(
                self,
                "No Items to Search",
                "All items already have ASIN candidates.\n"
                "Use the brand filter to narrow the search scope.",
            )
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Search ASINs",
            f"Found {len(items_without_candidates)} items without ASIN candidates.\n\n"
            f"This will search SP-API for matching ASINs.\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Create progress dialog
        self._progress_dialog = QProgressDialog(
            "Searching for ASINs...",
            "Cancel",
            0,
            len(items_without_candidates),
            self,
        )
        self._progress_dialog.setWindowTitle("ASIN Search")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.canceled.connect(self._on_search_cancelled)
        self._progress_dialog.show()

        # Start worker
        self._search_worker = AsinSearchWorkerSingle(items_without_candidates, self)
        self._search_worker.progress.connect(self._on_search_progress)
        self._search_worker.finished_signal.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_progress(self, current: int, total: int, message: str) -> None:
        """Handle search progress updates."""
        if self._progress_dialog:
            self._progress_dialog.setValue(current)
            self._progress_dialog.setLabelText(f"{current}/{total}: {message}")
            QApplication.processEvents()

    def _on_search_finished(self, items_with_matches: int, total_candidates: int) -> None:
        """Handle search completion."""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        self._search_worker = None

        QMessageBox.information(
            self,
            "ASIN Search Complete",
            f"Search completed!\n\n"
            f"Items with matches: {items_with_matches}\n"
            f"Total ASIN candidates found: {total_candidates}",
        )

        # Refresh the view
        self.refresh_data()
        self.mapping_updated.emit()

    def _on_search_error(self, error_msg: str) -> None:
        """Handle search error."""
        logger.error(f"ASIN search error: {error_msg}")

    def _on_search_cancelled(self) -> None:
        """Handle search cancellation."""
        if self._search_worker:
            self._search_worker.cancel()
            self._search_worker = None

        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        # Refresh to show any results found before cancellation
        self.refresh_data()
