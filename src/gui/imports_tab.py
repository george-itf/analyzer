"""Imports tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.csv_importer import CsvImporter, CsvValidationError
from src.core.models import AsinCandidate, Brand, CandidateSource, SupplierItem
from src.db.repository import Repository

logger = logging.getLogger(__name__)


class AsinSearchWorker(QThread):
    """Background worker to search for ASINs via SP-API."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    item_found = pyqtSignal(int, int)  # supplier_item_id, candidates_found
    finished_signal = pyqtSignal(int, int)  # total_items, total_candidates
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
        """Run the ASIN search for all items."""
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

            # Skip items that already have ASIN hints (they already have candidates)
            if item.asin_hint:
                self.progress.emit(i + 1, total, f"Skipped {item.part_number} (has ASIN)")
                continue

            # Search for ASINs using EAN, MPN, and description
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
                        candidate.is_primary = candidates_saved == 0  # First one is primary
                        repo.save_asin_candidate(candidate)
                        candidates_saved += 1

                if candidates_saved > 0:
                    total_candidates += candidates_saved
                    items_with_matches += 1
                    self.item_found.emit(item.id, candidates_saved)

            except Exception as e:
                logger.warning(f"Failed to search ASINs for {item.part_number}: {e}")
                continue

        self.finished_signal.emit(items_with_matches, total_candidates)


class ImportsTab(QWidget):
    """Tab widget for importing supplier CSV files."""

    import_completed = pyqtSignal(str)  # Signal emitted with batch_id after import

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = Repository()
        self._importer = CsvImporter()
        self._current_file: str | None = None
        self._search_worker: AsinSearchWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # File selection
        file_group = QGroupBox("File Selection")
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, stretch=1)

        browse_btn = QPushButton("Browse CSV...")
        browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Required headers info
        headers_group = QGroupBox("Required CSV Headers")
        headers_layout = QVBoxLayout(headers_group)
        headers_text = ", ".join(self._importer.get_required_headers())
        headers_layout.addWidget(QLabel(headers_text))
        headers_layout.addWidget(QLabel(
            "Brand must be one of: " + ", ".join(Brand.values())
        ))
        layout.addWidget(headers_group)

        # Preview table
        preview_group = QGroupBox("Preview (First 10 Rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Validation messages
        validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout(validation_group)

        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setMaximumHeight(120)
        validation_layout.addWidget(self.validation_text)

        layout.addWidget(validation_group)

        # Auto-search checkbox
        self.auto_search_checkbox = QCheckBox("Auto-search ASINs after import (uses SP-API)")
        self.auto_search_checkbox.setChecked(True)
        layout.addWidget(self.auto_search_checkbox)

        # Import button and progress
        import_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        import_layout.addWidget(self.progress_bar, stretch=1)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        import_layout.addWidget(self.progress_label)

        self.import_btn = QPushButton("Import File")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_import)
        import_layout.addWidget(self.import_btn)

        self.cancel_btn = QPushButton("Cancel Search")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel_search)
        import_layout.addWidget(self.cancel_btn)

        layout.addLayout(import_layout)

        # Import history
        history_group = QGroupBox("Import Log")
        history_layout = QVBoxLayout(history_group)

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setMaximumHeight(150)
        history_layout.addWidget(self.history_text)

        layout.addWidget(history_group)

    def _on_browse(self) -> None:
        """Open file browser to select CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Supplier CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        self._current_file = file_path
        self.file_label.setText(Path(file_path).name)
        self._preview_file(file_path)

    def _preview_file(self, file_path: str) -> None:
        """Preview the CSV file contents."""
        self.validation_text.clear()
        self.preview_table.clear()

        try:
            rows, errors = self._importer.preview(file_path, max_rows=10)
        except CsvValidationError as e:
            self.validation_text.setTextColor(Qt.GlobalColor.red)
            self.validation_text.setText(str(e))
            if e.missing_headers:
                self.validation_text.append(
                    f"\nRequired headers: {', '.join(self._importer.get_required_headers())}"
                )
            self.import_btn.setEnabled(False)
            return
        except FileNotFoundError as e:
            self.validation_text.setTextColor(Qt.GlobalColor.red)
            self.validation_text.setText(str(e))
            self.import_btn.setEnabled(False)
            return

        # Show errors
        if errors:
            self.validation_text.setTextColor(Qt.GlobalColor.red)
            for err in errors:
                self.validation_text.append(err)
            self.import_btn.setEnabled(False)
        else:
            self.validation_text.setTextColor(Qt.GlobalColor.darkGreen)
            self.validation_text.setText(f"Validation passed. {len(rows)} preview rows loaded.")
            self.import_btn.setEnabled(True)

        # Show warnings
        for row in rows:
            if row.warnings:
                self.validation_text.setTextColor(Qt.GlobalColor.darkYellow)
                for warn in row.warnings:
                    self.validation_text.append(f"Warning: {warn}")

        # Populate preview table
        if rows:
            headers = self._importer.get_required_headers()
            self.preview_table.setColumnCount(len(headers))
            self.preview_table.setHorizontalHeaderLabels(headers)
            self.preview_table.setRowCount(len(rows))

            for i, row in enumerate(rows):
                values = [
                    row.brand,
                    row.supplier,
                    row.part_number,
                    row.description,
                    row.ean,
                    row.mpn,
                    row.asin,
                    str(row.cost_ex_vat_1),
                    str(row.cost_ex_vat_5plus),
                    str(row.pack_qty),
                ]
                for j, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.preview_table.setItem(i, j, item)

    def _on_import(self) -> None:
        """Execute the import."""
        if not self._current_file:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.import_btn.setEnabled(False)

        try:
            items, result = self._importer.import_file(self._current_file)

            self.progress_bar.setValue(30)

            if not items:
                msg = "No valid items to import."
                if result.errors:
                    msg += "\n\nErrors:\n" + "\n".join(result.errors)
                QMessageBox.warning(self, "Import Failed", msg)
                self.progress_bar.setVisible(False)
                self.import_btn.setEnabled(True)
                return

            # Save to database
            saved_items = self._repo.save_supplier_items_batch(items)
            self.progress_bar.setValue(60)

            # Create ASIN candidates from CSV hints
            candidates_from_csv = 0
            items_without_asin = []
            for item in saved_items:
                if item.asin_hint and item.id:
                    # Check for existing candidate
                    existing = self._repo.get_candidate_by_asin(item.id, item.asin_hint)
                    if not existing:
                        candidate = AsinCandidate(
                            supplier_item_id=item.id,
                            brand=item.brand,
                            supplier=item.supplier,
                            part_number=item.part_number,
                            asin=item.asin_hint,
                            match_reason="Provided in CSV",
                            confidence_score=__import__("decimal").Decimal("0.99"),
                            source=CandidateSource.MANUAL_CSV,
                            is_active=True,
                            is_primary=True,
                        )
                        self._repo.save_asin_candidate(candidate)
                        candidates_from_csv += 1
                else:
                    # Track items that need ASIN search
                    items_without_asin.append(item)

            self.progress_bar.setValue(100)

            # Log the import
            log_msg = (
                f"Import completed: {result.batch_id}\n"
                f"  File: {Path(self._current_file).name}\n"
                f"  Items imported: {result.items_imported}\n"
                f"  Items skipped: {result.items_skipped}\n"
                f"  ASIN candidates from CSV: {candidates_from_csv}\n"
                f"  Items needing ASIN search: {len(items_without_asin)}\n"
            )

            if result.warnings:
                log_msg += f"  Warnings: {len(result.warnings)}\n"

            self.history_text.append(log_msg)
            logger.info(log_msg)

            # Emit import completed signal
            self.import_completed.emit(result.batch_id)

            # Auto-search for ASINs if enabled and there are items without ASINs
            if self.auto_search_checkbox.isChecked() and items_without_asin:
                self.history_text.append(
                    f"\nStarting auto-ASIN search for {len(items_without_asin)} items...\n"
                )
                self._start_asin_search(items_without_asin)
            else:
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {result.items_imported} items.\n"
                    f"Created {candidates_from_csv} ASIN candidate mappings from CSV.",
                )
                self.progress_bar.setVisible(False)
                self.import_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Import failed: {e}")
            logger.exception("Import failed")
            self.progress_bar.setVisible(False)
            self.import_btn.setEnabled(True)

    def _start_asin_search(self, items: list[SupplierItem]) -> None:
        """Start the background ASIN search."""
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(items))
        self.progress_label.setVisible(True)
        self.progress_label.setText("Starting ASIN search...")
        self.cancel_btn.setVisible(True)

        self._search_worker = AsinSearchWorker(items, self)
        self._search_worker.progress.connect(self._on_search_progress)
        self._search_worker.item_found.connect(self._on_item_found)
        self._search_worker.finished_signal.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_progress(self, current: int, total: int, message: str) -> None:
        """Handle search progress updates."""
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"{current}/{total}: {message}")
        QApplication.processEvents()

    def _on_item_found(self, supplier_item_id: int, candidates_found: int) -> None:
        """Handle when ASINs are found for an item."""
        self.history_text.append(f"  Found {candidates_found} ASINs for item #{supplier_item_id}")

    def _on_search_finished(self, items_with_matches: int, total_candidates: int) -> None:
        """Handle search completion."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.import_btn.setEnabled(True)

        log_msg = (
            f"\nASIN search completed:\n"
            f"  Items with matches: {items_with_matches}\n"
            f"  Total ASIN candidates found: {total_candidates}\n"
        )
        self.history_text.append(log_msg)
        logger.info(log_msg)

        QMessageBox.information(
            self,
            "ASIN Search Complete",
            f"Found {total_candidates} ASIN candidates for {items_with_matches} items.",
        )

        self._search_worker = None

    def _on_search_error(self, error_msg: str) -> None:
        """Handle search error."""
        self.history_text.append(f"  Error: {error_msg}")
        logger.error(f"ASIN search error: {error_msg}")

    def _on_cancel_search(self) -> None:
        """Cancel the running ASIN search."""
        if self._search_worker:
            self._search_worker.cancel()
            self.history_text.append("\nASIN search cancelled by user.\n")
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.import_btn.setEnabled(True)
