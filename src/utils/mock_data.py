"""Mock data generators for testing without API credentials."""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path

# Try to load fixtures from file
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def load_fixture(name: str) -> dict | None:
    """Load a fixture file if it exists."""
    fixture_path = FIXTURES_DIR / f"{name}.json"
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return None


def get_mock_keepa_response(asins: list[str]) -> dict:
    """Generate mock Keepa API response."""
    # Try to load from fixtures
    fixture = load_fixture("keepa_response")
    if fixture and asins:
        # Modify fixture with requested ASINs
        products = []
        for i, asin in enumerate(asins):
            product = _generate_mock_keepa_product(asin, seed=hash(asin))
            products.append(product)

        return {
            "tokensLeft": random.randint(100, 500),
            "refillRate": 20,
            "refillIn": 60,
            "tokensConsumed": len(asins),
            "tokenFlowReduction": 0.0,
            "processingTimeInMs": random.randint(50, 200),
            "products": products,
        }

    return {
        "tokensLeft": 200,
        "refillRate": 20,
        "refillIn": 60,
        "tokensConsumed": 0,
        "products": [],
    }


def _generate_mock_keepa_product(asin: str, seed: int = 0) -> dict:
    """Generate a single mock Keepa product."""
    random.seed(seed)

    base_price = random.randint(1500, 15000)  # In pence
    price_variation = int(base_price * 0.1)

    # Generate price history (timestamps and values interleaved)
    now_keepa = int((datetime.now(UTC).timestamp() + 21564000 * 60) / 60)
    prices = []
    for i in range(30):
        timestamp = now_keepa - (30 - i) * 1440  # Daily
        price = base_price + random.randint(-price_variation, price_variation)
        prices.extend([timestamp, price])

    # Current price
    current_price = base_price + random.randint(-price_variation // 2, price_variation // 2)

    # Generate CSV array (simplified - only key indices)
    csv = [None] * 30
    csv[0] = prices if random.random() > 0.7 else None  # Amazon
    csv[1] = prices  # New
    csv[7] = prices  # New FBM
    csv[18] = prices  # Buy box

    # Sales rank
    sales_rank = random.randint(1000, 500000)
    rank_drops = random.randint(5, 100)

    # Offers
    fbm_offers = random.randint(1, 20)
    fba_offers = random.randint(0, 10)

    return {
        "asin": asin,
        "domainId": 2,  # UK
        "title": f"Mock Product {asin}",
        "csv": csv,
        "stats": {
            "current": [
                current_price if random.random() > 0.5 else -1,  # Amazon
                current_price,  # New
                -1,  # Used
                sales_rank,  # Sales rank
            ] + [0] * 16,
            "avg30": [
                base_price,  # Amazon avg
                base_price,  # New avg
                -1,
                0,
            ] + [base_price] * 16,
            "min30": [
                base_price - price_variation,
            ] * 20,
            "max30": [
                base_price + price_variation,
            ] * 20,
            "salesRankDrops30": [rank_drops, 0, 0],
        },
        "offers": [
            {
                "offerId": i,
                "isFBA": i < fba_offers,
                "isPrime": i < fba_offers,
                "condition": 1,
            }
            for i in range(fbm_offers + fba_offers)
        ],
        "liveOffersOrder": list(range(fbm_offers + fba_offers)),
        "offerCountNew": prices,  # Reuse for simplicity
        "buyBoxSellerIdHistory": ["A123" if random.random() > 0.5 else "SELLER123"],
    }


def get_mock_spapi_response(
    path: str,
    params: dict | None,
    body: dict | None,
) -> dict:
    """Generate mock SP-API response."""
    # Catalog item
    if "/catalog/" in path and "/items/" in path:
        asin = path.split("/items/")[-1].split("?")[0]
        return _generate_mock_catalog_item(asin)

    # Catalog search
    if "/catalog/" in path and "/items" in path:
        return _generate_mock_catalog_search(params)

    # Restrictions
    if "/restrictions" in path:
        return _generate_mock_restrictions(params)

    # Fees
    if "/feesEstimate" in path:
        return _generate_mock_fees(body)

    return {}


def _generate_mock_catalog_item(asin: str) -> dict:
    """Generate mock catalog item response."""
    weight_kg = random.uniform(0.1, 5.0)

    return {
        "asin": asin,
        "attributes": {
            "item_package_dimensions": [
                {
                    "weight": {
                        "value": weight_kg,
                        "unit": "kilograms",
                    },
                    "length": {
                        "value": random.uniform(10, 50),
                        "unit": "centimeters",
                    },
                    "width": {
                        "value": random.uniform(5, 30),
                        "unit": "centimeters",
                    },
                    "height": {
                        "value": random.uniform(5, 20),
                        "unit": "centimeters",
                    },
                }
            ],
        },
        "summaries": [
            {
                "marketplaceId": "A1F83G8C2ARO7P",
                "itemName": f"Mock Product Title for {asin}",
                "brand": random.choice(["Makita", "DeWalt", "Timco"]),
                "browseClassification": {
                    "displayName": "Power Tools",
                },
            }
        ],
    }


def _generate_mock_catalog_search(params: dict | None) -> dict:
    """Generate mock catalog search response."""
    items = []
    num_results = random.randint(1, 5)

    for i in range(num_results):
        asin = f"B{random.randint(10000000, 99999999):08d}"
        items.append({
            "asin": asin,
            "summaries": [
                {
                    "marketplaceId": "A1F83G8C2ARO7P",
                    "itemName": f"Search Result {i + 1}",
                    "brand": random.choice(["Makita", "DeWalt", "Timco"]),
                }
            ],
        })

    return {"items": items}


def _generate_mock_restrictions(params: dict | None) -> dict:
    """Generate mock restrictions response."""
    # 80% chance of no restrictions
    if random.random() > 0.2:
        return {"restrictions": []}

    return {
        "restrictions": [
            {
                "conditionType": "new_new",
                "marketplaceId": "A1F83G8C2ARO7P",
                "reasonCode": "APPROVAL_REQUIRED",
            }
        ]
    }


def _generate_mock_fees(body: dict | None) -> dict:
    """Generate mock fee estimate response."""
    if not body:
        return {"error": "No body provided"}

    request = body.get("FeesEstimateRequest", {})
    price_data = request.get("PriceToEstimateFees", {}).get("ListingPrice", {})
    price = float(price_data.get("Amount", 0))

    # Calculate mock fees (roughly 15% total)
    referral_fee = price * 0.15
    variable_closing_fee = 0.50

    total_fee = referral_fee + variable_closing_fee

    return {
        "payload": {
            "FeesEstimateResult": {
                "Status": "Success",
                "FeesEstimate": {
                    "TotalFeesEstimate": {
                        "CurrencyCode": "GBP",
                        "Amount": round(total_fee, 2),
                    },
                    "FeeDetailList": [
                        {
                            "FeeType": "ReferralFee",
                            "FeeAmount": {
                                "CurrencyCode": "GBP",
                                "Amount": round(referral_fee, 2),
                            },
                        },
                        {
                            "FeeType": "VariableClosingFee",
                            "FeeAmount": {
                                "CurrencyCode": "GBP",
                                "Amount": round(variable_closing_fee, 2),
                            },
                        },
                    ],
                },
            }
        }
    }
