"""Tests for chart widgets."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor

from src.gui.charts import (
    BarChartWidget,
    DonutChartWidget,
    ScoreDistributionWidget,
)


class TestBarChartWidget:
    """Tests for BarChartWidget."""

    def test_creation(self, qtbot):
        """Test widget can be created."""
        widget = BarChartWidget("Test Chart")
        qtbot.addWidget(widget)

        assert widget.title == "Test Chart"

    def test_set_data(self, qtbot):
        """Test setting chart data."""
        widget = BarChartWidget()
        qtbot.addWidget(widget)

        data = [
            ("Item 1", 50, "#ff0000"),
            ("Item 2", 75, QColor("#00ff00")),
            ("Item 3", 25, "#0000ff"),
        ]
        widget.set_data(data)

        assert len(widget._data) == 3
        assert widget._max_value == 75

    def test_empty_data(self, qtbot):
        """Test with empty data."""
        widget = BarChartWidget()
        qtbot.addWidget(widget)

        widget.set_data([])
        assert len(widget._data) == 0


class TestDonutChartWidget:
    """Tests for DonutChartWidget."""

    def test_creation(self, qtbot):
        """Test widget can be created."""
        widget = DonutChartWidget("Test Donut")
        qtbot.addWidget(widget)

        assert widget.title == "Test Donut"

    def test_set_data(self, qtbot):
        """Test setting chart data."""
        widget = DonutChartWidget()
        qtbot.addWidget(widget)

        data = [
            ("Slice 1", 30, "#ff0000"),
            ("Slice 2", 70, "#00ff00"),
        ]
        widget.set_data(data)

        assert len(widget._data) == 2
        assert widget._total == 100

    def test_total_calculation(self, qtbot):
        """Test total is calculated correctly."""
        widget = DonutChartWidget()
        qtbot.addWidget(widget)

        data = [
            ("A", 25, "#ff0000"),
            ("B", 25, "#00ff00"),
            ("C", 50, "#0000ff"),
        ]
        widget.set_data(data)

        assert widget._total == 100


class TestScoreDistributionWidget:
    """Tests for ScoreDistributionWidget."""

    def test_creation(self, qtbot):
        """Test widget can be created."""
        widget = ScoreDistributionWidget()
        qtbot.addWidget(widget)

        assert len(widget._buckets) == 5

    def test_set_scores(self, qtbot):
        """Test setting scores."""
        widget = ScoreDistributionWidget()
        qtbot.addWidget(widget)

        scores = [10, 15, 25, 35, 45, 55, 65, 75, 85, 95]
        widget.set_scores(scores)

        assert sum(widget._buckets) == 10

    def test_bucket_distribution(self, qtbot):
        """Test scores are bucketed correctly."""
        widget = ScoreDistributionWidget()
        qtbot.addWidget(widget)

        # All in 60-80 bucket
        scores = [60, 65, 70, 75, 79]
        widget.set_scores(scores)

        assert widget._buckets[3] == 5  # 60-80 bucket
        assert sum(widget._buckets) == 5

    def test_edge_cases(self, qtbot):
        """Test edge case scores."""
        widget = ScoreDistributionWidget()
        qtbot.addWidget(widget)

        # Test boundary values
        scores = [0, 20, 40, 60, 80, 100]
        widget.set_scores(scores)

        # 0 -> bucket 0, 20 -> bucket 1, etc.
        assert widget._buckets[0] == 1  # 0
        assert widget._buckets[1] == 1  # 20
        assert widget._buckets[2] == 1  # 40
        assert widget._buckets[3] == 1  # 60
        assert widget._buckets[4] == 2  # 80, 100
