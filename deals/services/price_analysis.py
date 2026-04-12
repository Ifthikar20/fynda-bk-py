"""
Price Analysis Service
======================

Computes price positioning for a product by comparing it against
similar items from the existing vendor search infrastructure.

Returns: min, max, avg prices, the product's percentile rank,
and a price verdict (great deal / fair / above average / overpriced).
"""

import logging
import statistics
from deals.services.orchestrator import DealOrchestrator
from outfi.config import config

logger = logging.getLogger(__name__)


class PriceAnalysisService:
    """
    Analyse where a product's price falls relative to comparable products.
    Uses the existing search pipeline to gather market prices.
    """

    # Verdict thresholds (percentile-based)
    THRESHOLDS = {
        "great_deal": 25,      # Bottom 25% = great deal
        "good_price": 40,      # 25-40% = good price
        "fair": 65,            # 40-65% = fair price
        "above_average": 85,   # 65-85% = above average
        # 85%+ = overpriced
    }

    @staticmethod
    def analyse(product_name: str, product_price: float, limit: int = 30) -> dict:
        """
        Compare a product's price against similar products from all vendors.

        Args:
            product_name: Name/title of the product
            product_price: Current price of the product
            limit: Max comparable products to fetch

        Returns:
            {
                "product_price": float,
                "min_price": float,
                "max_price": float,
                "avg_price": float,
                "median_price": float,
                "compared_count": int,
                "percentile": int,        # 0-100, where 0 = cheapest
                "verdict": str,           # "great_deal", "good_price", "fair", "above_average", "overpriced"
                "verdict_label": str,     # Human-readable label
                "savings_vs_avg": float,  # Negative = cheaper than avg
                "price_distribution": list,  # Sorted price list for the UI gauge
            }
        """
        if product_price <= 0:
            return PriceAnalysisService._empty_result(product_price)

        # Search for comparable products using existing infrastructure
        comparable_prices = PriceAnalysisService._fetch_comparable_prices(
            product_name, limit
        )

        if len(comparable_prices) < 3:
            return PriceAnalysisService._empty_result(product_price)

        # Compute statistics
        min_price = min(comparable_prices)
        max_price = max(comparable_prices)
        avg_price = statistics.mean(comparable_prices)
        median_price = statistics.median(comparable_prices)

        # Calculate percentile rank
        below_count = sum(1 for p in comparable_prices if p < product_price)
        percentile = int((below_count / len(comparable_prices)) * 100)

        # Determine verdict
        verdict, verdict_label = PriceAnalysisService._get_verdict(percentile)

        # Savings vs average
        savings_vs_avg = round(product_price - avg_price, 2)

        return {
            "product_price": product_price,
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "avg_price": round(avg_price, 2),
            "median_price": round(median_price, 2),
            "compared_count": len(comparable_prices),
            "percentile": percentile,
            "verdict": verdict,
            "verdict_label": verdict_label,
            "savings_vs_avg": savings_vs_avg,
            "price_distribution": sorted([round(p, 2) for p in comparable_prices]),
        }

    @staticmethod
    def _fetch_comparable_prices(product_name: str, limit: int) -> list:
        """
        Use the existing DealOrchestrator to find comparable product prices.
        Extracts numeric prices from all returned deals.
        """
        try:
            orchestrator = DealOrchestrator()
            search_result = orchestrator.search(product_name)

            prices = []
            for deal in search_result.deals[:limit]:
                price = deal.get("price")
                if price is None:
                    continue

                # Handle string prices like "$29.99"
                if isinstance(price, str):
                    price = price.replace("$", "").replace(",", "").strip()
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        continue
                else:
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        continue

                if price > 0:
                    prices.append(price)

            logger.info(
                f"Price analysis: found {len(prices)} comparable prices for '{product_name}'"
            )
            return prices

        except Exception as e:
            logger.warning(f"Price analysis search failed: {e}")
            return []

    @staticmethod
    def _get_verdict(percentile: int) -> tuple:
        """Return (verdict_key, human_label) based on percentile."""
        t = PriceAnalysisService.THRESHOLDS
        if percentile <= t["great_deal"]:
            return ("great_deal", "Great Deal 🔥")
        elif percentile <= t["good_price"]:
            return ("good_price", "Good Price ✅")
        elif percentile <= t["fair"]:
            return ("fair", "Fair Price")
        elif percentile <= t["above_average"]:
            return ("above_average", "Above Average")
        else:
            return ("overpriced", "Overpriced ⚠️")

    @staticmethod
    def _empty_result(product_price: float) -> dict:
        """Return a result with no comparison data."""
        return {
            "product_price": product_price,
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "median_price": None,
            "compared_count": 0,
            "percentile": None,
            "verdict": "unknown",
            "verdict_label": "Not enough data",
            "savings_vs_avg": None,
            "price_distribution": [],
        }
