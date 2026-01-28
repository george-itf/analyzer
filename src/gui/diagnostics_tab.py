"""Diagnostics tab widget for Seller Opportunity Scanner."""

from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.db.repository import Repository


class DiagnosticsTab(QWidget):
    """Tab widget for diagnostics and API logs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = Repository()
        self._build_ui()

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)
        self._refresh_timer.start(10000)  # Refresh every 10 seconds

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Token usage stats
        stats_group = QGroupBox("Token Usage (Last 24h)")
        stats_layout = QHBoxLayout(stats_group)

        self.stats_label = QLabel("Loading...")
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_group)

        # Database stats
        db_group = QGroupBox("Database Statistics")
        db_layout = QHBoxLayout(db_group)

        self.db_stats_label = QLabel("Loading...")
        db_layout.addWidget(self.db_stats_label)

        layout.addWidget(db_group)

        # API Logs
        logs_group = QGroupBox("API Call Log")
        logs_layout = QVBoxLayout(logs_group)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("API:"))
        self.api_filter = QComboBox()
        self.api_filter.addItems(["All", "keepa", "spapi"])
        self.api_filter.currentTextChanged.connect(self.refresh_logs)
        filter_layout.addWidget(self.api_filter)

        filter_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(refresh_btn)

        logs_layout.addLayout(filter_layout)

        # Logs table
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(8)
        self.logs_table.setHorizontalHeaderLabels([
            "Time", "API", "Endpoint", "Status", "Tokens", "Duration (ms)", "Success", "Error",
        ])
        self.logs_table.setAlternatingRowColors(True)
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        self.logs_table.verticalHeader().setVisible(False)
        self.logs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        logs_layout.addWidget(self.logs_table)

        layout.addWidget(logs_group)

        # App log
        app_log_group = QGroupBox("Application Log")
        app_log_layout = QVBoxLayout(app_log_group)

        self.app_log_text = QTextEdit()
        self.app_log_text.setReadOnly(True)
        self.app_log_text.setMaximumHeight(200)
        app_log_layout.addWidget(self.app_log_text)

        layout.addWidget(app_log_group)

    def refresh_data(self) -> None:
        """Refresh all diagnostics data."""
        self._refresh_stats()
        self._refresh_db_stats()
        self.refresh_logs()

    def _refresh_stats(self) -> None:
        """Refresh token usage statistics."""
        try:
            stats = self._repo.get_token_usage_stats(hours=24)
            self.stats_label.setText(
                f"Total Tokens: {stats['total_tokens']} | "
                f"API Calls: {stats['total_calls']} | "
                f"Success: {stats['success_count']} | "
                f"Failed: {stats['failure_count']}"
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.stats_label.setText(f"Error loading stats: {type(e).__name__}: {e}")

    def _refresh_db_stats(self) -> None:
        """Refresh database statistics."""
        try:
            item_counts = self._repo.get_item_counts_by_brand()
            candidate_counts = self._repo.get_candidate_counts_by_brand()

            parts = []
            for brand in ["Makita", "DeWalt", "Timco"]:
                items = item_counts.get(brand, 0)
                candidates = candidate_counts.get(brand, 0)
                parts.append(f"{brand}: {items} items, {candidates} candidates")

            self.db_stats_label.setText(" | ".join(parts))
        except Exception as e:
            self.db_stats_label.setText(f"Error: {e}")

    def refresh_logs(self) -> None:
        """Refresh API logs table."""
        api_filter = self.api_filter.currentText()
        api_name = api_filter if api_filter != "All" else None

        try:
            logs = self._repo.get_api_logs(api_name=api_name, limit=100)
        except Exception:
            logs = []

        self.logs_table.setRowCount(len(logs))

        for i, log in enumerate(logs):
            self.logs_table.setItem(i, 0, QTableWidgetItem(log["created_at"]))
            self.logs_table.setItem(i, 1, QTableWidgetItem(log["api_name"]))
            self.logs_table.setItem(i, 2, QTableWidgetItem(log["endpoint"]))
            self.logs_table.setItem(i, 3, QTableWidgetItem(str(log["response_status"])))
            self.logs_table.setItem(i, 4, QTableWidgetItem(str(log["tokens_consumed"])))
            self.logs_table.setItem(i, 5, QTableWidgetItem(str(log["duration_ms"])))
            self.logs_table.setItem(i, 6, QTableWidgetItem("Yes" if log["success"] else "No"))
            self.logs_table.setItem(i, 7, QTableWidgetItem(log["error_message"]))

    def append_log(self, message: str) -> None:
        """Append a message to the application log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.app_log_text.append(f"[{timestamp}] {message}")
