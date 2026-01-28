# Seller Opportunity Scanner — AI Handoff Document

> **Purpose:** This document provides complete context for any AI assistant (Claude, GPT, etc.) to understand, modify, and extend this codebase effectively. Read this first before making changes.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Name** | Seller Opportunity Scanner |
| **Version** | 1.0.0 |
| **Platform** | macOS (Apple Silicon native) |
| **Language** | Python 3.11+ |
| **GUI Framework** | PyQt6 |
| **Database** | SQLite via SQLAlchemy 2.0 |
| **Package Manager** | pip with pyproject.toml |
| **Marketplace** | Amazon.co.uk only (UK, GBP) |

---

## What This App Does (Business Logic)

This is a **local-first desktop application** for Amazon UK sellers who want to find profitable resale opportunities from supplier price lists.

### Core Workflow

1. **Import** — User imports supplier CSV files (Makita, DeWalt, Timco brands) with cost prices
2. **Map** — App finds matching Amazon ASINs via EAN lookup or keyword search
3. **Refresh** — Background scheduler continuously fetches market data (Keepa) and fee/restriction data (SP-API)
4. **Score** — Each (PartNumber, ASIN) pair gets a 0–100 opportunity score
5. **Display** — GUI shows sortable tables with score rings, flags, and drill-down details
6. **Export** — User can export results to CSV/XLSX

### The Scoring Model

Score = weighted sum of 5 components minus penalties, clamped to 0–100:

| Component | Weight | Source |
|-----------|--------|--------|
| Velocity | 45% | Keepa `salesRankDrops30` |
| Profit | 20% | Calculated from costs, fees, sell price |
| Margin | 20% | profit / sell_net |
| Stability | 10% | Price volatility CV, offer trend |
| Viability | 5% | FBM vs Buy Box gap |

Penalties subtract points for: restrictions, Amazon presence, unknown weight, overweight, low confidence mapping, high competition, below-threshold metrics.

### Two Cost Scenarios

Every item has two cost tiers from the CSV:
- `CostExVAT_1` — single unit price
- `CostExVAT_5Plus` — bulk (5+) unit price

The app calculates profit for both and uses the better one as the "winning scenario" for the main score.

### VAT Handling

- All internal economics are **ex-VAT**
- Sell prices from Keepa are **inc-VAT** → divided by 1.20
- Fees from SP-API are assumed **inc-VAT** → divided by 1.20
- Default VAT rate: 20% (configurable per-brand)

---

## Repository Structure

```
seller-opportunity-scanner/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point, Qt app setup, logging
│   ├── core/
│   │   ├── config.py           # Pydantic settings, per-brand config, .env loading
│   │   ├── models.py           # Domain models (dataclasses, not ORM)
│   │   ├── scoring.py          # ScoringEngine — the heart of the business logic
│   │   ├── shipping.py         # ShippingCalculator (2/3 GBP tier model)
│   │   ├── csv_importer.py     # Strict CSV schema validation and parsing
│   │   └── scheduler.py        # RefreshController + RefreshWorker (QThread)
│   ├── api/
│   │   ├── keepa.py            # KeepaClient — HTTP, token bucket, response parsing
│   │   └── spapi.py            # SpApiClient — LWA auth, SigV4 signing, catalog/fees/restrictions
│   ├── db/
│   │   ├── models.py           # SQLAlchemy ORM models (8 tables)
│   │   ├── session.py          # Engine, session factory, init_database()
│   │   └── repository.py       # Data access layer (all DB operations)
│   ├── gui/
│   │   ├── main_window.py      # MainWindow with tabs, token status, refresh toggle
│   │   ├── brand_tab.py        # Table view with ScoreRingDelegate
│   │   ├── mappings_tab.py     # Multi-ASIN mapping management
│   │   ├── imports_tab.py      # CSV import with preview
│   │   ├── settings_tab.py     # Per-brand weights/penalties editor
│   │   ├── diagnostics_tab.py  # API logs, DB stats, token usage
│   │   ├── detail_dialog.py    # Score breakdown popup
│   │   └── widgets.py          # ScoreRingWidget, ScoreRingDelegate, TokenStatusWidget
│   └── utils/
│       ├── mock_data.py        # Fake Keepa/SP-API responses for testing
│       └── export.py           # CSV/XLSX export
├── tests/                      # 48 pytest tests
├── migrations/                 # Alembic (optional — app auto-creates schema)
├── fixtures/                   # Sample CSV, mock JSON
├── pyproject.toml              # Dependencies and project metadata
├── seller_scanner.spec         # PyInstaller config for .app bundle
├── SETUP_GUIDE.md              # User-facing setup instructions
└── HANDOFF.md                  # This file
```

---

## Key Files to Understand

### 1. `src/core/scoring.py`
The most important file. Contains `ScoringEngine` which:
- Calculates safe sell price (min of current/median, minus buffer)
- Computes profit for both cost scenarios
- Normalizes sub-scores to 0–100
- Applies penalties based on flags
- Returns a `ScoreResult` dataclass with full breakdown

### 2. `src/core/config.py`
Pydantic-based settings with:
- Global settings (VAT rate, shipping tiers)
- Per-brand settings (thresholds, weights, penalties)
- API credentials loaded from `~/.seller-opportunity-scanner/.env`
- `get_settings()` singleton pattern

### 3. `src/api/keepa.py`
HTTP client for Keepa API:
- Token bucket tracking (tokensLeft, refillRate, refillIn)
- `fetch_and_parse()` returns list of `KeepaSnapshot`
- Parses CSV arrays (price history) into current/median/stats
- Domain code 2 = amazon.co.uk

### 4. `src/api/spapi.py`
Amazon SP-API client:
- LWA OAuth token refresh
- AWS SigV4 request signing (implemented from scratch)
- Endpoints: catalog search, restrictions, fees estimate
- `fetch_snapshot()` returns `SpApiSnapshot`

### 5. `src/core/scheduler.py`
Background refresh system:
- `RefreshController` manages a QThread
- `RefreshWorker` runs continuous loop with Pass 1 (wide) and Pass 2 (narrow)
- Emits Qt signals for UI updates
- Token-aware pacing (waits when tokens low)

### 6. `src/db/repository.py`
All database operations in one place:
- CRUD for supplier items, candidates, snapshots, scores
- Caching logic for SP-API (TTL-based)
- Statistics queries for diagnostics

---

## Data Flow

```
CSV Import
    ↓
SupplierItem (db) ──→ AsinCandidate (db) ──→ KeepaSnapshot (db)
                                          ↘ SpApiSnapshot (db)
                                                    ↓
                                            ScoringEngine
                                                    ↓
                                            ScoreResult ──→ ScoreHistory (db)
                                                    ↓
                                                GUI Table
```

---

## Database Schema (8 Tables)

| Table | Purpose |
|-------|---------|
| `supplier_items` | Imported CSV rows with costs, versioned by batch |
| `asin_candidates` | ASIN mappings per item, with confidence/source |
| `keepa_snapshots` | Time-series Keepa data per candidate |
| `spapi_snapshots` | Time-series SP-API data per candidate |
| `score_history` | Historical scores for trend analysis |
| `brand_settings` | Per-brand config (unused — config.py preferred) |
| `global_settings` | Key-value store (unused — config.py preferred) |
| `api_logs` | Debugging: every API call logged |

---

## Configuration Hierarchy

1. **Defaults** — hardcoded in `config.py` dataclasses
2. **JSON file** — `~/.seller-opportunity-scanner/settings.json` (if exists)
3. **Environment** — `~/.seller-opportunity-scanner/.env` (API keys, mock mode)

Per-brand settings (thresholds, weights, penalties) are in the Settings tab and saved to JSON.

---

## API Integration Details

### Keepa

- **Base URL:** `https://api.keepa.com/`
- **Auth:** API key as query param `?key=XXX`
- **Rate limiting:** Token bucket. Every response includes `tokensLeft`, `refillRate`, `refillIn`.
- **Data format:** Prices in cents (divide by 100), timestamps in Keepa minutes (offset from 2011-01-01)
- **Key endpoint:** `GET /product?domain=2&asin=X,Y,Z&stats=90,1,1`

### SP-API

- **Base URL:** `https://sellingpartnerapi-eu.amazon.com`
- **Auth:** LWA access token + AWS SigV4 signature
- **UK Marketplace ID:** `A1F83G8C2ARO7P`
- **Key endpoints:**
  - `GET /catalog/2022-04-01/items/{asin}` — product details, weight
  - `GET /catalog/2022-04-01/items?identifiers=EAN` — search by EAN
  - `GET /listings/2021-08-01/restrictions?asin=X` — can we sell this?
  - `POST /products/fees/v0/items/{asin}/feesEstimate` — fee calculation

---

## Testing

```bash
# Run all 48 tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

Tests cover:
- CSV validation (headers, brands, pack qty)
- Shipping tier calculation
- VAT conversions
- Profit/margin math
- Score normalization and penalties
- Model serialization

Tests use fixtures from `conftest.py` — sample items, candidates, snapshots.

---

## Mock Mode

Set `SOS_MOCK_MODE=true` in `.env` to run without real API credentials.

Mock data generators in `src/utils/mock_data.py`:
- `get_mock_keepa_response()` — realistic price/sales data
- `get_mock_spapi_response()` — catalog, fees, restrictions

Both API clients check `settings.api.mock_mode` and return fake data if true.

---

## Known Limitations / Technical Debt

1. **No Alembic migrations in practice** — `init_database()` uses `create_all()`. Schema changes require manual migration or DB reset.

2. **SP-API batch fees not implemented** — Fees are fetched one-at-a-time. Could batch for performance.

3. **Score history not visualized** — Data is stored but no trend charts in UI.

4. **No auto-ASIN discovery** — Candidates only created from CSV hints or manual EAN search. Could auto-search on import.

5. **Hardcoded UK marketplace** — Marketplace ID is constant. Multi-marketplace would need refactoring.

6. **Refresh worker error recovery** — Errors are logged but no automatic retry queue.

7. **No unit tests for GUI** — Only core logic is tested. pytest-qt is installed but unused.

8. **Settings tab doesn't persist to JSON** — The save button calls `settings.save()` but reload isn't wired up fully.

---

## Extension Ideas

### High Value
- **Profit trend sparklines** — Show 7-day profit history in table cells
- **Auto-refresh on import** — Trigger Keepa/SP-API fetch for new items immediately
- **Bulk ASIN search** — For items without EAN, search by brand+MPN automatically
- **Price alerts** — Notify when score crosses threshold

### Medium Value
- **Multi-marketplace** — Add DE, FR, IT, ES (different marketplace IDs, same APIs)
- **FBA mode** — Currently FBM-only; add FBA fee calculation toggle
- **Competitor tracking** — Store offer history, track specific sellers
- **Dashboard tab** — Summary stats, top movers, recent changes

### Lower Priority
- **Dark mode** — Qt supports it, just need stylesheet
- **Keyboard shortcuts** — Navigate tabs, refresh, export
- **Tray icon** — Run in background with notifications
- **Auto-update** — Check GitHub releases, prompt for update

---

## Common Tasks for AI Assistants

### "Add a new column to the brand table"

1. Add field to `ScoreResult` in `src/core/models.py` (if new data)
2. Populate it in `ScoringEngine.calculate()` in `src/core/scoring.py`
3. Add column to `ScoreTableModel.COLUMNS` in `src/gui/brand_tab.py`
4. Add display logic in `_get_display_value()` same file
5. Add to export in `src/utils/export.py` `score_results_to_dict()`

### "Add a new penalty type"

1. Add field to `ScoringPenalties` in `src/core/config.py`
2. Add flag code constant (e.g., `"NEW_PENALTY"`)
3. Add penalty logic in `ScoringEngine.apply_penalties()` in `src/core/scoring.py`
4. Add color mapping in `FlagLabel.FLAG_COLORS` in `src/gui/widgets.py`
5. Add UI control in `BrandSettingsWidget` in `src/gui/settings_tab.py`

### "Add a new API data source"

1. Create client in `src/api/new_api.py`
2. Add credentials to `ApiConfig` in `src/core/config.py`
3. Add snapshot model in `src/core/models.py`
4. Add DB table in `src/db/models.py`
5. Add repository methods in `src/db/repository.py`
6. Integrate into `RefreshWorker` in `src/core/scheduler.py`
7. Add mock generator in `src/utils/mock_data.py`

### "Fix a scoring bug"

1. Write a failing test in `tests/test_scoring.py`
2. Fix the logic in `src/core/scoring.py`
3. Run `pytest tests/test_scoring.py -v` to verify
4. Run full suite `pytest tests/ -v` to check for regressions

---

## Code Style

- **Type hints everywhere** — All functions have return types, parameters typed
- **Dataclasses for domain models** — `src/core/models.py` uses `@dataclass`
- **Pydantic for config** — `src/core/config.py` uses `BaseSettings`
- **SQLAlchemy 2.0 style** — Mapped columns, type annotations
- **Qt signals for cross-thread** — Never update UI from worker thread directly
- **Decimal for money** — Never use float for currency

Formatting: `black` and `ruff` configured in `pyproject.toml`.

---

## How to Run

```bash
cd ~/Desktop/ANALYZER/seller-opportunity-scanner
source venv/bin/activate
python -m src.main
```

Or after `pip install -e .`:

```bash
seller-scanner
```

---

## Questions This Document Should Answer

| Question | Section |
|----------|---------|
| What does the app do? | What This App Does |
| How is the score calculated? | The Scoring Model |
| Where is the main business logic? | Key Files to Understand |
| How do I add a feature? | Common Tasks for AI Assistants |
| What are the known issues? | Known Limitations |
| How do I test changes? | Testing |
| What's the data model? | Database Schema, Data Flow |
| How do the APIs work? | API Integration Details |

---

## Final Notes for AI Assistants

1. **Always run tests after changes** — `pytest tests/ -v`
2. **Use mock mode for development** — No API keys needed
3. **The scoring engine is the core** — Most business logic changes go there
4. **Qt runs on main thread** — Use signals to communicate from RefreshWorker
5. **Check config.py for hardcoded values** — Thresholds, defaults, etc.
6. **The user is a UK Amazon seller** — All features should support that use case

When in doubt, read `src/core/scoring.py` — it's the most important 300 lines in the codebase.
