"""Export functionality for Seller Opportunity Scanner."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.models import ScoreResult


class Exporter:
    """Exports data to various formats."""

    @staticmethod
    def score_results_to_dict(results: list[ScoreResult]) -> list[dict[str, Any]]:
        """Convert score results to dictionaries for export."""
        rows = []
        for r in results:
            winning = r.scenario_cost_1 if r.winning_scenario == "cost_1" else r.scenario_cost_5plus
            other = r.scenario_cost_5plus if r.winning_scenario == "cost_1" else r.scenario_cost_1

            row = {
                "Score": r.score,
                "Winning Scenario": r.winning_scenario,
                "Brand": r.brand.value,
                "Supplier": r.supplier,
                "Part Number": r.part_number,
                "ASIN": r.asin,
                "Sales Proxy 30d": r.sales_proxy_30d,
                "Offer Count": r.offer_count,
                "Amazon Present": "Yes" if r.amazon_present else "No",
                "Restricted": "Yes" if r.is_restricted else "No",
                "Mapping Confidence": float(r.mapping_confidence),
                "Weight (kg)": float(r.weight_kg) if r.weight_kg else "",
                # Winning scenario
                "Cost ExVAT": float(winning.cost_ex_vat),
                "Sell Gross Safe": float(winning.sell_gross_safe),
                "Sell Net": float(winning.sell_net),
                "Fees Gross": float(winning.fees_gross),
                "Fees Net": float(winning.fees_net),
                "Shipping Cost": float(winning.shipping_cost),
                "Profit Net": float(winning.profit_net),
                "Margin Net": float(winning.margin_net),
                # Other scenario
                "Alt Cost ExVAT": float(other.cost_ex_vat),
                "Alt Profit Net": float(other.profit_net),
                "Alt Margin Net": float(other.margin_net),
                # Score breakdown
                "Velocity Score": float(r.breakdown.velocity_raw),
                "Profit Score": float(r.breakdown.profit_raw),
                "Margin Score": float(r.breakdown.margin_raw),
                "Stability Score": float(r.breakdown.stability_raw),
                "Viability Score": float(r.breakdown.viability_raw),
                "Total Penalties": float(r.breakdown.total_penalties),
                # Flags
                "Flags": ", ".join(f.code for f in r.flags),
                "Flag Details": "; ".join(f"{f.code}: {f.description}" for f in r.flags),
                # Timestamps
                "Calculated At": r.calculated_at.isoformat() if r.calculated_at else "",
                "Keepa Data Time": r.keepa_data_time.isoformat() if r.keepa_data_time else "",
                "SPAPI Data Time": r.spapi_data_time.isoformat() if r.spapi_data_time else "",
            }
            rows.append(row)

        return rows

    @classmethod
    def export_to_csv(
        cls,
        results: list[ScoreResult],
        file_path: str | Path,
    ) -> None:
        """Export score results to CSV."""
        rows = cls.score_results_to_dict(results)

        if not rows:
            return

        path = Path(file_path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    @classmethod
    def export_to_xlsx(
        cls,
        results: list[ScoreResult],
        file_path: str | Path,
    ) -> None:
        """Export score results to Excel."""
        rows = cls.score_results_to_dict(results)

        if not rows:
            return

        df = pd.DataFrame(rows)

        # Format columns
        path = Path(file_path)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Opportunities")

            # Auto-adjust column widths
            worksheet = writer.sheets["Opportunities"]
            for i, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + i) if i < 26 else f"A{chr(65 + i - 26)}"].width = min(max_length + 2, 50)

    @classmethod
    def generate_filename(cls, brand: str, extension: str) -> str:
        """Generate a timestamped filename for export."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"opportunities_{brand.lower()}_{timestamp}.{extension}"
