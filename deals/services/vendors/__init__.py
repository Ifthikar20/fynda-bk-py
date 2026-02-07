"""
Vendors Package

Centralized vendor management for Fynda.
Provides access to all vendor services through VendorManager.
"""

from .base_vendor import BaseVendorService, VendorProduct, VendorConfig, VendorCategory
from .vendor_registry import VENDOR_REGISTRY, get_vendor_config, get_all_vendors
from .vendor_manager import VendorManager, vendor_manager

__all__ = [
    # Base classes
    "BaseVendorService",
    "VendorProduct",
    "VendorConfig",
    "VendorCategory",
    # Registry
    "VENDOR_REGISTRY",
    "get_vendor_config",
    "get_all_vendors",
    # Manager
    "VendorManager",
    "vendor_manager",
]
