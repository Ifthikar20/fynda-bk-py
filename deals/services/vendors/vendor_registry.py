"""
Vendor Registry

Central configuration for all available vendors.
Toggle vendors on/off via environment variables.

Each entry maps a vendor_id -> VendorConfig, which includes
the Python class to instantiate and whether the vendor is enabled.
"""

from .base_vendor import VendorConfig, VendorCategory


# ─── All available vendors ──────────────────────────────────────
VENDOR_REGISTRY: dict[str, VendorConfig] = {
    
    # ===== MARKETPLACE APIs =====
    
    "amazon": VendorConfig(
        id="amazon",
        name="Amazon",
        service_class="AmazonVendor",
        enabled=True,
        requires_auth=True,
        priority=95,
        category=VendorCategory.MARKETPLACE,
        env_toggle_key="VENDOR_AMAZON",
        description="Amazon via RapidAPI Real-Time Amazon Data",
    ),
    
    "ebay": VendorConfig(
        id="ebay",
        name="eBay",
        service_class="EbayVendor",
        enabled=True,
        requires_auth=True,
        priority=85,
        category=VendorCategory.MARKETPLACE,
        env_toggle_key="VENDOR_EBAY",
        description="eBay Browse API",
    ),
    
    "bestbuy": VendorConfig(
        id="bestbuy",
        name="Best Buy",
        service_class="BestBuyVendor",
        enabled=True,
        requires_auth=True,
        priority=70,
        category=VendorCategory.MARKETPLACE,
        env_toggle_key="VENDOR_BESTBUY",
        description="Best Buy Products API",
    ),
    
    # ===== SOCIAL =====
    
    "facebook": VendorConfig(
        id="facebook",
        name="Facebook Marketplace",
        service_class="FacebookVendor",
        enabled=True,
        requires_auth=False,      # Uses RapidAPI key, falls back to mock
        priority=50,
        category=VendorCategory.SOCIAL,
        env_toggle_key="VENDOR_FACEBOOK",
        description="Facebook Marketplace via RapidAPI",
    ),
    
    # ===== DIRECT / SHOPIFY =====
    
    "shopify": VendorConfig(
        id="shopify",
        name="Shopify",
        service_class="ShopifyVendor",
        enabled=True,
        requires_auth=False,      # Public /products.json
        priority=60,
        category=VendorCategory.DIRECT,
        env_toggle_key="VENDOR_SHOPIFY",
        description="Shopify stores via public /products.json",
    ),
    
    # ===== AFFILIATE NETWORKS (wrapped as single vendor) =====
    
    "affiliates": VendorConfig(
        id="affiliates",
        name="Affiliate Networks",
        service_class="AffiliatesVendor",
        enabled=True,
        requires_auth=True,
        priority=75,
        category=VendorCategory.AFFILIATE,
        env_toggle_key="VENDOR_AFFILIATES",
        description="CJ, Rakuten, ShareASale — ~21,500 merchants",
    ),
    
    # ===== INDIVIDUAL AFFILIATE NETWORKS (disabled — use 'affiliates' above) =====
    
    "rakuten": VendorConfig(
        id="rakuten",
        name="Rakuten",
        service_class="RakutenService",
        enabled=False,  # Managed via AffiliatesVendor
        requires_auth=True,
        priority=80,
        category=VendorCategory.AFFILIATE,
        description="Rakuten Advertising — 2,500+ retailers",
    ),
    
    "cj": VendorConfig(
        id="cj",
        name="CJ Affiliate",
        service_class="CJService",
        enabled=False,  # Managed via AffiliatesVendor
        requires_auth=True,
        priority=75,
        category=VendorCategory.AFFILIATE,
        description="Commission Junction — 3,000+ brands",
    ),
    
    "shareasale": VendorConfig(
        id="shareasale",
        name="ShareASale",
        service_class="ShareASaleService",
        enabled=False,  # Managed via AffiliatesVendor
        requires_auth=True,
        priority=60,
        category=VendorCategory.AFFILIATE,
        description="ShareASale — 16,000+ merchants",
    ),
}


def get_vendor_config(vendor_id: str) -> VendorConfig | None:
    """Get configuration for a specific vendor."""
    return VENDOR_REGISTRY.get(vendor_id)


def get_all_vendors() -> list[VendorConfig]:
    """Get all registered vendors."""
    return list(VENDOR_REGISTRY.values())


def get_vendors_by_category(category: VendorCategory) -> list[VendorConfig]:
    """Get vendors filtered by category."""
    return [v for v in VENDOR_REGISTRY.values() if v.category == category]
