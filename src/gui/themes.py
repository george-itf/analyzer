"""Theme management for Seller Opportunity Scanner."""

from __future__ import annotations

# Light theme stylesheet
LIGHT_THEME = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QTabWidget::pane {
        border: 1px solid #ccc;
        background-color: white;
    }
    QTabBar::tab {
        background-color: #e0e0e0;
        border: 1px solid #ccc;
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: white;
        border-bottom-color: white;
    }
    QTabBar::tab:hover {
        background-color: #d0d0d0;
    }
    QTableView {
        gridline-color: #e0e0e0;
        selection-background-color: #cce5ff;
        selection-color: #000000;
        background-color: white;
        alternate-background-color: #f8f9fa;
    }
    QTableView::item {
        padding: 4px;
    }
    QHeaderView::section {
        background-color: #f0f0f0;
        padding: 6px;
        border: 1px solid #ddd;
        font-weight: bold;
    }
    QPushButton {
        background-color: #0d6efd;
        color: white;
        border: none;
        padding: 6px 16px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #0b5ed7;
    }
    QPushButton:pressed {
        background-color: #0a58ca;
    }
    QPushButton:disabled {
        background-color: #6c757d;
    }
    QPushButton:checked {
        background-color: #dc3545;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #ddd;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 16px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        padding: 4px 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
        background-color: white;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QTextEdit {
        background-color: white;
        border: 1px solid #ccc;
    }
    QTreeWidget {
        background-color: white;
        border: 1px solid #ccc;
    }
"""

# Dark theme stylesheet
DARK_THEME = """
    QMainWindow {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QTabWidget::pane {
        border: 1px solid #3c3c3c;
        background-color: #252526;
    }
    QTabBar::tab {
        background-color: #2d2d30;
        border: 1px solid #3c3c3c;
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        color: #e0e0e0;
    }
    QTabBar::tab:selected {
        background-color: #252526;
        border-bottom-color: #252526;
    }
    QTabBar::tab:hover {
        background-color: #3c3c3c;
    }
    QTableView {
        gridline-color: #3c3c3c;
        selection-background-color: #264f78;
        selection-color: #ffffff;
        background-color: #1e1e1e;
        alternate-background-color: #252526;
        color: #e0e0e0;
    }
    QTableView::item {
        padding: 4px;
    }
    QHeaderView::section {
        background-color: #2d2d30;
        padding: 6px;
        border: 1px solid #3c3c3c;
        font-weight: bold;
        color: #e0e0e0;
    }
    QPushButton {
        background-color: #0d6efd;
        color: white;
        border: none;
        padding: 6px 16px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #0b5ed7;
    }
    QPushButton:pressed {
        background-color: #0a58ca;
    }
    QPushButton:disabled {
        background-color: #4a4a4a;
        color: #808080;
    }
    QPushButton:checked {
        background-color: #dc3545;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 16px;
        color: #e0e0e0;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: #e0e0e0;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        padding: 4px 8px;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        background-color: #2d2d30;
        color: #e0e0e0;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    QTextEdit {
        background-color: #1e1e1e;
        border: 1px solid #3c3c3c;
        color: #e0e0e0;
    }
    QTreeWidget {
        background-color: #1e1e1e;
        border: 1px solid #3c3c3c;
        color: #e0e0e0;
    }
    QTreeWidget::item:selected {
        background-color: #264f78;
    }
    QLabel {
        color: #e0e0e0;
    }
    QCheckBox {
        color: #e0e0e0;
    }
    QCheckBox::indicator {
        border: 1px solid #3c3c3c;
        background-color: #2d2d30;
    }
    QCheckBox::indicator:checked {
        background-color: #0d6efd;
    }
    QFrame {
        background-color: #252526;
        border-color: #3c3c3c;
    }
    StatCard, BrandSummaryWidget, TopMoversWidget {
        background-color: #252526;
        border: 1px solid #3c3c3c;
    }
"""


def get_theme_stylesheet(dark_mode: bool = False) -> str:
    """Get the stylesheet for the specified theme."""
    return DARK_THEME if dark_mode else LIGHT_THEME
