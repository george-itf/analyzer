# Seller Opportunity Scanner

A macOS desktop application for scanning Amazon.co.uk seller opportunities from supplier price files using Keepa and Amazon SP-API data.

**Platform:** macOS (Apple Silicon / M-series)
**Marketplace:** Amazon.co.uk only (GBP)

## Quick Start

### 1. Create virtual environment and install

```bash
cd seller-opportunity-scanner
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### 2. Set up credentials

```bash
mkdir -p ~/.seller-opportunity-scanner
cp .env.example ~/.seller-opportunity-scanner/.env
# Edit ~/.seller-opportunity-scanner/.env with your API keys
```

To run without API credentials (mock mode), set `SOS_MOCK_MODE=true` in the `.env` file.

### 3. Run the application

```bash
python -m src.main
```

Or after installation:

```bash
seller-scanner
```

## Importing Supplier CSV Files

Go to the **Imports** tab and click **Browse CSV...**. The CSV must have these exact column headers:

| Column | Type | Notes |
|--------|------|-------|
| Brand | string | Must be: Makita, DeWalt, or Timco |
| Supplier | string | Free text |
| PartNumber | string | Unique within Brand+Supplier |
| Description | string | Can be blank |
| EAN | string | Can be blank, digits only |
| MPN | string | Can be blank |
| ASIN | string | Can be blank; treated as manual mapping |
| CostExVAT_1 | decimal | Cost per unit ex VAT (single unit) |
| CostExVAT_5Plus | decimal | Cost per unit ex VAT (5+ units) |
| PackQty | int | Default 1; costs are per-pack |

A sample file is in `fixtures/sample_import.csv`.

## How Scoring Works

Each (PartNumber, ASIN) pair gets a score from 0-100 composed of:

- **Velocity (45%)**: Based on 30-day sales rank drops from Keepa
- **Profit (20%)**: Based on calculated profit (ex-VAT) at conservative sell price
- **Margin (20%)**: Based on margin percentage (ex-VAT)
- **Stability (10%)**: Based on price volatility and offer count trends
- **FBM Viability (5%)**: Based on FBM vs Buy Box price gap

Penalties are applied for: restrictions, Amazon presence, unknown weight, high competition, below-threshold metrics.

Both cost scenarios (single unit and 5+ units) are computed. The main score uses whichever scenario yields higher profit.

All weights, penalties, and thresholds are configurable per-brand in **Settings**.

## Continuous Refresh and Token Management

The app continuously refreshes Keepa and SP-API data in the background:

- **Pass 1** (wide scan): Refreshes all active ASIN candidates with basic Keepa data
- **Pass 2** (narrow scan): Fetches buy box data for the top N candidates

The scheduler monitors Keepa's token bucket and automatically paces requests to stay within limits. Live token status is shown at the top of the window.

SP-API responses are cached with a configurable TTL (default 60 minutes).

## Building macOS .app Bundle

```bash
source venv/bin/activate
pip install pyinstaller

# Build for Apple Silicon
pyinstaller seller_scanner.spec --noconfirm

# Output: dist/Seller Opportunity Scanner.app
```

## Running Tests

```bash
pytest
pytest --cov=src
```

## Project Structure

```
src/
  api/         - Keepa and SP-API client implementations
  core/        - Business logic (config, models, scoring, shipping, CSV import, scheduler)
  db/          - SQLAlchemy models, repository, session management
  gui/         - PyQt6 GUI (main window, tabs, widgets)
  utils/       - Mock data generators, export functionality
  main.py      - Application entry point
tests/         - Unit tests
migrations/    - Alembic database migrations
fixtures/      - Mock JSON data and sample CSV
```
# analyzer
