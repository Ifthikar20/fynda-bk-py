"""
Affiliates Vendor

Wraps the existing affiliate_aggregator (CJ, Rakuten, ShareASale)
as a single BaseVendorService so it fits into the unified vendor pattern.

The aggregator itself handles parallel fan-out to each network internally.
"""

import logging
from typing import List
from datetime import datetime

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class AffiliatesVendor(BaseVendorService):
    """
    Wraps all affiliate networks as one vendor.
    
    Internally delegates to affiliate_aggregator.search_all()
    which fans out to CJ, Rakuten, and ShareASale in parallel.
    """
    
    VENDOR_ID = "affiliates"
    VENDOR_NAME = "Affiliates"
    PRIORITY = 75
    TIMEOUT = 20  # Aggregator has its own internal timeout
    
    def _load_credentials(self):
        # Import lazily to avoid circular imports
        pass
    
    def is_configured(self) -> bool:
        """Check if at least one affiliate network is configured."""
        try:
            from ..affiliates.affiliate_aggregator import affiliate_aggregator
            status = affiliate_aggregator.get_network_status()
            return any(v.get("configured") for v in status.values())
        except Exception:
            return False
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        try:
            from ..affiliates.affiliate_aggregator import affiliate_aggregator
        except ImportError:
            logger.warning("affiliate_aggregator not available")
            return []
        
        # Delegate to the aggregator
        affiliate_products = affiliate_aggregator.search_all(query, limit=limit)
        
        # Convert AffiliateProduct -> VendorProduct
        results = []
        for ap in affiliate_products:
            # Calculate discount
            discount = ap.discount_percent
            if not discount and ap.original_price and ap.price and ap.original_price > ap.price:
                discount = int((1 - ap.price / ap.original_price) * 100)
            
            results.append(VendorProduct(
                id=ap.id,
                title=ap.title,
                description=ap.description,
                price=ap.price,
                original_price=ap.original_price,
                discount_percent=discount,
                currency=ap.currency,
                url=ap.affiliate_url or ap.product_url,
                product_url=ap.product_url,
                image_url=ap.image_url,
                source=f"Affiliate ({ap.network.upper()})" if ap.network else "Affiliate",
                merchant_name=ap.merchant_name,
                merchant_id=ap.merchant_id,
                network=ap.network,
                brand=ap.brand,
                category=ap.category,
                in_stock=ap.in_stock,
                sku=ap.sku,
                upc=ap.upc,
                fetched_at=datetime.now().isoformat(),
            ))
        
        logger.info(f"Affiliates returned {len(results)} products for '{query}'")
        return results
