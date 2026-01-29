"""
Affiliate Network Services

Integrations with major affiliate networks:
- CJ Affiliate (Commission Junction)
- Rakuten Advertising
- ShareASale
- Awin

These provide access to 40,000+ retailers for product search.
"""

from .affiliate_base import AffiliateProduct, AffiliateService
from .cj_affiliate import CJAffiliateService, cj_service
from .rakuten import RakutenService, rakuten_service
from .shareasale import ShareASaleService, shareasale_service
from .affiliate_aggregator import AffiliateAggregator, affiliate_aggregator

__all__ = [
    "AffiliateProduct",
    "AffiliateService",
    "CJAffiliateService",
    "cj_service",
    "RakutenService",
    "rakuten_service",
    "ShareASaleService",
    "shareasale_service",
    "AffiliateAggregator",
    "affiliate_aggregator",
]
