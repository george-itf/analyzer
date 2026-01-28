"""Tests for core models."""

from decimal import Decimal

import pytest

from src.core.models import Brand, SupplierItem, AsinCandidate, CandidateSource


class TestBrand:
    def test_from_string(self) -> None:
        assert Brand.from_string("Makita") == Brand.MAKITA
        assert Brand.from_string("DeWalt") == Brand.DEWALT
        assert Brand.from_string("Timco") == Brand.TIMCO

    def test_from_string_case_insensitive(self) -> None:
        assert Brand.from_string("makita") == Brand.MAKITA
        assert Brand.from_string("DEWALT") == Brand.DEWALT

    def test_from_string_invalid(self) -> None:
        with pytest.raises(ValueError):
            Brand.from_string("Unknown")

    def test_values(self) -> None:
        values = Brand.values()
        assert "Makita" in values
        assert "DeWalt" in values
        assert "Timco" in values
        assert len(values) == 3


class TestSupplierItem:
    def test_pack_qty_conversion(self) -> None:
        item = SupplierItem(
            cost_ex_vat_1=Decimal("50.00"),
            cost_ex_vat_5plus=Decimal("45.00"),
            pack_qty=10,
        )
        assert item.cost_per_unit_ex_vat_1 == Decimal("5.00")
        assert item.cost_per_unit_ex_vat_5plus == Decimal("4.50")

    def test_single_unit(self) -> None:
        item = SupplierItem(
            cost_ex_vat_1=Decimal("25.00"),
            cost_ex_vat_5plus=Decimal("22.00"),
            pack_qty=1,
        )
        assert item.cost_per_unit_ex_vat_1 == Decimal("25.00")
        assert item.cost_per_unit_ex_vat_5plus == Decimal("22.00")


class TestAsinCandidate:
    def test_default_values(self) -> None:
        c = AsinCandidate()
        assert c.is_active is True
        assert c.is_primary is False
        assert c.is_locked is False
        assert c.confidence_score == Decimal("0.5")

    def test_source_enum(self) -> None:
        assert CandidateSource.MANUAL_CSV.value == "manual_csv"
        assert CandidateSource.SPAPI_EAN.value == "spapi_ean"
        assert CandidateSource.SPAPI_KEYWORD.value == "spapi_keyword"
