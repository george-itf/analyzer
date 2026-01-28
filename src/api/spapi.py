"""Amazon SP-API client with LWA authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests

from src.core.config import Settings
from src.core.models import AsinCandidate, SpApiSnapshot

# UK Marketplace ID
UK_MARKETPLACE_ID = "A1F83G8C2ARO7P"

# SP-API endpoints
SP_API_ENDPOINT = "https://sellingpartnerapi-eu.amazon.com"
LWA_ENDPOINT = "https://api.amazon.com/auth/o2/token"


@dataclass
class SpApiAuth:
    """SP-API authentication state."""

    access_token: str = ""
    token_type: str = "bearer"
    expires_at: datetime | None = None
    refresh_token: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if the access token is still valid."""
        if not self.access_token or not self.expires_at:
            return False
        # Add 5 minute buffer
        return datetime.now(UTC) < self.expires_at


class SpApiClient:
    """Amazon SP-API client with LWA + SigV4 authentication."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the SP-API client."""
        self.settings = settings
        self.mock_mode = settings.api.mock_mode

        # Credentials
        self.client_id = settings.api.spapi_client_id
        self.client_secret = settings.api.spapi_client_secret
        self.refresh_token = settings.api.spapi_refresh_token
        self.aws_access_key = settings.api.spapi_aws_access_key
        self.aws_secret_key = settings.api.spapi_aws_secret_key
        self.role_arn = settings.api.spapi_role_arn

        # Authentication state
        self._auth = SpApiAuth(refresh_token=self.refresh_token)

        # Session
        self.session = requests.Session()

        # Region
        self.region = "eu-west-1"
        self.service = "execute-api"

    def _get_lwa_access_token(self) -> str:
        """Get or refresh the LWA access token."""
        if self._auth.is_valid:
            return self._auth.access_token

        if self.mock_mode:
            self._auth.access_token = "mock_access_token"
            self._auth.expires_at = datetime.now(UTC).replace(
                hour=datetime.now(UTC).hour + 1
            )
            return self._auth.access_token

        # Request new access token
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = requests.post(LWA_ENDPOINT, data=data, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        self._auth.access_token = token_data["access_token"]
        self._auth.token_type = token_data.get("token_type", "bearer")

        expires_in = token_data.get("expires_in", 3600)
        self._auth.expires_at = datetime.now(UTC).replace(
            second=datetime.now(UTC).second + expires_in
        )

        return self._auth.access_token

    def _sign_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: str = "",
    ) -> dict[str, str]:
        """Sign a request using AWS Signature Version 4."""
        # Parse URL
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.netloc
        canonical_uri = parsed.path or "/"
        canonical_querystring = parsed.query

        # Current time
        t = datetime.now(UTC)
        amz_date = t.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = t.strftime("%Y%m%d")

        # Create canonical headers
        headers["host"] = host
        headers["x-amz-date"] = amz_date

        signed_headers = ";".join(sorted(headers.keys()))
        canonical_headers = "".join(
            f"{k}:{headers[k]}\n" for k in sorted(headers.keys())
        )

        # Create payload hash
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        # Create canonical request
        canonical_request = (
            f"{method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        # Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        # Create signing key
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(f"AWS4{self.aws_secret_key}".encode(), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, self.service)
        k_signing = sign(k_service, "aws4_request")

        signature = hmac.new(
            k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Create authorization header
        authorization = (
            f"{algorithm} "
            f"Credential={self.aws_access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers["Authorization"] = authorization
        return headers

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict:
        """Make a signed request to the SP-API."""
        if self.mock_mode:
            return self._mock_response(path, params, body)

        access_token = self._get_lwa_access_token()

        url = f"{SP_API_ENDPOINT}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        headers = {
            "x-amz-access-token": access_token,
            "content-type": "application/json",
        }

        payload = json.dumps(body) if body else ""

        headers = self._sign_request(method, url, headers, payload)

        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            data=payload if body else None,
            timeout=30,
        )

        if response.status_code == 429:
            # Rate limited
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise SpApiRateLimitError(f"Rate limited. Retry after {retry_after}s")

        response.raise_for_status()
        return response.json()

    def _mock_response(
        self, path: str, params: dict | None, body: dict | None
    ) -> dict:
        """Generate mock response for testing."""
        from src.utils.mock_data import get_mock_spapi_response
        return get_mock_spapi_response(path, params, body)

    def get_catalog_item(self, asin: str) -> dict | None:
        """Get catalog item details for an ASIN."""
        path = f"/catalog/2022-04-01/items/{asin}"
        params = {
            "marketplaceIds": UK_MARKETPLACE_ID,
            "includedData": "attributes,dimensions,identifiers,images,salesRanks,summaries",
        }

        try:
            response = self._make_request("GET", path, params=params)
            return response
        except Exception:
            return None

    def search_catalog_by_identifier(
        self,
        identifier: str,
        identifier_type: str = "EAN",
    ) -> list[dict]:
        """Search catalog by identifier (EAN, UPC, etc.)."""
        path = "/catalog/2022-04-01/items"
        params = {
            "marketplaceIds": UK_MARKETPLACE_ID,
            "identifiersType": identifier_type,
            "identifiers": identifier,
            "includedData": "attributes,identifiers,summaries",
        }

        try:
            response = self._make_request("GET", path, params=params)
            return response.get("items", [])
        except Exception:
            return []

    def search_catalog_by_keywords(
        self,
        keywords: str,
        brand: str | None = None,
    ) -> list[dict]:
        """Search catalog by keywords."""
        path = "/catalog/2022-04-01/items"
        params = {
            "marketplaceIds": UK_MARKETPLACE_ID,
            "keywords": keywords,
            "includedData": "attributes,identifiers,summaries",
            "pageSize": 10,
        }

        if brand:
            params["brandNames"] = brand

        try:
            response = self._make_request("GET", path, params=params)
            return response.get("items", [])
        except Exception:
            return []

    def get_restrictions(self, asin: str) -> dict:
        """Check listing restrictions for an ASIN."""
        path = "/listings/2021-08-01/restrictions"
        params = {
            "asin": asin,
            "marketplaceIds": UK_MARKETPLACE_ID,
            "conditionType": "new_new",
            "reasonLocale": "en_GB",
        }

        try:
            response = self._make_request("GET", path, params=params)
            return response
        except Exception as e:
            return {"restrictions": [], "error": str(e)}

    def get_fees_estimate(
        self,
        asin: str,
        price: Decimal,
        currency: str = "GBP",
        is_fba: bool = False,
    ) -> dict:
        """Get fee estimate for an ASIN at a given price."""
        path = f"/products/fees/v0/items/{asin}/feesEstimate"

        body = {
            "FeesEstimateRequest": {
                "MarketplaceId": UK_MARKETPLACE_ID,
                "IsAmazonFulfilled": is_fba,
                "PriceToEstimateFees": {
                    "ListingPrice": {
                        "CurrencyCode": currency,
                        "Amount": float(price),
                    },
                    "Shipping": {
                        "CurrencyCode": currency,
                        "Amount": 0.0,  # Free shipping
                    },
                },
                "Identifier": asin,
            }
        }

        try:
            response = self._make_request("POST", path, body=body)
            return response
        except Exception as e:
            return {"error": str(e)}

    def get_fees_estimates_batch(
        self,
        items: list[tuple[str, Decimal]],
        currency: str = "GBP",
        is_fba: bool = False,
    ) -> dict[str, dict]:
        """Get fee estimates for multiple ASINs using batch API.

        Returns a dict mapping ASIN to fee response.
        """
        if not items:
            return {}

        # SP-API batch fees endpoint: POST /products/fees/v0/feesEstimate
        # Limited to 20 items per request
        path = "/products/fees/v0/feesEstimate"
        batch_size = 20
        all_results: dict[str, dict] = {}

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # Build batch request body
            requests_list = []
            for asin, price in batch:
                requests_list.append({
                    "MarketplaceId": UK_MARKETPLACE_ID,
                    "IdType": "ASIN",
                    "IdValue": asin,
                    "IsAmazonFulfilled": is_fba,
                    "PriceToEstimateFees": {
                        "ListingPrice": {
                            "CurrencyCode": currency,
                            "Amount": float(price),
                        },
                        "Shipping": {
                            "CurrencyCode": currency,
                            "Amount": 0.0,
                        },
                    },
                    "Identifier": asin,  # Used to match results
                })

            body = requests_list

            try:
                response = self._make_request("POST", path, body=body)

                # Parse response - it returns a list of FeesEstimateResult
                for result in response:
                    status = result.get("Status", "")
                    identifier = result.get("FeesEstimateIdentifier", {})
                    asin = identifier.get("IdValue", "") or identifier.get("SellerInputIdentifier", "")

                    if status == "Success" and asin:
                        all_results[asin] = result
                    elif asin:
                        # Store error result too
                        all_results[asin] = {"error": result.get("Error", {}).get("Message", "Unknown error")}

            except Exception:
                # On error, fall back to individual requests for this batch
                for asin, price in batch:
                    if asin not in all_results:
                        try:
                            result = self.get_fees_estimate(asin, price, currency, is_fba)
                            all_results[asin] = result
                        except Exception as inner_e:
                            all_results[asin] = {"error": str(inner_e)}

        return all_results

    def parse_batch_fee_result(self, result: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
        """Parse a batch fee result into (total, referral, fba, variable_closing)."""
        if "error" in result:
            return None, None, None, None

        estimate = result.get("FeesEstimate", {})
        fee_details = estimate.get("FeeDetailList", [])

        total = estimate.get("TotalFeesEstimate", {})
        total_fee = Decimal(str(total.get("Amount", 0))) if total else None

        referral_fee = None
        fba_fee = None
        variable_fee = None

        for detail in fee_details:
            fee_type = detail.get("FeeType", "")
            fee_amount = Decimal(str(detail.get("FeeAmount", {}).get("Amount", 0)))

            if fee_type == "ReferralFee":
                referral_fee = fee_amount
            elif fee_type == "FBAFees":
                fba_fee = fee_amount
            elif fee_type == "VariableClosingFee":
                variable_fee = fee_amount

        return total_fee, referral_fee, fba_fee, variable_fee

    def fetch_snapshot(
        self,
        asin: str,
        sell_price: Decimal,
    ) -> SpApiSnapshot:
        """Fetch all SP-API data for an ASIN and create a snapshot."""
        snapshot = SpApiSnapshot(
            asin=asin,
            snapshot_time=datetime.now(),
            sell_price_used=sell_price,
        )

        raw_data: dict[str, Any] = {}

        # Get catalog item for weight and product info
        catalog = self.get_catalog_item(asin)
        if catalog:
            raw_data["catalog"] = catalog

            # Parse weight
            attributes = catalog.get("attributes", {})
            dimensions = attributes.get("item_package_dimensions", [])
            if dimensions:
                dim = dimensions[0]
                weight_data = dim.get("weight", {})
                if weight_data:
                    weight_value = weight_data.get("value", 0)
                    weight_unit = weight_data.get("unit", "").lower()

                    # Convert to kg
                    if weight_unit == "grams" or weight_unit == "g":
                        snapshot.weight_kg = Decimal(str(weight_value)) / 1000
                    elif weight_unit == "kilograms" or weight_unit == "kg":
                        snapshot.weight_kg = Decimal(str(weight_value))
                    elif weight_unit == "pounds" or weight_unit == "lb":
                        snapshot.weight_kg = Decimal(str(weight_value)) * Decimal("0.453592")
                    elif weight_unit == "ounces" or weight_unit == "oz":
                        snapshot.weight_kg = Decimal(str(weight_value)) * Decimal("0.0283495")

                    snapshot.weight_source = "catalog"

            # Parse summaries
            summaries = catalog.get("summaries", [])
            if summaries:
                for summary in summaries:
                    if summary.get("marketplaceId") == UK_MARKETPLACE_ID:
                        snapshot.product_title = summary.get("itemName", "")
                        snapshot.product_brand = summary.get("brand", "")
                        browse_class = summary.get("browseClassification", {})
                        snapshot.product_category = browse_class.get("displayName", "")
                        break

        # Get restrictions
        restrictions = self.get_restrictions(asin)
        raw_data["restrictions"] = restrictions

        restriction_list = restrictions.get("restrictions", [])
        if restriction_list:
            snapshot.is_restricted = True
            reasons = []
            for r in restriction_list:
                reason = r.get("reasonCode", "UNKNOWN")
                reasons.append(reason)
            snapshot.restriction_reasons = ", ".join(reasons)

        # Get fee estimate
        fees = self.get_fees_estimate(asin, sell_price, is_fba=False)
        raw_data["fees"] = fees

        if "error" not in fees:
            payload = fees.get("payload", {})
            estimate = payload.get("FeesEstimateResult", {}).get("FeesEstimate", {})
            fee_details = estimate.get("FeeDetailList", [])

            total = estimate.get("TotalFeesEstimate", {})
            if total:
                snapshot.fee_total_gross = Decimal(str(total.get("Amount", 0)))

            for detail in fee_details:
                fee_type = detail.get("FeeType", "")
                fee_amount = Decimal(str(detail.get("FeeAmount", {}).get("Amount", 0)))

                if fee_type == "ReferralFee":
                    snapshot.fee_referral = fee_amount
                elif fee_type == "FBAFees":
                    snapshot.fee_fba = fee_amount
                elif fee_type == "VariableClosingFee":
                    snapshot.fee_variable_closing = fee_amount

        snapshot.raw_json = json.dumps(raw_data)
        return snapshot

    def search_asins_for_item(
        self,
        ean: str | None,
        mpn: str | None,
        description: str | None,
        brand: str,
    ) -> list[AsinCandidate]:
        """Search for ASIN candidates for a supplier item."""
        from src.core.models import CandidateSource

        candidates: list[AsinCandidate] = []
        seen_asins: set[str] = set()

        # Search by EAN first (highest confidence)
        if ean and ean.strip():
            items = self.search_catalog_by_identifier(ean.strip(), "EAN")
            for item in items:
                asin = item.get("asin", "")
                if asin and asin not in seen_asins:
                    seen_asins.add(asin)

                    summaries = item.get("summaries", [])
                    title = ""
                    amazon_brand = ""
                    for s in summaries:
                        if s.get("marketplaceId") == UK_MARKETPLACE_ID:
                            title = s.get("itemName", "")
                            amazon_brand = s.get("brand", "")
                            break

                    candidates.append(
                        AsinCandidate(
                            asin=asin,
                            title=title,
                            amazon_brand=amazon_brand,
                            match_reason=f"EAN match: {ean}",
                            confidence_score=Decimal("0.95"),
                            source=CandidateSource.SPAPI_EAN,
                        )
                    )

        # Search by keywords if no EAN results
        if not candidates:
            keywords_parts = []
            if brand:
                keywords_parts.append(brand)
            if mpn:
                keywords_parts.append(mpn)
            if description:
                # Take first few words of description
                desc_words = description.split()[:5]
                keywords_parts.extend(desc_words)

            if keywords_parts:
                keywords = " ".join(keywords_parts)
                items = self.search_catalog_by_keywords(keywords, brand)

                for item in items:
                    asin = item.get("asin", "")
                    if asin and asin not in seen_asins:
                        seen_asins.add(asin)

                        summaries = item.get("summaries", [])
                        title = ""
                        amazon_brand = ""
                        for s in summaries:
                            if s.get("marketplaceId") == UK_MARKETPLACE_ID:
                                title = s.get("itemName", "")
                                amazon_brand = s.get("brand", "")
                                break

                        # Lower confidence for keyword matches
                        confidence = Decimal("0.5")
                        if amazon_brand.lower() == brand.lower():
                            confidence = Decimal("0.7")

                        candidates.append(
                            AsinCandidate(
                                asin=asin,
                                title=title,
                                amazon_brand=amazon_brand,
                                match_reason=f"Keyword match: {keywords[:50]}",
                                confidence_score=confidence,
                                source=CandidateSource.SPAPI_KEYWORD,
                            )
                        )

        return candidates


class SpApiRateLimitError(Exception):
    """Raised when SP-API rate limit is hit."""

    pass
