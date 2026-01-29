"""
Deal Serializers

Serializes deal data for API responses.
"""

from rest_framework import serializers


class DealSerializer(serializers.Serializer):
    """Serializer for individual deal items."""
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(required=False)
    price = serializers.FloatField()
    original_price = serializers.FloatField(required=False)
    discount_percent = serializers.IntegerField(required=False)
    currency = serializers.CharField(default="USD")
    source = serializers.CharField()
    seller = serializers.CharField(required=False)
    seller_rating = serializers.FloatField(required=False)
    url = serializers.URLField()
    image_url = serializers.URLField(required=False)
    condition = serializers.CharField(required=False)
    shipping = serializers.CharField(required=False)
    rating = serializers.FloatField(required=False)
    reviews_count = serializers.IntegerField(required=False)
    in_stock = serializers.BooleanField(default=True)
    relevance_score = serializers.IntegerField(required=False)
    features = serializers.ListField(child=serializers.CharField(), required=False)
    fetched_at = serializers.CharField(required=False)


class ParsedQuerySerializer(serializers.Serializer):
    """Serializer for parsed query details."""
    product = serializers.CharField()
    budget = serializers.FloatField(allow_null=True)
    requirements = serializers.ListField(child=serializers.CharField())


class QuerySerializer(serializers.Serializer):
    """Serializer for the query section of response."""
    original = serializers.CharField()
    parsed = ParsedQuerySerializer()


class MetaSerializer(serializers.Serializer):
    """Serializer for response metadata."""
    total_results = serializers.IntegerField()
    sources_queried = serializers.ListField(child=serializers.CharField())
    cache_hit = serializers.BooleanField()
    search_time_ms = serializers.IntegerField()


class SearchResponseSerializer(serializers.Serializer):
    """Serializer for the complete search response."""
    query = QuerySerializer()
    deals = DealSerializer(many=True)
    meta = MetaSerializer()
