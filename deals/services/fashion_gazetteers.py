"""
Fashion Gazetteers

Hardcoded lists of fashion entities for entity recognition.
These lists are used for fast lookup during query parsing.

Entity Types:
- BRANDS: Fashion brands and designers
- COLORS: Color names and variations  
- CATEGORIES: Product categories (clothing, shoes, etc.)
- STYLES: Style descriptors (casual, formal, etc.)
- MATERIALS: Fabric and material types
- GENDER: Gender-specific keywords
"""

# =============================================================================
# FASHION BRANDS (200+ popular brands)
# =============================================================================
BRANDS = {
    # Luxury/Designer
    "gucci", "prada", "louis vuitton", "lv", "chanel", "dior", "christian dior",
    "hermes", "hermès", "balenciaga", "versace", "fendi", "givenchy", "burberry",
    "valentino", "dolce gabbana", "dolce & gabbana", "d&g", "armani", "giorgio armani",
    "emporio armani", "ysl", "saint laurent", "yves saint laurent", "bottega veneta",
    "celine", "céline", "loewe", "alexander mcqueen", "mcqueen", "stella mccartney",
    "marc jacobs", "tom ford", "off white", "off-white", "maison margiela", "margiela",
    "balmain", "lanvin", "moncler", "kenzo", "acne studios", "isabel marant",
    "jacquemus", "the row", "rick owens",
    
    # Sportswear/Athletic
    "nike", "adidas", "puma", "reebok", "under armour", "new balance", "asics",
    "fila", "champion", "jordan", "air jordan", "converse", "vans", "skechers",
    "brooks", "saucony", "mizuno", "lululemon", "athleta", "gymshark",
    
    # Fast Fashion
    "zara", "h&m", "hm", "uniqlo", "forever 21", "forever21", "topshop", "asos",
    "primark", "shein", "boohoo", "plt", "prettylittlething", "fashion nova",
    "fashionnova", "missguided", "nasty gal", "romwe", "mango", "bershka",
    "pull&bear", "stradivarius", "massimo dutti",
    
    # Contemporary/Mid-range
    "coach", "michael kors", "mk", "kate spade", "tory burch", "ralph lauren",
    "polo ralph lauren", "tommy hilfiger", "calvin klein", "ck", "dkny",
    "guess", "lacoste", "hugo boss", "boss", "ted baker", "all saints",
    "theory", "club monaco", "banana republic", "j crew", "j.crew",
    "anthropologie", "free people", "urban outfitters", "uo",
    
    # Denim
    "levis", "levi's", "wrangler", "lee", "true religion", "seven for all mankind",
    "7 for all mankind", "ag jeans", "citizens of humanity", "paige", "mother",
    "frame", "hudson", "dl1961", "joes jeans", "joe's jeans", "diesel",
    
    # Outdoor/Workwear
    "north face", "the north face", "patagonia", "columbia", "timberland",
    "carhartt", "dickies", "helly hansen", "arc'teryx", "arcteryx",
    "canada goose", "woolrich", "fjallraven",
    
    # Shoes
    "doc martens", "dr martens", "birkenstock", "crocs", "ugg", "uggs",
    "clarks", "steve madden", "sam edelman", "stuart weitzman", "jimmy choo",
    "christian louboutin", "louboutin", "manolo blahnik", "salvatore ferragamo",
    "ferragamo", "tod's", "tods", "cole haan", "ecco", "merrell",
    "golden goose", "common projects", "axel arigato",
    
    # Accessories/Bags
    "ray ban", "ray-ban", "rayban", "oakley", "fossil", "swatch", "casio",
    "g-shock", "seiko", "tissot", "longines", "omega", "rolex", "tag heuer",
    "herschel", "fjällräven", "tumi", "samsonite", "longchamp", "mcm",
    
    # Jewelry
    "pandora", "swarovski", "tiffany", "tiffany & co", "cartier", "bulgari",
    "david yurman", "kendra scott", "mejuri", "anna beck",
    
    # Streetwear
    "supreme", "bape", "a bathing ape", "stussy", "palace", "kith",
    "fear of god", "fog", "essentials", "yeezy", "travis scott", "golf wang",
    "anti social social club", "vlone", "heron preston", "ambush",
}

# Brand aliases (maps variations to canonical names)
BRAND_ALIASES = {
    "lv": "louis vuitton",
    "hm": "h&m",
    "ck": "calvin klein",
    "mk": "michael kors",
    "uo": "urban outfitters",
    "fog": "fear of god",
    "d&g": "dolce & gabbana",
    "ysl": "saint laurent",
    "mcqueen": "alexander mcqueen",
    "margiela": "maison margiela",
    "louboutin": "christian louboutin",
    "dr martens": "doc martens",
    "ray-ban": "ray ban",
    "rayban": "ray ban",
    "levis": "levi's",
    "uggs": "ugg",
    "the north face": "north face",
}

# =============================================================================
# COLORS
# =============================================================================
COLORS = {
    # Basic
    "black", "white", "gray", "grey", "silver",
    "red", "blue", "green", "yellow", "orange", "purple", "pink",
    "brown", "beige", "tan", "cream", "ivory", "nude",
    
    # Shades of Blue
    "navy", "navy blue", "royal blue", "baby blue", "light blue", "dark blue",
    "sky blue", "teal", "turquoise", "aqua", "cobalt", "indigo", "denim",
    
    # Shades of Green
    "olive", "sage", "mint", "emerald", "forest green", "dark green",
    "lime", "neon green", "seafoam", "hunter green", "khaki",
    
    # Shades of Red/Pink
    "burgundy", "maroon", "wine", "crimson", "coral", "salmon", "rose",
    "blush", "hot pink", "fuchsia", "magenta", "mauve", "dusty rose",
    
    # Shades of Brown
    "camel", "cognac", "chocolate", "espresso", "rust", "terracotta",
    "taupe", "mocha", "chestnut", "sienna",
    
    # Shades of Purple
    "lavender", "lilac", "plum", "violet", "mauve", "orchid",
    
    # Shades of Yellow/Orange
    "gold", "golden", "mustard", "amber", "peach", "apricot",
    
    # Multi/Pattern
    "multi", "multicolor", "rainbow", "tie dye", "tie-dye",
    "camo", "camouflage", "leopard", "cheetah", "zebra", "snake",
    "floral", "striped", "plaid", "checkered", "polka dot",
}

# Color aliases
COLOR_ALIASES = {
    "grey": "gray",
    "nude": "beige",
    "navy blue": "navy",
    "camo": "camouflage",
}

# =============================================================================
# CATEGORIES (Product Types)
# =============================================================================
CATEGORIES = {
    # Tops
    "shirt", "shirts", "t-shirt", "tshirt", "t shirt", "tee", "tees",
    "blouse", "blouses", "top", "tops", "tank", "tank top", "tanktop",
    "sweater", "sweaters", "pullover", "cardigan", "hoodie", "hoodies",
    "sweatshirt", "sweatshirts", "polo", "polos", "henley",
    "crop top", "croptop", "bodysuit", "camisole", "cami",
    "turtleneck", "mock neck", "v-neck", "vneck",
    
    # Bottoms
    "pants", "trousers", "jeans", "denim", "shorts", "skirt", "skirts",
    "leggings", "joggers", "sweatpants", "chinos", "khakis",
    "culottes", "palazzo", "cargo", "cargo pants",
    
    # Dresses
    "dress", "dresses", "maxi dress", "midi dress", "mini dress",
    "gown", "gowns", "romper", "jumpsuit", "jumpsuits", "playsuit",
    "sundress", "cocktail dress", "evening dress",
    
    # Outerwear
    "jacket", "jackets", "coat", "coats", "blazer", "blazers",
    "bomber", "bomber jacket", "leather jacket", "denim jacket",
    "parka", "puffer", "puffer jacket", "down jacket", "windbreaker",
    "trench", "trench coat", "peacoat", "overcoat", "cape", "poncho",
    "vest", "vests", "gilet",
    
    # Suits & Formal
    "suit", "suits", "tuxedo", "tux", "waistcoat",
    
    # Shoes
    "shoes", "shoe", "sneakers", "sneaker", "trainers", "kicks",
    "boots", "boot", "ankle boots", "booties", "chelsea boots",
    "heels", "high heels", "pumps", "stilettos", "wedges",
    "sandals", "sandal", "flip flops", "slides", "slippers",
    "loafers", "oxfords", "brogues", "derbys", "flats", "ballet flats",
    "mules", "clogs", "espadrilles", "platforms",
    "running shoes", "running", "basketball shoes", "basketball",
    
    # Bags
    "bag", "bags", "handbag", "handbags", "purse", "purses",
    "tote", "totes", "tote bag", "clutch", "clutches",
    "crossbody", "crossbody bag", "shoulder bag", "satchel",
    "backpack", "backpacks", "duffel", "duffle", "messenger bag",
    "fanny pack", "belt bag", "wallet", "wallets", "card holder",
    
    # Accessories
    "hat", "hats", "cap", "caps", "beanie", "beanies", "fedora",
    "scarf", "scarves", "belt", "belts", "tie", "ties", "bow tie",
    "sunglasses", "glasses", "eyewear",
    "watch", "watches", "jewelry", "necklace", "bracelet", "ring", "earrings",
    "gloves", "socks", "umbrella",
    
    # Underwear/Loungewear
    "underwear", "boxers", "briefs", "bra", "bras", "lingerie",
    "pajamas", "pyjamas", "pjs", "robe", "slippers", "loungewear",
    "swimsuit", "swimwear", "bikini", "one piece", "swim trunks",
    
    # Activewear
    "activewear", "sportswear", "workout", "gym", "athletic",
    "sports bra", "yoga pants", "yoga", "running shorts",
}

# Category normalization (maps to canonical form)
CATEGORY_NORMALIZATION = {
    "tshirt": "t-shirt",
    "t shirt": "t-shirt",
    "tee": "t-shirt",
    "tees": "t-shirt",
    "trainers": "sneakers",
    "kicks": "sneakers",
    "purse": "handbag",
    "purses": "handbags",
    "pyjamas": "pajamas",
    "pjs": "pajamas",
}

# =============================================================================
# STYLES
# =============================================================================
STYLES = {
    # Fit
    "slim", "slim fit", "skinny", "regular", "regular fit", "loose", "loose fit",
    "relaxed", "relaxed fit", "oversized", "fitted", "tailored",
    "straight", "straight fit", "straight leg", "bootcut", "wide leg", "flare",
    "cropped", "petite", "tall", "plus size", "plus",
    
    # Style Types
    "casual", "formal", "smart casual", "business casual", "dressy",
    "sporty", "athletic", "bohemian", "boho", "vintage", "retro",
    "minimalist", "classic", "modern", "contemporary", "trendy",
    "streetwear", "street style", "preppy", "chic", "elegant",
    "romantic", "edgy", "punk", "goth", "gothic", "grunge",
    "y2k", "90s", "80s", "70s",
    
    # Descriptors
    "high waist", "high waisted", "high rise", "low rise", "mid rise",
    "long sleeve", "short sleeve", "sleeveless", "cap sleeve",
    "v neck", "v-neck", "crew neck", "round neck", "scoop neck",
    "button down", "button up", "zip up", "zip-up", "pullover",
    "distressed", "ripped", "raw hem", "faded", "washed",
    "embroidered", "printed", "graphic", "logo", "plain", "solid",
}

# =============================================================================
# MATERIALS
# =============================================================================
MATERIALS = {
    # Natural Fabrics
    "cotton", "100% cotton", "organic cotton", "linen", "silk", "wool",
    "cashmere", "merino", "merino wool", "alpaca", "mohair",
    "leather", "genuine leather", "real leather", "suede",
    "denim", "canvas", "tweed", "velvet", "satin", "chiffon",
    "lace", "crochet", "knit", "knitted", "woven",
    
    # Synthetic Fabrics
    "polyester", "nylon", "spandex", "lycra", "elastane",
    "rayon", "viscose", "modal", "acrylic", "fleece", "jersey",
    "mesh", "microfiber",
    
    # Leather alternatives
    "faux leather", "vegan leather", "pleather", "pu leather",
    "faux suede", "faux fur", "synthetic",
    
    # Special
    "waterproof", "water resistant", "breathable", "stretch",
    "recycled", "sustainable", "eco friendly", "organic",
}

# =============================================================================
# GENDER
# =============================================================================
GENDER = {
    "women", "womens", "women's", "woman", "ladies", "female",
    "men", "mens", "men's", "man", "male", "guys",
    "unisex", "gender neutral",
    "kids", "children", "boys", "girls", "toddler", "baby", "infant",
    "teen", "teens", "junior", "juniors",
}

# Gender normalization
GENDER_NORMALIZATION = {
    "womens": "women",
    "women's": "women",
    "woman": "women",
    "ladies": "women",
    "female": "women",
    "mens": "men",
    "men's": "men",
    "man": "men",
    "male": "men",
    "guys": "men",
    "children": "kids",
    "boys": "kids",
    "girls": "kids",
    "teen": "teens",
    "junior": "juniors",
}

# =============================================================================
# SIZE KEYWORDS
# =============================================================================
SIZES = {
    # Letter sizes
    "xs", "extra small", "s", "small", "m", "medium", "l", "large",
    "xl", "extra large", "xxl", "2xl", "xxxl", "3xl",
    
    # Number sizes (women's US)
    "size 0", "size 2", "size 4", "size 6", "size 8", "size 10",
    "size 12", "size 14", "size 16",
    
    # Other
    "one size", "os", "free size", "plus size", "petite",
}

# =============================================================================
# PRICE MODIFIERS
# =============================================================================
PRICE_MODIFIERS = {
    "cheap", "affordable", "budget", "inexpensive", "low cost",
    "sale", "discount", "discounted", "clearance", "outlet",
    "luxury", "premium", "high end", "designer", "expensive",
    "mid range", "mid-range", "moderate",
}

# =============================================================================
# OCCASION KEYWORDS
# =============================================================================
OCCASIONS = {
    "wedding", "wedding guest", "bridal", "bridesmaid", "prom",
    "party", "cocktail", "night out", "date night", "club",
    "work", "office", "professional", "interview",
    "casual", "everyday", "weekend", "lounge", "home",
    "vacation", "travel", "beach", "resort", "festival",
    "gym", "workout", "running", "yoga", "hiking", "outdoor",
    "formal", "black tie", "gala", "red carpet",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_entities():
    """Return all entities as a dictionary for easy lookup."""
    return {
        "brands": BRANDS,
        "colors": COLORS,
        "categories": CATEGORIES,
        "styles": STYLES,
        "materials": MATERIALS,
        "gender": GENDER,
        "sizes": SIZES,
        "price_modifiers": PRICE_MODIFIERS,
        "occasions": OCCASIONS,
    }


def get_brand_canonical(brand: str) -> str:
    """Get canonical brand name from alias."""
    brand_lower = brand.lower()
    return BRAND_ALIASES.get(brand_lower, brand_lower)


def get_color_canonical(color: str) -> str:
    """Get canonical color name from alias."""
    color_lower = color.lower()
    return COLOR_ALIASES.get(color_lower, color_lower)


def get_category_canonical(category: str) -> str:
    """Get canonical category name."""
    category_lower = category.lower()
    return CATEGORY_NORMALIZATION.get(category_lower, category_lower)


def get_gender_canonical(gender: str) -> str:
    """Get canonical gender term."""
    gender_lower = gender.lower()
    return GENDER_NORMALIZATION.get(gender_lower, gender_lower)
