"""
Build fashion_taxonomy.json from Google Product Taxonomy + Fashionpedia.

Run once:  python deals/services/build_taxonomy.py

Strategy:
  - From Google Product Taxonomy, extract LEAF CATEGORY names (the most 
    specific subcategory) as multi-word phrases. These are precise and 
    cause minimal false positives (e.g. "cake pans & molds", "handbags").
  - From Fashionpedia, extract garment categories and attributes.
  - Add hand-curated single-word terms for common fashion items.
  - DO NOT extract individual words from category names — that causes
    substring collisions (e.g. "glass" blocking "sunglasses").

Outputs:
  - deals/services/fashion_taxonomy.json
"""

import json
import re
import urllib.request
from pathlib import Path

OUTPUT = Path(__file__).parent / "fashion_taxonomy.json"

GOOGLE_URL = "https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt"

# Top-level categories that ARE fashion
FASHION_ROOTS = {"Apparel & Accessories"}

# Sub-branches under fashion to EXCLUDE
EXCLUDE_BRANCHES = {"Costumes & Accessories"}

# Beauty sub-branches to INCLUDE as fashion
BEAUTY_ROOTS = {"Health & Beauty"}
BEAUTY_INCLUDE = {
    "Cosmetics", "Fragrance", "Nail Care", "Skin Care",
    "Hair Care", "Makeup", "Perfume",
}


def fetch_google_taxonomy():
    """Download and parse Google Product Taxonomy into fashion & non-fashion sets."""
    print("Downloading Google Product Taxonomy...")
    req = urllib.request.Request(GOOGLE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        lines = resp.read().decode("utf-8").strip().split("\n")

    fashion = set()
    non_fashion = set()

    for line in lines:
        if line.startswith("#") or not line.strip():
            continue

        match = re.match(r"\d+\s*-\s*(.+)", line)
        if not match:
            continue
        
        path = match.group(1).strip()
        parts = [p.strip() for p in path.split(">")]
        root = parts[0]

        # Get the leaf (most specific) category name
        leaf = parts[-1].strip().lower()

        if root in FASHION_ROOTS:
            if any(excl in path for excl in EXCLUDE_BRANCHES):
                continue
            fashion.add(leaf)
            # Also add parent terms (2+ words only to stay precise)
            for part in parts[1:]:
                term = part.strip().lower()
                if len(term) > 5:
                    fashion.add(term)

        elif root in BEAUTY_ROOTS:
            if any(inc.lower() in path.lower() for inc in BEAUTY_INCLUDE):
                fashion.add(leaf)
        else:
            if len(leaf) > 4:
                non_fashion.add(leaf)
            # Add parent terms for non-fashion (only 6+ chars)
            for part in parts[1:]:
                term = part.strip().lower()
                if len(term) > 5:
                    non_fashion.add(term)

    return fashion, non_fashion


FASHIONPEDIA_URL = "https://raw.githubusercontent.com/KMnP/fashionpedia-api/master/data/demo/category_attributes_descriptions.json"


def fetch_fashionpedia():
    """Download Fashionpedia categories + attributes."""
    print("Downloading Fashionpedia ontology...")
    req = urllib.request.Request(FASHIONPEDIA_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    terms = set()
    for cat in data.get("categories", []):
        for part in cat.get("name", "").split(","):
            t = part.strip().lower()
            if len(t) > 2:
                terms.add(t)
    for attr in data.get("attributes", []):
        for part in attr.get("name", "").split(","):
            t = part.strip().lower()
            if len(t) > 2:
                terms.add(t)
    return terms


# ── Hand-curated fashion terms ──
# These are common single-word terms that are unambiguously fashion
CURATED_FASHION = {
    # Clothing types (single words that appear in product titles)
    "dress", "blouse", "shirt", "tunic", "henley", "polo",
    "sweater", "cardigan", "hoodie", "sweatshirt", "pullover",
    "jacket", "coat", "blazer", "vest", "parka", "windbreaker",
    "trench", "bomber", "puffer", "overcoat",
    "jeans", "pants", "trouser", "legging", "jogger", "chino",
    "shorts", "capri", "culottes", "palazzo",
    "skirt", "pleated",
    "jumpsuit", "romper", "overalls", "playsuit",
    "suit", "tuxedo",
    "lingerie", "bra", "underwear", "panties", "boxers", "briefs",
    "swimsuit", "bikini", "swimwear", "coverup",
    "pajama", "nightgown", "robe", "sleepwear",
    "activewear", "sportswear", "athleisure",
    # Footwear
    "shoe", "sneaker", "boot", "sandal", "heel", "pump",
    "loafer", "oxford", "mule", "espadrille", "slipper", "clog",
    "wedge", "stiletto", "platform", "footwear",
    # Bags
    "bag", "handbag", "purse", "tote", "clutch", "crossbody",
    "backpack", "satchel", "wallet", "wristlet", "duffel",
    # Jewelry & Watches
    "necklace", "bracelet", "earring", "anklet", "pendant",
    "choker", "bangle", "brooch", "charm",
    "watch", "wristwatch",
    # Eyewear
    "sunglasses", "eyeglasses", "aviator", "wayfarer",
    # Headwear
    "hat", "cap", "beanie", "beret", "fedora",
    "visor", "headband", "scrunchie", "turban", "headwrap",
    # Scarves & Wraps
    "scarf", "shawl", "stole", "pashmina", "bandana",
    # Belts & Ties
    "belt", "necktie", "suspender", "cummerbund",
    # Fabrics (unambiguous ones only)
    "cotton", "silk", "linen", "cashmere", "wool", "denim",
    "leather", "suede", "satin", "chiffon", "velvet", "lace",
    "sequin", "embroidered", "knitted", "crochet", "woven",
    "polyester", "nylon", "spandex", "lycra", "rayon", "tweed",
    "flannel", "corduroy", "organza", "tulle", "georgette",
    # Patterns
    "floral", "striped", "plaid", "checkered",
    "paisley", "houndstooth", "argyle", "camouflage",
    # Fashion descriptors
    "outfit", "apparel", "clothing", "garment", "fashion",
    "couture", "designer", "vintage", "retro", "boho", "bohemian",
    "streetwear", "elegant", "chic",
    "oversized", "petite", "menswear", "womenswear",
    # Makeup & Beauty
    "lipstick", "mascara", "concealer", "eyeliner",
    "eyeshadow", "bronzer", "highlighter", "primer",
    "makeup", "cosmetic", "skincare", "serum",
    "moisturizer", "perfume", "cologne", "fragrance",
    "parfum",
    # Multi-word
    "t-shirt", "tank top", "crop top", "bow tie", "flip flop",
    "hair clip", "hair tie", "polka dot", "nail polish",
    "slim fit", "plus size", "ankle boot", "knee boot",
    "messenger bag", "bucket bag", "fanny pack", "hobo bag",
    "shoulder bag", "denim jacket", "leather jacket",
    "animal print", "leopard print", "mini skirt", "maxi skirt",
    "midi skirt", "eau de toilette",
}

# ── Hand-curated non-fashion terms (common single words) ──
CURATED_NON_FASHION = {
    # Food
    "cake", "cookie", "brownie", "chocolate", "candy",
    "recipe", "baking", "frosting", "donut", "pastry",
    "bread", "muffin", "dessert", "snack", "cereal",
    "sauce", "spice", "seasoning", "syrup", "grocery",
    "juice", "smoothie", "yogurt", "cheese", "butter",
    "flour", "sugar", "honey",
    # Kitchen
    "kitchen", "cookware", "bakeware", "utensil", "spatula",
    "skillet", "blender", "toaster", "microwave", "oven",
    "dishwasher", "dinnerware", "saucepan",
    # Electronics
    "laptop", "computer", "monitor", "keyboard", "printer",
    "router", "modem", "charger", "speaker", "headphone",
    "earbud", "tablet", "kindle",
    "gaming", "controller", "console", "playstation", "xbox",
    "nintendo", "camera", "tripod", "drone", "projector",
    "bluetooth",
    # Toys & Baby
    "lego", "puzzle", "stroller", "diaper", "pacifier",
    # Home
    "furniture", "mattress", "pillow", "curtain", "carpet",
    "candle", "planter",
    # Garden
    "garden", "lawn", "fertilizer", "pesticide",
    # Tools
    "drill", "hammer", "wrench", "screwdriver",
    "motor oil", "windshield", "alternator",
    # Cleaning
    "vacuum", "broom", "detergent", "bleach", "disinfectant",
    # Sports equipment
    "treadmill", "dumbbell", "barbell", "kettlebell",
    "basketball", "football", "baseball", "tennis racket",
    # Health
    "vitamin", "supplement", "medicine", "thermometer",
    "syringe", "wheelchair",
    # Office
    "textbook", "notebook", "stationery",
    # Pet
    "aquarium", "fish tank", "bird cage",
    # Plumbing
    "plumbing", "faucet", "toilet",
    "light bulb", "light bulbs",
    # Food items that might not be in taxonomy as standalone
    "apple", "tomato", "onion", "banana", "orange", "cherry",
    "mango", "strawberry", "blueberry", "raspberry", "grape",
    "lemon", "lime", "avocado", "potato", "carrot",
}


def build_taxonomy():
    """Build the merged taxonomy JSON."""
    google_fashion, google_non_fashion = fetch_google_taxonomy()
    fashionpedia = fetch_fashionpedia()

    # Merge fashion: Google taxonomy categories + Fashionpedia + curated
    all_fashion = google_fashion | fashionpedia | CURATED_FASHION
    all_fashion = {t for t in all_fashion if len(t) > 2}

    # Merge non-fashion: Google taxonomy categories + curated
    all_non_fashion = google_non_fashion | CURATED_NON_FASHION
    all_non_fashion = {t for t in all_non_fashion if len(t) > 3}
    
    # Fashion always wins on exact overlaps
    all_non_fashion -= all_fashion
    
    # ── Substring collision cleanup ──
    # Remove non-fashion terms that are substrings of fashion terms.
    # E.g. "glass" is a substring of "sunglasses", "water" of "freshwater".
    # These cause false blocks on fashion products.
    collisions = set()
    for nf in all_non_fashion:
        if len(nf) <= 5:  # Only short terms cause substring problems
            for f in all_fashion:
                if nf != f and nf in f:
                    collisions.add(nf)
                    break
    
    # Also remove known-problematic short words that appear 
    # in common fashion product titles (e.g. "freshwater pearl")
    KNOWN_COLLISIONS = {"water", "light", "stone", "pearl", "coral", "ivory"}
    collisions |= (KNOWN_COLLISIONS & all_non_fashion)
    
    all_non_fashion -= collisions
    if collisions:
        print(f"   Removed {len(collisions)} substring collisions: {sorted(collisions)[:20]}...")

    taxonomy = {
        "_meta": {
            "version": "3.0.0",
            "sources": [
                "Google Product Taxonomy (2021-09-21)",
                "Fashionpedia (KMnP/fashionpedia-api)",
                "Hand-curated extras",
            ],
            "fashion_count": len(all_fashion),
            "non_fashion_count": len(all_non_fashion),
        },
        "fashion_terms": sorted(all_fashion),
        "non_fashion_terms": sorted(all_non_fashion),
    }

    with open(OUTPUT, "w") as f:
        json.dump(taxonomy, f, indent=2)

    print(f"\n✅ Written to {OUTPUT}")
    print(f"   Fashion terms:     {len(all_fashion)}")
    print(f"   Non-fashion terms: {len(all_non_fashion)}")
    
    # ── Sanity checks ──
    print("\n── Sanity checks ──")
    test_titles = [
        ("Women's Velvet Midi Dress", True),
        ("Nike Air Max Running Shoe", True),
        ("Coach Leather Crossbody Bag", True),
        ("Gold Chain Necklace 18K", True),
        ("Ray-Ban Aviator Sunglasses", True),
        ("Levi's 501 Original Jeans", True),
        ("MAC Ruby Woo Lipstick", True),
        ("Casio Digital Watch Black", True),
        ("Dr. Martens Leather Boot", True),
        ("Chanel No. 5 Eau de Parfum", True),
        ("Freshwater Pearl Necklace", True),
        ("Velvet Red Cake Mix 12oz", False),
        ("Organic Fuji Apple 3lb Bag", False),
        ("Apple MacBook Pro 16 inch", False),
        ("Wireless Bluetooth Headphone", False),
        ("LEGO Star Wars Building Set", False),
        ("Dewalt Power Drill Kit 20V", False),
        ("Wilson NBA Basketball", False),
        ("Philips Hue Smart Light Bulb", False),
        ("Dyson V15 Cordless Vacuum", False),
    ]
    
    fashion_set = set(taxonomy["fashion_terms"])
    nf_set = set(taxonomy["non_fashion_terms"])
    
    for title, should_pass in test_titles:
        t = title.lower()
        blocked = any(kw in t for kw in nf_set)
        has_fashion = any(kw in t for kw in fashion_set)
        passes = (not blocked) and has_fashion
        status = "✅" if passes == should_pass else "❌"
        print(f"  {status} {'PASS' if should_pass else 'BLOCK':5s} {title}")
        if passes != should_pass:
            if blocked:
                blockers = [kw for kw in nf_set if kw in t]
                print(f"       Blocked by: {blockers}")
            if not has_fashion:
                print(f"       No fashion term matched")
            if has_fashion and not should_pass:
                matches = [kw for kw in fashion_set if kw in t]
                print(f"       Fashion matches: {matches}")


if __name__ == "__main__":
    build_taxonomy()
