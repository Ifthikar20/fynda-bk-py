"""
Vendor Manager

Entitlement service to toggle vendors on/off dynamically.
Reads configuration from environment variables.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from importlib import import_module

from .vendor_registry import VENDOR_REGISTRY, VendorConfig, VendorCategory
from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class VendorManager:
    """
    Manages vendor lifecycle and entitlements.
    
    Allows enabling/disabling vendors via environment variables.
    Provides access to vendor instances and their status.
    """
    
    def __init__(self):
        self._vendor_instances: Dict[str, BaseVendorService] = {}
        self._load_vendors()
    
    def _load_vendors(self):
        """Load all enabled vendors."""
        for vendor_id, config in VENDOR_REGISTRY.items():
            if self.is_vendor_enabled(vendor_id):
                try:
                    instance = self._instantiate_vendor(config)
                    if instance:
                        self._vendor_instances[vendor_id] = instance
                        logger.info(f"Loaded vendor: {config.name}")
                except Exception as e:
                    logger.error(f"Failed to load vendor {vendor_id}: {e}")
    
    def _instantiate_vendor(self, config: VendorConfig) -> Optional[BaseVendorService]:
        """Create an instance of a vendor service."""
        try:
            # Map service class names to actual classes
            service_map = {
                "DemoStoreService": "deals.services.vendors.demo_store.DemoStoreService",
                "FakeStoreService": "deals.services.vendors.fakestore.FakeStoreService",
                "DummyJSONService": "deals.services.vendors.dummyjson.DummyJSONService",
                # Affiliate services (use existing)
                "RakutenService": "deals.services.affiliates.rakuten.RakutenService",
                "CJService": "deals.services.affiliates.cj_affiliate.CJAffiliateService",
                "ShareASaleService": "deals.services.affiliates.shareasale.ShareASaleService",
            }
            
            class_path = service_map.get(config.service_class)
            if not class_path:
                logger.warning(f"No service mapping for {config.service_class}")
                return None
            
            module_path, class_name = class_path.rsplit(".", 1)
            module = import_module(module_path)
            service_class = getattr(module, class_name)
            return service_class()
        except ImportError as e:
            logger.debug(f"Module not found for {config.service_class}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error instantiating {config.service_class}: {e}")
            return None
    
    def is_vendor_enabled(self, vendor_id: str) -> bool:
        """
        Check if a vendor is enabled.
        
        Reads from environment variable first, falls back to registry default.
        """
        config = VENDOR_REGISTRY.get(vendor_id)
        if not config:
            return False
        
        # Check environment variable
        env_key = config.env_key
        env_value = os.getenv(env_key, None)
        
        if env_value is not None:
            return env_value.lower() in ("true", "1", "yes", "on")
        
        # Fall back to registry default
        return config.enabled
    
    def get_enabled_vendors(self) -> List[VendorConfig]:
        """Get list of enabled vendor configurations."""
        return [
            config for vendor_id, config in VENDOR_REGISTRY.items()
            if self.is_vendor_enabled(vendor_id)
        ]
    
    def get_vendor_instance(self, vendor_id: str) -> Optional[BaseVendorService]:
        """Get a vendor service instance."""
        if vendor_id not in self._vendor_instances:
            config = VENDOR_REGISTRY.get(vendor_id)
            if config and self.is_vendor_enabled(vendor_id):
                instance = self._instantiate_vendor(config)
                if instance:
                    self._vendor_instances[vendor_id] = instance
        return self._vendor_instances.get(vendor_id)
    
    def get_all_instances(self) -> Dict[str, BaseVendorService]:
        """Get all loaded vendor instances."""
        return self._vendor_instances.copy()
    
    def search_all_vendors(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """
        Search across all enabled vendors.
        
        Args:
            query: Search term
            limit: Max results per vendor
            
        Returns:
            Combined list of products from all vendors
        """
        all_products = []
        
        for vendor_id, instance in self._vendor_instances.items():
            try:
                products = instance.search_products(query, limit)
                all_products.extend(products)
                logger.info(f"Got {len(products)} products from {vendor_id}")
            except Exception as e:
                logger.warning(f"Error searching {vendor_id}: {e}")
        
        return all_products
    
    def get_vendor_status(self, vendor_id: str) -> Dict[str, Any]:
        """Get detailed status for a vendor."""
        config = VENDOR_REGISTRY.get(vendor_id)
        if not config:
            return {"error": "Vendor not found"}
        
        instance = self._vendor_instances.get(vendor_id)
        
        return {
            "id": vendor_id,
            "name": config.name,
            "enabled": self.is_vendor_enabled(vendor_id),
            "loaded": instance is not None,
            "configured": instance.is_configured() if instance else False,
            "category": config.category.value,
            "requires_auth": config.requires_auth,
            "env_key": config.env_key,
        }
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status for all registered vendors."""
        return [self.get_vendor_status(vid) for vid in VENDOR_REGISTRY.keys()]
    
    def reload_vendors(self):
        """Reload all vendors (useful after config changes)."""
        self._vendor_instances.clear()
        self._load_vendors()


# Singleton instance
vendor_manager = VendorManager()
