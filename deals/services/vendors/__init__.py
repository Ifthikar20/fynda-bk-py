"""
Vendors Package

Unified vendor abstraction layer for all product sources.

Usage:
    from deals.services.vendors import vendor_manager
    
    # Search all enabled vendors
    products = vendor_manager.search_all_vendors("leather jacket")
    
    # Get a specific vendor instance
    amazon = vendor_manager.get_vendor_instance("amazon")
    
    # Check vendor status
    status = vendor_manager.get_all_status()
"""

from .base_vendor import BaseVendorService, VendorProduct, VendorConfig, VendorCategory
from .base_vendor import VendorError, QuotaExceededError, AuthenticationError
from .vendor_manager import vendor_manager
from .vendor_registry import VENDOR_REGISTRY, get_vendor_config, get_all_vendors

__all__ = [
    "BaseVendorService",
    "VendorProduct",
    "VendorConfig",
    "VendorCategory",
    "VendorError",
    "QuotaExceededError",
    "AuthenticationError",
    "vendor_manager",
    "VENDOR_REGISTRY",
    "get_vendor_config",
    "get_all_vendors",
]
