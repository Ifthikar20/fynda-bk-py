"""
API Orchestrator

Coordinates multiple marketplace APIs with fallback logic.
Aggregates results from eBay, Best Buy, Facebook Marketplace, Shopify stores, and mock data.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import concurrent.futures

from .query_parser import query_parser, ParsedQuery
from .deal_data import mock_deal_service
from .ebay_service import ebay_service
from .bestbuy_service import bestbuy_service
from .facebook_service import facebook_service
from .shopify_service import shopify_service
from .affiliates import affiliate_aggregator
from .amazon_service import amazon_service
from .vendors import vendor_manager

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Container for search results."""
    query: ParsedQuery
    deals: List[Dict[str, Any]]
    sources_queried: List[str]
    sources_with_results: List[str]
    cache_hit: bool
    search_time_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "deals": self.deals,
            "meta": {
                "total_results": len(self.deals),
                "sources_queried": self.sources_queried,
                "sources_with_results": self.sources_with_results,
                "cache_hit": self.cache_hit,
                "search_time_ms": self.search_time_ms,
            }
        }


class DealOrchestrator:
    """
    Orchestrates deal searches across multiple marketplace sources.
    
    Data sources (in priority order):
    1. eBay Browse API - Requires EBAY_APP_ID, EBAY_CERT_ID
    2. Best Buy Products API - Requires BESTBUY_API_KEY
    3. Facebook Marketplace - Requires RAPIDAPI_KEY (or uses mock)
    4. Shopify Stores - No auth required, scrapes /products.json
    5. Mock Data - Always available as fallback
    """
    
    def __init__(self):
        # Get source names from enabled vendors
        enabled = vendor_manager.get_enabled_vendors()
        self.all_sources = [v.name for v in enabled]
    
    def search(self, query: str) -> SearchResult:
        """
        Search for deals matching the natural language query.
        
        Queries all configured marketplaces in parallel and aggregates results.
        
        Args:
            query: Natural language search string
                   e.g., "sony camera $1200 with lens"
        
        Returns:
            SearchResult with parsed query, deals, and metadata
        """
        start_time = datetime.now()
        
        # Step 1: Parse the query
        parsed = query_parser.parse(query)
        logger.info(f"Parsed query: product='{parsed.product}', budget={parsed.budget}, requirements={parsed.requirements}")
        
        # Step 2: Fetch deals from all sources in parallel
        deals, sources_with_results = self._fetch_all_deals(parsed)
        
        # Step 3: Apply budget filter
        if parsed.budget:
            deals = [d for d in deals if d.get("price", 0) <= parsed.budget]
        
        # Step 4: Deduplicate similar listings
        deals = self._deduplicate_deals(deals)
        
        # Step 5: Rank results
        deals = self._rank_deals(deals, parsed)
        
        # Calculate search time
        search_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return SearchResult(
            query=parsed,
            deals=deals[:20],  # Return top 20 results
            sources_queried=self.all_sources,
            sources_with_results=sources_with_results,
            cache_hit=False,
            search_time_ms=search_time,
        )
    
    def _fetch_all_deals(self, parsed: ParsedQuery) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Fetch deals from affiliate networks only (CJ, Rakuten, ShareASale).
        
        Returns:
            Tuple of (all_deals, list_of_sources_that_returned_results)
        """
        all_deals = []
        sources_with_results = []
        
        # Query all enabled vendors using VendorManager
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {}
            
            # Add enabled vendors from VendorManager
            for vendor_id, instance in vendor_manager.get_all_instances().items():
                futures[executor.submit(self._fetch_from_vendor, instance, parsed)] = instance.VENDOR_NAME
            
            # Also include affiliate aggregator for compatibility
            futures[executor.submit(self._fetch_affiliates, parsed)] = "Affiliates"
            
            for future in concurrent.futures.as_completed(futures, timeout=20):
                source = futures[future]
                try:
                    deals = future.result()
                    if deals:
                        all_deals.extend(deals)
                        sources_with_results.append(source)
                        logger.info(f"Fetched {len(deals)} deals from {source}")
                except Exception as e:
                    logger.error(f"Error fetching from {source}: {e}")
        
        return all_deals, sources_with_results
    
    def _fetch_from_vendor(self, vendor_instance, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """
        Fetch deals from a vendor instance.
        
        Uses the standardized VendorProduct format.
        """
        try:
            products = vendor_instance.search_products(
                query=parsed.product,
                limit=15,
            )
            # Convert VendorProduct to dict if needed
            results = []
            for p in products:
                if hasattr(p, 'to_dict'):
                    results.append(p.to_dict())
                elif isinstance(p, dict):
                    results.append(p)
            
            # Filter by budget if specified
            if parsed.budget:
                results = [p for p in results if p.get('price', 0) <= parsed.budget]
            return results
        except Exception as e:
            logger.warning(f"Vendor fetch error: {e}")
            return []
    
    def _fetch_amazon(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Amazon via RapidAPI."""
        try:
            deals = amazon_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"Amazon fetch error: {e}")
            return []
    
    def _fetch_ebay(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from eBay."""
        try:
            deals = ebay_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"eBay fetch error: {e}")
            return []
    
    def _fetch_bestbuy(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Best Buy."""
        try:
            deals = bestbuy_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"Best Buy fetch error: {e}")
            return []
    
    def _fetch_facebook(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Facebook Marketplace."""
        try:
            deals = facebook_service.search(
                query=parsed.product,
                limit=8,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"Facebook Marketplace fetch error: {e}")
            return []
    
    def _fetch_mock(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch mock deals as fallback."""
        return mock_deal_service.search(
            query=parsed.product,
            budget=parsed.budget,
            requirements=parsed.requirements,
        )
    
    def _fetch_shopify(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Shopify stores."""
        try:
            products = shopify_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [p.to_dict() for p in products]
        except Exception as e:
            logger.warning(f"Shopify fetch error: {e}")
            return []
    
    def _fetch_affiliates(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """
        Fetch deals from affiliate networks (CJ, Rakuten, ShareASale).
        
        Provides access to 40,000+ retailers.
        """
        try:
            products = affiliate_aggregator.search_all(
                query=parsed.product,
                limit=15,
                sort_by="price",
            )
            # Filter by budget if specified
            if parsed.budget:
                products = [p for p in products if p.price <= parsed.budget or p.price == 0]
            return [p.to_dict() for p in products]
        except Exception as e:
            logger.warning(f"Affiliate networks fetch error: {e}")
            return []
    
    def _deduplicate_deals(self, deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate listings based on title similarity.
        Keeps the cheapest version of similar items.
        """
        seen_titles = {}
        unique_deals = []
        
        for deal in deals:
            # Normalize title for comparison
            title_key = deal.get("title", "").lower()[:50]
            
            if title_key not in seen_titles:
                seen_titles[title_key] = deal
                unique_deals.append(deal)
            else:
                # Keep the cheaper one
                existing = seen_titles[title_key]
                if deal.get("price", float("inf")) < existing.get("price", float("inf")):
                    unique_deals.remove(existing)
                    unique_deals.append(deal)
                    seen_titles[title_key] = deal
        
        return unique_deals
    
    def _rank_deals(
        self, deals: List[Dict[str, Any]], parsed: ParsedQuery
    ) -> List[Dict[str, Any]]:
        """
        Rank deals by value (best deals first).
        
        Ranking factors:
        1. Relevance score (matches query/requirements)
        2. Discount percentage
        3. Seller rating
        4. User reviews
        5. Source priority (real APIs ranked higher)
        """
        def score(deal: Dict) -> float:
            # Weighted scoring - ensure all values are numbers, not None
            relevance = deal.get("relevance_score") if deal.get("relevance_score") is not None else 50
            discount = deal.get("discount_percent") if deal.get("discount_percent") is not None else 0
            rating = deal.get("rating") if deal.get("rating") is not None else 4.0
            reviews_count = deal.get("reviews_count") if deal.get("reviews_count") is not None else 0
            reviews = min(reviews_count / 1000, 5)
            
            # Source priority bonus
            source = deal.get("source", "") or ""
            source_bonus = {
                "Amazon": 18,
                "eBay": 15,
                "Best Buy": 15,
                "Facebook Marketplace": 10,
                "Shopify": 8,
                "Affiliates": 5,
                "Mock": 0,
            }.get(source, 5)  # Default bonus for affiliate sources
            
            # Check if deal meets requirements
            requirement_bonus = 0
            if parsed.requirements:
                features = [f.lower() for f in deal.get("features", []) or []]
                title_lower = (deal.get("title", "") or "").lower()
                for req in parsed.requirements:
                    if req.lower() in features or req.lower() in title_lower:
                        requirement_bonus += 20
            
            return (
                float(relevance) * 0.3 +
                float(discount) * 0.2 +
                float(rating) * 4 +
                float(reviews) * 2 +
                source_bonus +
                requirement_bonus
            )
        
        return sorted(deals, key=score, reverse=True)


# Singleton instance
orchestrator = DealOrchestrator()
