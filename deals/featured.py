"""
Featured Content Configuration

Curated brands, categories, and trending terms served via the Featured Content API.
All brand and category data that appears on the landing page comes from here —
nothing is hardcoded in the frontend.
"""

# =============================================================================
# FEATURED BRANDS (displayed on the homepage "Explore Brands" section)
# =============================================================================
FEATURED_BRANDS = [
    {"name": "Nike", "initial": "N", "category": "Sportswear"},
    {"name": "Gucci", "initial": "G", "category": "Luxury Fashion"},
    {"name": "Zara", "initial": "Z", "category": "Fast Fashion"},
    {"name": "Louis Vuitton", "initial": "LV", "category": "Luxury"},
    {"name": "Adidas", "initial": "A", "category": "Sportswear"},
    {"name": "H&M", "initial": "H", "category": "Fashion"},
    {"name": "Sephora", "initial": "S", "category": "Beauty"},
    {"name": "Lululemon", "initial": "L", "category": "Activewear"},
]

# =============================================================================
# SEARCH PROMPTS (animated placeholder text in the search bar)
# =============================================================================
SEARCH_PROMPTS = [
    "Find me a vintage leather jacket under $200...",
    "Show Nike Air Jordan 1 best deals...",
    "Summer dress for beach vacation...",
    "Designer handbag with best discount...",
    "Wireless headphones with noise canceling...",
]

# =============================================================================
# QUICK SUGGESTIONS (shown below the search bar)
# =============================================================================
QUICK_SUGGESTIONS = [
    "Vintage jacket",
    "Running shoes",
    "Designer bag",
    "Summer dress",
]

# =============================================================================
# CATEGORY DATA (used on category pages: /shop/women, /shop/men, etc.)
# =============================================================================
CATEGORIES = {
    "women": {
        "title": "Women's Fashion",
        "description": "Discover the latest trends in women's clothing, shoes, and accessories at the best prices.",
        "subcategories": ["All", "Dresses", "Tops", "Pants", "Shoes", "Bags", "Jewelry", "Activewear"],
        "brands": [
            {"name": "Nike", "logo": "N"},
            {"name": "Zara", "logo": "Z"},
            {"name": "H&M", "logo": "H"},
            {"name": "Lululemon", "logo": "L"},
            {"name": "Adidas", "logo": "A"},
            {"name": "Nordstrom", "logo": "N"},
        ],
        "trending": [
            {"name": "Summer Dresses", "query": "women summer dress"},
            {"name": "Designer Bags", "query": "women designer bag"},
            {"name": "Sneakers", "query": "women sneakers"},
            {"name": "Sunglasses", "query": "women sunglasses"},
        ],
        "search_query": "women fashion clothing",
    },
    "men": {
        "title": "Men's Fashion",
        "description": "Shop men's clothing, shoes, and accessories from top brands at unbeatable prices.",
        "subcategories": ["All", "Shirts", "Pants", "Suits", "Shoes", "Watches", "Accessories", "Athleisure"],
        "brands": [
            {"name": "Nike", "logo": "N"},
            {"name": "Ralph Lauren", "logo": "RL"},
            {"name": "Uniqlo", "logo": "U"},
            {"name": "Adidas", "logo": "A"},
            {"name": "Levi's", "logo": "L"},
            {"name": "Hugo Boss", "logo": "HB"},
        ],
        "trending": [
            {"name": "Sneakers", "query": "men sneakers"},
            {"name": "Watches", "query": "men watches"},
            {"name": "Jackets", "query": "men jackets"},
            {"name": "Sunglasses", "query": "men sunglasses"},
        ],
        "search_query": "men fashion clothing",
    },
    "home": {
        "title": "Home & Living",
        "description": "Find amazing deals on furniture, decor, kitchen essentials, and everything for your home.",
        "subcategories": ["All", "Furniture", "Decor", "Kitchen", "Bedding", "Lighting", "Storage", "Outdoor"],
        "brands": [
            {"name": "IKEA", "logo": "IK"},
            {"name": "West Elm", "logo": "WE"},
            {"name": "Crate & Barrel", "logo": "CB"},
            {"name": "Pottery Barn", "logo": "PB"},
            {"name": "Wayfair", "logo": "W"},
            {"name": "Target", "logo": "T"},
        ],
        "trending": [
            {"name": "Bedding Sets", "query": "bedding sets"},
            {"name": "Coffee Makers", "query": "coffee maker"},
            {"name": "Rugs", "query": "area rug"},
            {"name": "Lamps", "query": "modern lamp"},
        ],
        "search_query": "home decor furniture",
    },
    "beauty": {
        "title": "Beauty & Personal Care",
        "description": "Skincare, makeup, haircare, and wellness products from top beauty brands.",
        "subcategories": ["All", "Skincare", "Makeup", "Haircare", "Fragrance", "Wellness", "Tools", "Sets"],
        "brands": [
            {"name": "Sephora", "logo": "S"},
            {"name": "Ulta", "logo": "U"},
            {"name": "Glossier", "logo": "G"},
            {"name": "Fenty", "logo": "F"},
            {"name": "Drunk Elephant", "logo": "DE"},
            {"name": "The Ordinary", "logo": "TO"},
        ],
        "trending": [
            {"name": "Serums", "query": "skincare serum"},
            {"name": "Perfumes", "query": "perfume deals"},
            {"name": "Lip Products", "query": "lip gloss lipstick"},
            {"name": "Hair Tools", "query": "hair dryer straightener"},
        ],
        "search_query": "beauty skincare makeup",
    },
}
