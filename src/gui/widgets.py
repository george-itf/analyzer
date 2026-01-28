"""Custom widgets for Seller Opportunity Scanner."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)


class ScoreRingWidget(QWidget):
    """Widget displaying a score as a circular ring with color gradient."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score = 0
        self._size = 60
        self.setMinimumSize(self._size, self._size)
        self.setMaximumSize(self._size, self._size)

    @property
    def score(self) -> int:
        return self._score

    @score.setter
    def score(self, value: int) -> None:
        self._score = max(0, min(100, value))
        self.update()

    def get_score_color(self, score: int) -> QColor:
        """Get the color for a given score value."""
        if score < 50:
            # Red spectrum (0-49)
            # Interpolate from dark red to orange-red
            ratio = score / 49
            r = int(180 + (220 - 180) * ratio)
            g = int(30 + (100 - 30) * ratio)
            b = int(30 + (30 - 30) * ratio)
        elif score < 80:
            # Orange spectrum (50-79)
            # Interpolate from orange to yellow-green
            ratio = (score - 50) / 29
            r = int(230 + (180 - 230) * ratio)
            g = int(126 + (200 - 126) * ratio)
            b = int(34 + (50 - 34) * ratio)
        else:
            # Green spectrum (80-100)
            # Interpolate from green to bright green
            ratio = (score - 80) / 20
            r = int(100 + (40 - 100) * ratio)
            g = int(180 + (220 - 180) * ratio)
            b = int(80 + (80 - 80) * ratio)

        return QColor(r, g, b)

    def paintEvent(self, event) -> None:
        """Paint the score ring."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        width = self.width()
        height = self.height()
        size = min(width, height) - 4
        x = (width - size) // 2
        y = (height - size) // 2
        rect = QRect(x, y, size, size)

        # Ring thickness
        ring_width = 6

        # Background ring (gray)
        pen = QPen(QColor(220, 220, 220))
        pen.setWidth(ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Score arc
        if self._score > 0:
            color = self.get_score_color(self._score)
            pen = QPen(color)
            pen.setWidth(ring_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            # Arc spans from top (90 degrees) counterclockwise
            span_angle = int(self._score / 100 * 360 * 16)
            start_angle = 90 * 16  # Start at top
            painter.drawArc(rect, start_angle, -span_angle)  # Negative for clockwise

        # Draw score text in center
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(60, 60, 60)))

        text_rect = QRect(x, y, size, size)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self._score))


class ScoreRingDelegate(QStyledItemDelegate):
    """Delegate for rendering score rings in table views."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ring_size = 50

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Paint the score ring in the cell."""
        # Get score value
        score = index.data(Qt.ItemDataRole.DisplayRole)
        if score is None:
            super().paint(painter, option, index)
            return

        try:
            score = int(score)
        except (ValueError, TypeError):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Cell rect
        rect = option.rect

        # Draw selection highlight if selected
        if option.state & option.State_Selected:
            painter.fillRect(rect, option.palette.highlight())

        # Calculate ring dimensions
        size = min(rect.width(), rect.height()) - 8
        size = min(size, self._ring_size)
        x = rect.x() + (rect.width() - size) // 2
        y = rect.y() + (rect.height() - size) // 2
        ring_rect = QRect(x, y, size, size)

        # Ring properties
        ring_width = 5

        # Draw background ring
        pen = QPen(QColor(220, 220, 220))
        pen.setWidth(ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(ring_rect, 0, 360 * 16)

        # Draw score arc
        if score > 0:
            color = self._get_score_color(score)
            pen = QPen(color)
            pen.setWidth(ring_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            span_angle = int(score / 100 * 360 * 16)
            start_angle = 90 * 16
            painter.drawArc(ring_rect, start_angle, -span_angle)

        # Draw score text
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)

        if option.state & option.State_Selected:
            painter.setPen(QPen(option.palette.highlightedText().color()))
        else:
            painter.setPen(QPen(QColor(60, 60, 60)))

        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, str(score))

        painter.restore()

    def _get_score_color(self, score: int) -> QColor:
        """Get the color for a given score value."""
        if score < 50:
            ratio = score / 49
            r = int(180 + (220 - 180) * ratio)
            g = int(30 + (100 - 30) * ratio)
            b = 30
        elif score < 80:
            ratio = (score - 50) / 29
            r = int(230 + (180 - 230) * ratio)
            g = int(126 + (200 - 126) * ratio)
            b = int(34 + (50 - 34) * ratio)
        else:
            ratio = (score - 80) / 20
            r = int(100 + (40 - 100) * ratio)
            g = int(180 + (220 - 180) * ratio)
            b = 80

        return QColor(r, g, b)

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        """Return the preferred size for the score ring cell."""
        return QSize(self._ring_size + 10, self._ring_size + 10)


class TokenStatusWidget(QWidget):
    """Widget displaying Keepa token status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens_left = 0
        self._refill_rate = 20
        self._refill_in = 60
        self.setMinimumWidth(200)
        self.setMaximumHeight(30)

    def update_status(
        self,
        tokens_left: int,
        refill_rate: int,
        refill_in: int,
    ) -> None:
        """Update the token status."""
        self._tokens_left = tokens_left
        self._refill_rate = refill_rate
        self._refill_in = refill_in
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the token status."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(245, 245, 245))

        # Draw token bar
        bar_height = 8
        bar_y = (self.height() - bar_height) // 2 + 8
        bar_width = self.width() - 20
        bar_x = 10

        # Background bar
        painter.fillRect(bar_x, bar_y, bar_width, bar_height, QColor(220, 220, 220))

        # Token fill (assuming max ~500 tokens)
        fill_ratio = min(self._tokens_left / 500, 1.0)
        fill_width = int(bar_width * fill_ratio)

        # Color based on token level
        if fill_ratio > 0.5:
            fill_color = QColor(100, 180, 100)
        elif fill_ratio > 0.2:
            fill_color = QColor(220, 180, 50)
        else:
            fill_color = QColor(200, 80, 80)

        painter.fillRect(bar_x, bar_y, fill_width, bar_height, fill_color)

        # Draw text
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QPen(QColor(60, 60, 60)))

        text = f"Tokens: {self._tokens_left} | Rate: {self._refill_rate}/min | Refill: {self._refill_in}s"
        painter.drawText(
            bar_x,
            bar_y - 4,
            bar_width,
            20,
            Qt.AlignmentFlag.AlignLeft,
            text,
        )


class FlagLabel(QWidget):
    """Widget for displaying a score flag as a colored label."""

    FLAG_COLORS = {
        "RESTRICTED": ("#dc3545", "#ffffff"),
        "AMAZON_RETAIL": ("#fd7e14", "#ffffff"),
        "OVERWEIGHT": ("#dc3545", "#ffffff"),
        "WEIGHT_UNKNOWN": ("#6c757d", "#ffffff"),
        "LOW_CONFIDENCE": ("#ffc107", "#212529"),
        "HIGH_COMPETITION": ("#17a2b8", "#ffffff"),
        "RISING_COMPETITION": ("#17a2b8", "#ffffff"),
        "LOW_SALES": ("#6c757d", "#ffffff"),
        "LOW_MARGIN": ("#ffc107", "#212529"),
        "LOW_PROFIT": ("#ffc107", "#212529"),
    }

    def __init__(self, code: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._code = code
        colors = self.FLAG_COLORS.get(code, ("#6c757d", "#ffffff"))
        self._bg_color = QColor(colors[0])
        self._text_color = QColor(colors[1])
        self.setMinimumHeight(20)

    def paintEvent(self, event) -> None:
        """Paint the flag label."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw rounded rectangle background
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        # Draw text
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(self._text_color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._code)

    def sizeHint(self) -> QSize:
        """Return the preferred size."""
        return QSize(len(self._code) * 8 + 16, 22)
