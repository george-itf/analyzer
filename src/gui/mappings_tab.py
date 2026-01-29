"""Mappings tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
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
    """Optimized background worker for ASIN search with parallel batching."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(int, int)  # items_with_matches, total_candidates
    error = pyqtSignal(str)

    BATCH_SIZE = 20  # SP-API max identifiers per request
    MAX_WORKERS = 1  # Single worker to avoid rate limits
    BATCH_DELAY = 1.0  # Seconds between batches

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
        """Run optimized ASIN search with parallel batch processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from src.api.spapi import SpApiClient
        from src.core.config import get_settings
        from src.core.models import CandidateSource
        from decimal import Decimal
        import time

        settings = get_settings()
        spapi = SpApiClient(settings)
        repo = Repository()

        total = len(self._items)
        total_candidates = 0
        items_with_matches = 0
        processed = 0

        def is_valid_ean(ean: str) -> bool:
            """Validate EAN/UPC format and check digit."""
            if not ean or len(ean) < 8:
                return False
            # Remove leading zeros for UPC-A (12 digits) or EAN-13 (13 digits)
            if not ean.isdigit():
                return False
            if len(ean) not in (8, 12, 13, 14):  # EAN-8, UPC-A, EAN-13, GTIN-14
                return False
            # Verify check digit (modulo 10)
            try:
                digits = [int(d) for d in ean]
                if len(ean) == 13:
                    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:-1]))
                    check = (10 - (total % 10)) % 10
                    return check == digits[-1]
                return True  # Skip check digit validation for other lengths
            except:
                return False

        # Deduplicate EANs and map to items
        ean_to_items: dict[str, list[SupplierItem]] = {}
        items_without_ean: list[SupplierItem] = []
        invalid_eans: list[str] = []
        
        for item in self._items:
            ean = (item.ean or "").strip()
            if ean:
                if is_valid_ean(ean):
                    if ean not in ean_to_items:
                        ean_to_items[ean] = []
                    ean_to_items[ean].append(item)
                else:
                    invalid_eans.append(ean)
                    items_without_ean.append(item)
            else:
                items_without_ean.append(item)
        
        if invalid_eans:
            logger.warning(f"Skipped {len(invalid_eans)} invalid EANs: {invalid_eans[:5]}...")

        unique_eans = list(ean_to_items.keys())
        total_batches = (len(unique_eans) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        
        self.progress.emit(0, total, f"Found {len(unique_eans)} unique EANs in {total_batches} batches...")

        # Create batches
        batches = [
            unique_eans[i:i + self.BATCH_SIZE] 
            for i in range(0, len(unique_eans), self.BATCH_SIZE)
        ]

        def process_batch(batch_eans: list[str]) -> dict[str, list[dict]]:
            """Process a single batch of EANs with rate limit protection."""
            if self._cancelled:
                return {}
            try:
                result = spapi.search_catalog_by_identifiers_batch(batch_eans, "EAN")
                time.sleep(self.BATCH_DELAY)  # Pace requests to avoid rate limits
                return result
            except Exception as e:
                logger.warning(f"Batch failed: {e}")
                return {}

        # Process batches with thread pool - save results in real-time
        start_time = time.time()
        completed_batches = 0
        
        def save_batch_results(batch_result: dict[str, list[dict]]) -> tuple[int, int]:
            """Save batch results to database immediately. Returns (items_matched, candidates_saved)."""
            batch_matches = 0
            batch_candidates = 0
            
            for ean, api_items in batch_result.items():
                items_for_ean = ean_to_items.get(ean, [])
                
                for item in items_for_ean:
                    item_saved = 0
                    
                    for api_item in api_items:
                        asin = api_item.get("asin", "")
                        if not asin:
                            continue
                        
                        # Check if this ASIN already exists for this item
                        existing_with_asin = repo.get_candidate_by_asin(item.id, asin)
                        if existing_with_asin:
                            continue  # Already have this ASIN
                        
                        # Extract title and brand
                        summaries = api_item.get("summaries", [])
                        title = ""
                        amazon_brand = ""
                        for s in summaries:
                            if s.get("marketplaceId") == "A1F83G8C2ARO7P":
                                title = s.get("itemName", "")
                                amazon_brand = s.get("brand", "")
                                break
                        
                        confidence = Decimal("0.95")
                        
                        # Check for existing empty candidate to UPDATE
                        empty_candidate = repo.get_empty_candidate(item.id)
                        if empty_candidate and empty_candidate.id:
                            # Update existing empty candidate
                            repo.update_candidate_asin(
                                candidate_id=empty_candidate.id,
                                asin=asin,
                                title=title,
                                amazon_brand=amazon_brand,
                                confidence_score=confidence,
                                source=CandidateSource.SPAPI_EAN.value,
                                match_reason=f"EAN match: {ean}",
                            )
                            item_saved += 1
                        else:
                            # Create new candidate
                            candidate = AsinCandidate(
                                supplier_item_id=item.id,
                                brand=item.brand,
                                supplier=item.supplier,
                                part_number=item.part_number,
                                asin=asin,
                                title=title,
                                amazon_brand=amazon_brand,
                                match_reason=f"EAN match: {ean}",
                                confidence_score=confidence,
                                source=CandidateSource.SPAPI_EAN,
                                is_active=True,
                                is_primary=True,
                            )
                            repo.save_asin_candidate(candidate)
                            item_saved += 1
                        
                        # Clear other primaries for this item
                        repo.clear_other_primaries(item.id, asin)
                    
                    if item_saved > 0:
                        batch_candidates += item_saved
                        batch_matches += 1
                    else:
                        # Mark as searched but not found (update empty candidate's match_reason)
                        empty = repo.get_empty_candidate(item.id)
                        if empty and empty.id:
                            repo.mark_search_attempted(empty.id)
            
            return batch_matches, batch_candidates
        
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(process_batch, batch): i for i, batch in enumerate(batches)}
            
            for future in as_completed(futures):
                if self._cancelled:
                    break
                    
                batch_idx = futures[future]
                try:
                    result = future.result()
                    
                    # Save immediately to database
                    matches, candidates = save_batch_results(result)
                    items_with_matches += matches
                    total_candidates += candidates
                    processed += len(result) 
                    
                    completed_batches += 1
                    elapsed = time.time() - start_time
                    rate = completed_batches / elapsed if elapsed > 0 else 0
                    remaining = total_batches - completed_batches
                    eta = int(remaining / rate) if rate > 0 else 0
                    
                    self.progress.emit(
                        completed_batches * self.BATCH_SIZE, 
                        len(unique_eans),
                        f"Batch {completed_batches}/{total_batches} | Found: {total_candidates} | ETA: {eta}s"
                    )
                except Exception as e:
                    logger.warning(f"Batch {batch_idx} failed: {e}")

        # Mark items without EAN matches as needing keyword search
        # (Skip keyword search for now - too slow, can be done separately)
        items_no_match = len(items_without_ean)
        if items_no_match > 0:
            logger.info(f"{items_no_match} items without EAN skipped (keyword search too slow)")

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
                return QColor(220, 255, 220)  # Green for primary
            if not c.is_active:
                return QColor(240, 240, 240)  # Gray for inactive
            # Confidence-based coloring
            if col_key == "confidence":
                conf = float(c.confidence_score)
                if conf >= 0.90:
                    return QColor(200, 255, 200)  # Bright green
                elif conf >= 0.75:
                    return QColor(230, 255, 230)  # Light green
                elif conf >= 0.50:
                    return QColor(255, 255, 200)  # Yellow
                else:
                    return QColor(255, 220, 220)  # Light red

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
        self.search_asins_btn.setToolTip("Search for ASINs by EAN (fast, batched)")
        self.search_asins_btn.clicked.connect(self._on_search_asins)
        toolbar.addWidget(self.search_asins_btn)

        self.keyword_search_btn = QPushButton("Keyword Search")
        self.keyword_search_btn.setToolTip("Search by keywords for items without EAN matches (slower)")
        self.keyword_search_btn.clicked.connect(self._on_keyword_search)
        toolbar.addWidget(self.keyword_search_btn)

        self.duplicates_btn = QPushButton("Check Duplicates")
        self.duplicates_btn.setToolTip("Find ASINs mapped to multiple part numbers")
        self.duplicates_btn.clicked.connect(self._on_check_duplicates)
        toolbar.addWidget(self.duplicates_btn)

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
                    # Check if no candidates OR all candidates have empty ASINs AND not already searched
                    needs_search = (
                        not candidates or 
                        all(not c.asin and c.source != "spapi_ean_not_found" for c in candidates)
                    )
                    if needs_search:
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
        """Handle search completion with detailed statistics."""
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        self._search_worker = None

        # Calculate detailed stats
        brand_filter = self.brand_filter.currentText()
        brands = Brand.values() if brand_filter == "All" else [brand_filter]
        
        total_items = 0
        items_with_asin = 0
        items_no_match = 0
        
        for brand_name in brands:
            try:
                brand = Brand.from_string(brand_name)
            except ValueError:
                continue
            items = self._repo.get_supplier_items_by_brand(brand)
            for item in items:
                if item.id:
                    total_items += 1
                    candidates = self._repo.get_candidates_by_supplier_item(item.id, active_only=False)
                    if any(c.asin for c in candidates):
                        items_with_asin += 1
                    elif any(c.source == "spapi_ean_not_found" for c in candidates):
                        items_no_match += 1

        match_rate = (items_with_asin / total_items * 100) if total_items > 0 else 0

        QMessageBox.information(
            self,
            "ASIN Search Complete",
            f"Search completed!\n\n"
            f"📊 Overall Statistics:\n"
            f"  Total items: {total_items}\n"
            f"  With ASINs: {items_with_asin} ({match_rate:.1f}%)\n"
            f"  No match: {items_no_match}\n\n"
            f"This session:\n"
            f"  Matched: {items_with_matches}\n"
            f"  ASINs found: {total_candidates}",
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

    def _on_keyword_search(self) -> None:
        """Search for ASINs using keywords for items without EAN matches."""
        # Find items that were searched by EAN but not found
        brand_filter = self.brand_filter.currentText()
        brands = Brand.values() if brand_filter == "All" else [brand_filter]

        items_for_keyword: list[SupplierItem] = []

        for brand_name in brands:
            try:
                brand = Brand.from_string(brand_name)
            except ValueError:
                continue

            items = self._repo.get_supplier_items_by_brand(brand)
            for item in items:
                if item.id:
                    candidates = self._repo.get_candidates_by_supplier_item(item.id, active_only=False)
                    # Items with "not found" status or no EAN
                    for c in candidates:
                        if c.source == "spapi_ean_not_found" or (not c.asin and not item.ean):
                            items_for_keyword.append(item)
                            break

        if not items_for_keyword:
            QMessageBox.information(
                self,
                "No Items for Keyword Search",
                "No items need keyword search.\n"
                "Run 'Search ASINs' first to identify items without EAN matches.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Keyword Search",
            f"Found {len(items_for_keyword)} items for keyword search.\n\n"
            f"This is SLOWER than EAN search (1 item at a time).\n"
            f"Estimated time: {len(items_for_keyword) * 2} seconds.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # TODO: Implement keyword search worker
        QMessageBox.information(
            self,
            "Coming Soon",
            "Keyword search will be implemented in next update.\n"
            f"Items queued: {len(items_for_keyword)}",
        )

    def _on_check_duplicates(self) -> None:
        """Check for ASINs mapped to multiple part numbers."""
        duplicates = self._repo.find_duplicate_asins()
        
        if not duplicates:
            QMessageBox.information(
                self,
                "No Duplicates",
                "No ASINs are mapped to multiple part numbers. ✓",
            )
            return

        # Build report
        report = f"Found {len(duplicates)} ASINs mapped to multiple items:\n\n"
        for asin, count, parts in duplicates[:20]:  # Show first 20
            report += f"• {asin}: {count} items\n"
            report += f"  Parts: {', '.join(parts[:5])}"
            if len(parts) > 5:
                report += f" (+{len(parts)-5} more)"
            report += "\n\n"

        if len(duplicates) > 20:
            report += f"... and {len(duplicates) - 20} more duplicates"

        QMessageBox.warning(
            self,
            "Duplicate ASINs Found",
            report,
        )
