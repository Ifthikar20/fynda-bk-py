"""
Fuzzy Matching Utility

Provides typo-tolerant matching for fashion entity recognition.
Uses Levenshtein edit distance for similarity calculation.
"""

from typing import Optional, Tuple, List
from functools import lru_cache


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein edit distance between two strings.
    
    The edit distance is the minimum number of single-character edits
    (insertions, deletions, substitutions) needed to transform s1 into s2.
    
    Examples:
        >>> levenshtein_distance("nike", "nikee")
        1
        >>> levenshtein_distance("gucci", "guci")
        1
        >>> levenshtein_distance("adidas", "adidas")
        0
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


@lru_cache(maxsize=50000)
def cached_levenshtein(s1: str, s2: str) -> int:
    """Cached version of levenshtein_distance for repeated lookups."""
    return levenshtein_distance(s1, s2)


def fuzzy_match(
    query: str,
    candidates: set,
    max_distance: int = 2,
    min_length: int = 4
) -> Optional[Tuple[str, int]]:
    """
    Find the best fuzzy match for a query in a set of candidates.
    
    Args:
        query: The string to match
        candidates: Set of candidate strings to match against
        max_distance: Maximum allowed edit distance (default: 2)
        min_length: Minimum query length for fuzzy matching (default: 4)
    
    Returns:
        Tuple of (matched_string, edit_distance) or None if no match found
    
    Examples:
        >>> fuzzy_match("nikee", {"nike", "adidas", "puma"})
        ("nike", 1)
        >>> fuzzy_match("guci", {"gucci", "prada", "dior"})
        ("gucci", 1)
    """
    query = query.lower().strip()
    
    # Short queries require exact or near-exact match
    if len(query) < min_length:
        max_distance = min(max_distance, 1)
    
    # For very short queries, only exact match
    if len(query) < 3:
        return (query, 0) if query in candidates else None
    
    best_match = None
    best_distance = max_distance + 1
    
    for candidate in candidates:
        candidate_lower = candidate.lower()
        
        # Exact match - return immediately
        if query == candidate_lower:
            return (candidate, 0)
        
        # Skip if length difference is too large
        if abs(len(query) - len(candidate_lower)) > max_distance:
            continue
        
        distance = cached_levenshtein(query, candidate_lower)
        
        if distance <= max_distance and distance < best_distance:
            best_distance = distance
            best_match = candidate
    
    return (best_match, best_distance) if best_match else None


def fuzzy_match_multi_word(
    query: str,
    candidates: set,
    max_distance: int = 2
) -> Optional[Tuple[str, int]]:
    """
    Fuzzy match for multi-word phrases (like brand names).
    
    Handles cases like:
        - "louis vuitton" matching "louis vitton" (typo)
        - "michael kors" matching "micheal kors" (typo)
        - "off white" matching "offwhite" (spacing)
    
    Args:
        query: Multi-word query to match
        candidates: Set of candidate strings
        max_distance: Maximum allowed total edit distance
    
    Returns:
        Tuple of (matched_string, edit_distance) or None
    """
    query = query.lower().strip()
    
    # Try exact match first
    if query in {c.lower() for c in candidates}:
        for c in candidates:
            if c.lower() == query:
                return (c, 0)
    
    # Try with spaces removed (for "off white" vs "offwhite")
    query_no_space = query.replace(" ", "")
    
    best_match = None
    best_distance = max_distance + 1
    
    for candidate in candidates:
        candidate_lower = candidate.lower()
        candidate_no_space = candidate_lower.replace(" ", "")
        
        # Check both with and without spaces
        for q, c in [(query, candidate_lower), (query_no_space, candidate_no_space)]:
            if abs(len(q) - len(c)) > max_distance:
                continue
                
            distance = cached_levenshtein(q, c)
            
            if distance <= max_distance and distance < best_distance:
                best_distance = distance
                best_match = candidate
    
    return (best_match, best_distance) if best_match else None


def find_entity_in_text(
    text: str,
    entities: set,
    max_distance: int = 1
) -> List[Tuple[str, str, int, int]]:
    """
    Find all entity mentions in a text with fuzzy matching.
    
    Args:
        text: The text to search in
        entities: Set of entities to find
        max_distance: Maximum allowed edit distance
    
    Returns:
        List of tuples: (original_text, matched_entity, start_pos, end_pos)
    
    Example:
        >>> find_entity_in_text("i want nikee sneakers", {"nike", "adidas"})
        [("nikee", "nike", 7, 12)]
    """
    text_lower = text.lower()
    words = text_lower.split()
    results = []
    
    # Single word matching
    current_pos = 0
    for word in words:
        # Clean punctuation
        clean_word = ''.join(c for c in word if c.isalnum())
        
        if clean_word:
            match = fuzzy_match(clean_word, entities, max_distance)
            if match:
                word_start = text_lower.find(word, current_pos)
                results.append((word, match[0], word_start, word_start + len(word)))
        
        current_pos = text_lower.find(word, current_pos) + len(word)
    
    # Multi-word matching (for brand names like "louis vuitton")
    multi_word_entities = {e for e in entities if ' ' in e}
    for entity in multi_word_entities:
        entity_lower = entity.lower()
        if entity_lower in text_lower:
            start = text_lower.find(entity_lower)
            results.append((entity_lower, entity, start, start + len(entity)))
        else:
            # Try fuzzy match for 2-word phrases
            for i, word in enumerate(words[:-1]):
                two_word = f"{words[i]} {words[i+1]}"
                match = fuzzy_match_multi_word(two_word, {entity}, max_distance)
                if match:
                    start = text_lower.find(words[i])
                    end = text_lower.find(words[i+1]) + len(words[i+1])
                    results.append((two_word, match[0], start, end))
    
    return results


def normalize_brand_typos(brand: str, known_brands: set) -> str:
    """
    Normalize common brand typos to canonical form.
    
    Examples:
        >>> normalize_brand_typos("nikee", BRANDS)
        "nike"
        >>> normalize_brand_typos("guchi", BRANDS)
        "gucci"
    """
    match = fuzzy_match(brand, known_brands, max_distance=2)
    return match[0] if match else brand
