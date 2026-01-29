"""
Affiliate Network Aggregator

Queries multiple affiliate networks in parallel and combines results.
Provides unified access to 40,000+ retailers.
"""

import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from collections import defaultdict

from .affiliate_base import AffiliateProduct, AffiliateService
from .cj_affiliate import cj_service
from .rakuten import rakuten_service
from .shareasale import shareasale_service

logger = logging.getLogger(__name__)


class AffiliateAggregator:
    """
    Aggregates product search across all affiliate networks.
    
    Features:
    - Parallel API calls to all networks
    - Deduplication by product title/merchant
    - Price sorting
    - Network statistics
    
    Combined coverage:
    - CJ Affiliate: 3,000+ brands
    - Rakuten: 2,500+ retailers  
    - ShareASale: 16,000+ merchants
    - Total: ~21,500+ unique merchants
    """
    
    def __init__(self):
        """Initialize aggregator with all network services."""
        self.services: list[AffiliateService] = [
            cj_service,
            rakuten_service,
            shareasale_service,
        ]
        self.timeout = 20  # Max time to wait for all APIs
        self.max_workers = 5  # Parallel threads
    
    def search_all(
        self, 
        query: str, 
        limit: int = 30,
        networks: Optional[list[str]] = None,
        sort_by: str = "price",
        dedupe: bool = True
    ) -> list[AffiliateProduct]:
        """
        Search all affiliate networks in parallel.
        
        Args:
            query: Product search query
            limit: Total products to return (distributed across networks)
            networks: Optional list of networks to query (e.g., ["cj", "rakuten"])
            sort_by: Sort order - "price", "discount", or "relevance"
            dedupe: Whether to deduplicate similar products
            
        Returns:
            Combined list of products from all networks
        """
        # Filter services if specific networks requested
        active_services = self.services
        if networks:
            network_set = set(n.lower() for n in networks)
            active_services = [s for s in self.services if s.NETWORK_NAME in network_set]
        
        if not active_services:
            logger.warning("No affiliate services available")
            return []
        
        # Calculate per-network limit
        per_network_limit = max(10, limit // len(active_services) + 5)
        
        # Query all networks in parallel
        all_products = []
        network_stats = defaultdict(int)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all search tasks
            future_to_service = {
                executor.submit(service.search_products, query, per_network_limit): service
                for service in active_services
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_service, timeout=self.timeout):
                service = future_to_service[future]
                try:
                    products = future.result()
                    all_products.extend(products)
                    network_stats[service.NETWORK_NAME] = len(products)
                    logger.info(f"{service.NETWORK_NAME}: {len(products)} products")
                except Exception as e:
                    logger.error(f"Error from {service.NETWORK_NAME}: {e}")
                    network_stats[service.NETWORK_NAME] = 0
        
        logger.info(f"Affiliate search complete: {len(all_products)} total products from {len(network_stats)} networks")
        
        # Deduplicate similar products
        if dedupe:
            all_products = self._deduplicate(all_products)
        
        # Sort results
        all_products = self._sort_products(all_products, sort_by)
        
        # Limit final results
        return all_products[:limit]
    
    def _deduplicate(self, products: list[AffiliateProduct]) -> list[AffiliateProduct]:
        """
        Remove duplicate products based on title similarity and merchant.
        
        Keeps the product with the lowest price when duplicates found.
        """
        seen = {}  # Key: normalized title + merchant -> product
        
        for product in products:
            # Create dedup key from title words and merchant
            title_words = set(product.title.lower().split()[:5])
            key = (frozenset(title_words), product.merchant_name.lower())
            
            if key not in seen or product.price < seen[key].price:
                seen[key] = product
        
        deduped = list(seen.values())
        if len(deduped) < len(products):
            logger.info(f"Deduplicated: {len(products)} -> {len(deduped)} products")
        
        return deduped
    
    def _sort_products(self, products: list[AffiliateProduct], sort_by: str) -> list[AffiliateProduct]:
        """Sort products by specified criteria."""
        if sort_by == "price":
            return sorted(products, key=lambda p: p.price if p.price > 0 else float('inf'))
        elif sort_by == "discount":
            return sorted(
                products, 
                key=lambda p: -(p.discount_percent or 0) if p.discount_percent else 0,
                reverse=True
            )
        else:  # relevance - keep original order but prioritize in-stock
            return sorted(products, key=lambda p: (not p.in_stock, 0))
    
    def get_network_status(self) -> dict:
        """
        Get configuration status of all networks.
        
        Returns dict with network name -> configured status
        """
        return {
            service.NETWORK_NAME: {
                "configured": service.is_configured(),
                "name": service.__class__.__name__,
            }
            for service in self.services
        }
    
    def search_network(self, network: str, query: str, limit: int = 20) -> list[AffiliateProduct]:
        """Search a specific network only."""
        return self.search_all(query, limit, networks=[network])


# Singleton instance
affiliate_aggregator = AffiliateAggregator()
