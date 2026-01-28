"""CSV import functionality for Seller Opportunity Scanner."""

from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, TextIO

from .models import Brand, ImportResult, SupplierItem


class CsvValidationError(Exception):
    """Raised when CSV validation fails."""

    def __init__(self, message: str, missing_headers: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_headers = missing_headers or []


@dataclass
class CsvRow:
    """Parsed CSV row."""

    row_number: int
    brand: str
    supplier: str
    part_number: str
    description: str
    ean: str
    mpn: str
    asin: str
    cost_ex_vat_1: Decimal
    cost_ex_vat_5plus: Decimal
    pack_qty: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class CsvImporter:
    """Imports supplier CSV files with strict schema validation."""

    REQUIRED_HEADERS = [
        "Brand",
        "Supplier",
        "PartNumber",
        "Description",
        "EAN",
        "MPN",
        "ASIN",
        "CostExVAT_1",
        "CostExVAT_5Plus",
        "PackQty",
    ]

    VALID_BRANDS = Brand.values()

    def __init__(self) -> None:
        """Initialize the importer."""
        self.batch_id = ""
        self.import_time = datetime.now()

    def validate_headers(self, headers: list[str]) -> None:
        """Validate that all required headers are present."""
        # Strip whitespace and check
        cleaned_headers = [h.strip() for h in headers]
        missing = [h for h in self.REQUIRED_HEADERS if h not in cleaned_headers]

        if missing:
            raise CsvValidationError(
                f"Missing required columns: {', '.join(missing)}. "
                f"Required columns are: {', '.join(self.REQUIRED_HEADERS)}",
                missing_headers=missing,
            )

    def parse_decimal(self, value: str, row_num: int, field_name: str) -> tuple[Decimal, str | None]:
        """Parse a decimal value, returning the value and any error."""
        if not value or value.strip() == "":
            return Decimal("0"), f"Row {row_num}: {field_name} is empty, using 0"

        try:
            # Remove currency symbols and whitespace
            cleaned = value.strip().replace("£", "").replace(",", "").replace(" ", "")
            return Decimal(cleaned), None
        except InvalidOperation:
            return Decimal("0"), f"Row {row_num}: Invalid {field_name} value '{value}', using 0"

    def parse_int(self, value: str, row_num: int, field_name: str, default: int = 1) -> tuple[int, str | None]:
        """Parse an integer value, returning the value and any error."""
        if not value or value.strip() == "":
            return default, None

        try:
            return int(value.strip()), None
        except ValueError:
            return default, f"Row {row_num}: Invalid {field_name} value '{value}', using {default}"

    def parse_row(self, row: dict[str, str], row_number: int) -> CsvRow:
        """Parse a single CSV row."""
        errors: list[str] = []
        warnings: list[str] = []

        # Get string fields with defaults
        brand = row.get("Brand", "").strip()
        supplier = row.get("Supplier", "").strip()
        part_number = row.get("PartNumber", "").strip()
        description = row.get("Description", "").strip()
        ean = row.get("EAN", "").strip()
        mpn = row.get("MPN", "").strip()
        asin = row.get("ASIN", "").strip()

        # Validate brand
        if not brand:
            errors.append(f"Row {row_number}: Brand is required")
        elif brand not in self.VALID_BRANDS:
            errors.append(
                f"Row {row_number}: Invalid brand '{brand}'. "
                f"Must be one of: {', '.join(self.VALID_BRANDS)}"
            )

        # Validate required fields
        if not supplier:
            errors.append(f"Row {row_number}: Supplier is required")
        if not part_number:
            errors.append(f"Row {row_number}: PartNumber is required")

        # Parse decimal costs
        cost_1, err = self.parse_decimal(row.get("CostExVAT_1", ""), row_number, "CostExVAT_1")
        if err:
            warnings.append(err)

        cost_5plus, err = self.parse_decimal(
            row.get("CostExVAT_5Plus", ""), row_number, "CostExVAT_5Plus"
        )
        if err:
            warnings.append(err)

        # Parse pack quantity
        pack_qty, err = self.parse_int(row.get("PackQty", ""), row_number, "PackQty", default=1)
        if err:
            warnings.append(err)
        if pack_qty < 1:
            pack_qty = 1
            warnings.append(f"Row {row_number}: PackQty must be >= 1, using 1")

        return CsvRow(
            row_number=row_number,
            brand=brand,
            supplier=supplier,
            part_number=part_number,
            description=description,
            ean=ean,
            mpn=mpn,
            asin=asin,
            cost_ex_vat_1=cost_1,
            cost_ex_vat_5plus=cost_5plus,
            pack_qty=pack_qty,
            errors=errors,
            warnings=warnings,
        )

    def preview(self, file_path: str | Path, max_rows: int = 10) -> tuple[list[CsvRow], list[str]]:
        """Preview the first N rows of a CSV file.

        Returns tuple of (rows, validation_errors).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        rows: list[CsvRow] = []
        validation_errors: list[str] = []

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                raise CsvValidationError("CSV file is empty or has no headers")

            try:
                self.validate_headers(list(reader.fieldnames))
            except CsvValidationError as e:
                validation_errors.append(str(e))
                return rows, validation_errors

            for i, row in enumerate(reader, start=2):  # Start at 2 (1-indexed, after header)
                if i > max_rows + 1:
                    break
                parsed = self.parse_row(row, i)
                rows.append(parsed)
                validation_errors.extend(parsed.errors)

        return rows, validation_errors

    def import_file(self, file_path: str | Path) -> tuple[list[SupplierItem], ImportResult]:
        """Import a CSV file and return SupplierItem objects.

        Returns tuple of (items, import_result).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        self.batch_id = str(uuid.uuid4())[:8]
        self.import_time = datetime.now()

        items: list[SupplierItem] = []
        result = ImportResult(batch_id=self.batch_id)
        all_errors: list[str] = []
        all_warnings: list[str] = []

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                result.errors.append("CSV file is empty or has no headers")
                return items, result

            try:
                self.validate_headers(list(reader.fieldnames))
            except CsvValidationError as e:
                result.errors.append(str(e))
                return items, result

            for row_num, row in enumerate(reader, start=2):
                parsed = self.parse_row(row, row_num)

                if parsed.errors:
                    all_errors.extend(parsed.errors)
                    result.items_skipped += 1
                    continue

                all_warnings.extend(parsed.warnings)

                # Create SupplierItem
                try:
                    item = SupplierItem(
                        brand=Brand.from_string(parsed.brand),
                        supplier=parsed.supplier,
                        part_number=parsed.part_number,
                        description=parsed.description,
                        ean=parsed.ean,
                        mpn=parsed.mpn,
                        asin_hint=parsed.asin,
                        cost_ex_vat_1=parsed.cost_ex_vat_1,
                        cost_ex_vat_5plus=parsed.cost_ex_vat_5plus,
                        pack_qty=parsed.pack_qty,
                        import_date=self.import_time,
                        import_batch_id=self.batch_id,
                        is_active=True,
                    )
                    items.append(item)
                    result.items_imported += 1
                except ValueError as e:
                    all_errors.append(f"Row {row_num}: {e}")
                    result.items_skipped += 1

        result.errors = all_errors
        result.warnings = all_warnings
        result.success = len(all_errors) == 0

        return items, result

    def get_required_headers(self) -> list[str]:
        """Return the list of required headers."""
        return self.REQUIRED_HEADERS.copy()
