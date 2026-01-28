"""Chart widgets for dashboard visualizations."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QSizePolicy, QWidget


class BarChartWidget(QFrame):
    """Simple horizontal bar chart widget."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self._data: list[tuple[str, float, QColor]] = []  # (label, value, color)
        self._max_value: float = 100

        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            BarChartWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def set_data(self, data: list[tuple[str, float, QColor | str]]) -> None:
        """Set chart data. Each item is (label, value, color)."""
        self._data = []
        for label, value, color in data:
            if isinstance(color, str):
                color = QColor(color)
            self._data.append((label, value, color))

        if self._data:
            self._max_value = max(v for _, v, _ in self._data) or 1

        self.update()

    def paintEvent(self, event) -> None:
        """Paint the bar chart."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        padding = 16
        bar_height = 24
        bar_spacing = 8
        label_width = 80

        # Draw title
        if self.title:
            painter.setFont(QFont("", 12, QFont.Weight.Bold))
            painter.setPen(QColor("#212529"))
            painter.drawText(
                padding, padding + 12,
                self.title
            )
            y_start = padding + 30
        else:
            y_start = padding

        # Draw bars
        painter.setFont(QFont("", 10))

        for i, (label, value, color) in enumerate(self._data):
            y = y_start + i * (bar_height + bar_spacing)

            # Label
            painter.setPen(QColor("#495057"))
            painter.drawText(
                padding, y + bar_height - 6,
                label[:12]
            )

            # Bar background
            bar_x = padding + label_width
            bar_width = rect.width() - bar_x - padding - 50  # Leave room for value text

            painter.setBrush(QColor("#e9ecef"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(bar_x), int(y), int(bar_width), int(bar_height), 4, 4
            )

            # Bar fill
            fill_width = (value / self._max_value) * bar_width if self._max_value > 0 else 0
            painter.setBrush(color)
            painter.drawRoundedRect(
                int(bar_x), int(y), int(fill_width), int(bar_height), 4, 4
            )

            # Value text
            painter.setPen(QColor("#212529"))
            painter.drawText(
                int(bar_x + bar_width + 8), int(y + bar_height - 6),
                f"{value:.0f}"
            )

        painter.end()


class DonutChartWidget(QFrame):
    """Simple donut/pie chart widget."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self._data: list[tuple[str, float, QColor]] = []  # (label, value, color)
        self._total: float = 0

        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            DonutChartWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def set_data(self, data: list[tuple[str, float, QColor | str]]) -> None:
        """Set chart data. Each item is (label, value, color)."""
        self._data = []
        for label, value, color in data:
            if isinstance(color, str):
                color = QColor(color)
            self._data.append((label, value, color))

        self._total = sum(v for _, v, _ in self._data) or 1
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the donut chart."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        padding = 16

        # Draw title
        if self.title:
            painter.setFont(QFont("", 12, QFont.Weight.Bold))
            painter.setPen(QColor("#212529"))
            painter.drawText(padding, padding + 12, self.title)
            y_offset = 30
        else:
            y_offset = 0

        # Calculate donut dimensions
        chart_size = min(rect.width(), rect.height() - y_offset - padding * 2) - 60
        chart_x = (rect.width() - chart_size) // 2
        chart_y = y_offset + padding + 10
        chart_rect = QRectF(chart_x, chart_y, chart_size, chart_size)

        # Draw donut segments
        start_angle = 90 * 16  # Start from top (Qt uses 1/16 degrees)

        for label, value, color in self._data:
            span_angle = int((value / self._total) * 360 * 16)

            painter.setBrush(color)
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawPie(chart_rect, start_angle, span_angle)

            start_angle += span_angle

        # Draw center hole (donut effect)
        hole_size = chart_size * 0.5
        hole_x = chart_x + (chart_size - hole_size) / 2
        hole_y = chart_y + (chart_size - hole_size) / 2

        painter.setBrush(QColor("white"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(hole_x, hole_y, hole_size, hole_size))

        # Draw total in center
        painter.setFont(QFont("", 16, QFont.Weight.Bold))
        painter.setPen(QColor("#212529"))
        total_text = f"{self._total:.0f}"
        text_rect = QRectF(hole_x, hole_y, hole_size, hole_size)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, total_text)

        # Draw legend below
        legend_y = chart_y + chart_size + 15
        legend_x = padding
        box_size = 12

        painter.setFont(QFont("", 9))

        for label, value, color in self._data:
            # Color box
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(legend_x), int(legend_y), box_size, box_size)

            # Label
            painter.setPen(QColor("#495057"))
            pct = (value / self._total) * 100 if self._total > 0 else 0
            painter.drawText(
                int(legend_x + box_size + 4), int(legend_y + 10),
                f"{label}: {value:.0f} ({pct:.0f}%)"
            )

            legend_x += 120  # Move to next legend item
            if legend_x > rect.width() - 100:
                legend_x = padding
                legend_y += 18

        painter.end()


class ScoreDistributionWidget(QFrame):
    """Widget showing score distribution as a histogram."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scores: list[int] = []
        self._buckets: list[int] = [0] * 5  # 0-20, 20-40, 40-60, 60-80, 80-100

        self.setMinimumSize(250, 120)
        self.setStyleSheet("""
            ScoreDistributionWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def set_scores(self, scores: list[int]) -> None:
        """Set the scores to display."""
        self._scores = scores
        self._buckets = [0] * 5

        for score in scores:
            bucket = min(score // 20, 4)  # 0-4
            self._buckets[bucket] += 1

        self.update()

    def paintEvent(self, event) -> None:
        """Paint the histogram."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        padding = 16

        # Title
        painter.setFont(QFont("", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#212529"))
        painter.drawText(padding, padding + 12, "Score Distribution")

        # Histogram bars
        bar_area_y = padding + 30
        bar_area_height = rect.height() - bar_area_y - 30
        bar_width = (rect.width() - padding * 2) // 5 - 4

        max_count = max(self._buckets) or 1
        colors = [
            QColor("#dc3545"),  # 0-20: Red
            QColor("#fd7e14"),  # 20-40: Orange
            QColor("#ffc107"),  # 40-60: Yellow
            QColor("#28a745"),  # 60-80: Green
            QColor("#20c997"),  # 80-100: Teal
        ]
        labels = ["0-20", "20-40", "40-60", "60-80", "80-100"]

        painter.setFont(QFont("", 9))

        for i, (count, color, label) in enumerate(zip(self._buckets, colors, labels)):
            x = padding + i * (bar_width + 4)
            bar_height = (count / max_count) * bar_area_height if max_count > 0 else 0
            y = bar_area_y + bar_area_height - bar_height

            # Bar
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 3, 3)

            # Count above bar
            if count > 0:
                painter.setPen(QColor("#212529"))
                painter.drawText(
                    int(x + bar_width // 2 - 8), int(y - 4),
                    str(count)
                )

            # Label below
            painter.setPen(QColor("#6c757d"))
            painter.drawText(
                int(x + 2), int(bar_area_y + bar_area_height + 14),
                label
            )

        painter.end()
