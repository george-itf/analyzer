"""Tests for CSV importer."""

from pathlib import Path

import pytest

from src.core.csv_importer import CsvImporter, CsvValidationError
from src.core.models import Brand


class TestCsvValidation:
    """Tests for CSV header validation."""

    def test_valid_headers(self) -> None:
        importer = CsvImporter()
        headers = [
            "Brand", "Supplier", "PartNumber", "Description",
            "EAN", "MPN", "ASIN", "CostExVAT_1", "CostExVAT_5Plus", "PackQty",
        ]
        importer.validate_headers(headers)  # Should not raise

    def test_missing_headers(self) -> None:
        importer = CsvImporter()
        headers = ["Brand", "Supplier"]
        with pytest.raises(CsvValidationError) as exc_info:
            importer.validate_headers(headers)
        assert "PartNumber" in str(exc_info.value)
        assert len(exc_info.value.missing_headers) > 0

    def test_empty_headers(self) -> None:
        importer = CsvImporter()
        with pytest.raises(CsvValidationError):
            importer.validate_headers([])

    def test_headers_with_whitespace(self) -> None:
        importer = CsvImporter()
        headers = [
            " Brand ", " Supplier ", "PartNumber", "Description",
            "EAN", "MPN", "ASIN", "CostExVAT_1", "CostExVAT_5Plus", "PackQty",
        ]
        importer.validate_headers(headers)  # Should handle whitespace


class TestCsvImport:
    """Tests for CSV file import."""

    def test_successful_import(self, sample_csv_path: Path) -> None:
        importer = CsvImporter()
        items, result = importer.import_file(sample_csv_path)

        assert result.items_imported == 3
        assert result.items_skipped == 0
        assert len(items) == 3
        assert items[0].brand == Brand.MAKITA
        assert items[0].part_number == "DHP482Z"
        assert items[0].asin_hint == "B07RBJYQQN"

    def test_invalid_headers_import(self, invalid_csv_path: Path) -> None:
        importer = CsvImporter()
        items, result = importer.import_file(invalid_csv_path)

        assert result.items_imported == 0
        assert len(result.errors) > 0

    def test_file_not_found(self) -> None:
        importer = CsvImporter()
        with pytest.raises(FileNotFoundError):
            importer.import_file("/nonexistent/file.csv")

    def test_preview(self, sample_csv_path: Path) -> None:
        importer = CsvImporter()
        rows, errors = importer.preview(sample_csv_path, max_rows=2)

        assert len(rows) == 2
        assert len(errors) == 0
        assert rows[0].brand == "Makita"

    def test_invalid_brand(self, tmp_path: Path) -> None:
        csv_content = (
            "Brand,Supplier,PartNumber,Description,EAN,MPN,ASIN,CostExVAT_1,CostExVAT_5Plus,PackQty\n"
            "InvalidBrand,Supplier,PN1,Desc,,,,10.00,9.00,1\n"
        )
        csv_file = tmp_path / "invalid_brand.csv"
        csv_file.write_text(csv_content)

        importer = CsvImporter()
        items, result = importer.import_file(csv_file)

        assert result.items_imported == 0
        assert result.items_skipped == 1

    def test_pack_qty_conversion(self, tmp_path: Path) -> None:
        csv_content = (
            "Brand,Supplier,PartNumber,Description,EAN,MPN,ASIN,CostExVAT_1,CostExVAT_5Plus,PackQty\n"
            "Timco,Timco Supply,BOLT-10,Coach Bolt Pack,,,,50.00,45.00,10\n"
        )
        csv_file = tmp_path / "pack.csv"
        csv_file.write_text(csv_content)

        importer = CsvImporter()
        items, result = importer.import_file(csv_file)

        assert len(items) == 1
        assert items[0].pack_qty == 10
        assert items[0].cost_per_unit_ex_vat_1 == items[0].cost_ex_vat_1 / 10
