"""
Price Analysis API View
========================

GET /api/price-analysis/?product=<name>&price=<amount>

Returns price positioning data: where this product's price falls
relative to similar products across all marketplace vendors.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from deals.services.price_analysis import PriceAnalysisService

logger = logging.getLogger(__name__)


class PriceAnalysisView(APIView):
    """
    GET /api/price-analysis/?product=nike+air+max&price=129.99

    Returns:
        - min_price, max_price, avg_price, median_price
        - percentile (0-100, where 0 = cheapest)
        - verdict: "great_deal", "good_price", "fair", "above_average", "overpriced"
        - verdict_label: Human-readable label
        - savings_vs_avg: How much cheaper (negative) or more expensive than average
        - compared_count: Number of products compared against
    """
    permission_classes = [AllowAny]

    def get(self, request):
        product = request.query_params.get("product", "").strip()
        price_str = request.query_params.get("price", "").strip()

        if not product:
            return Response(
                {"error": "Missing 'product' query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not price_str:
            return Response(
                {"error": "Missing 'price' query parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            price = float(price_str.replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid price value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if price <= 0:
            return Response(
                {"error": "Price must be greater than 0"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = PriceAnalysisService.analyse(product, price)
            return Response(result)
        except Exception as e:
            logger.exception(f"Price analysis failed: {e}")
            return Response(
                {"error": "Price analysis failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
