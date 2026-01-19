"""
PubMed query builder for Literature Digest.

Constructs PubMed search queries from selected topics and exclusions.
"""

from typing import List, Dict


# Base aging/longevity filter - always included
BASE_AGING_FILTER = (
    '(aging[MeSH] OR "healthy aging"[tiab] OR longevity[tiab] OR healthspan[tiab] '
    'OR "biological age"[tiab] OR lifespan[tiab])'
)


def build_pubmed_query(
    topics: List[Dict],
    exclusions: List[str],
    include_base_filter: bool = True
) -> str:
    """
    Build a PubMed query string from selected topics and exclusions.
    
    Args:
        topics: List of topic dicts with 'name' and 'query_fragment' keys
        exclusions: List of exclusion term strings
        include_base_filter: Whether to include the aging/longevity base filter
    
    Returns:
        Complete PubMed query string
    
    Example:
        >>> topics = [{"name": "CVD", "query_fragment": "cardiovascular[tiab]"}]
        >>> exclusions = ["pediatric", "neonatal"]
        >>> build_pubmed_query(topics, exclusions)
        '(aging[MeSH] OR ...) AND (cardiovascular[tiab]) NOT pediatric[tiab] NOT neonatal[tiab]'
    """
    if not topics:
        # Return a minimal aging query if no topics selected
        return BASE_AGING_FILTER if include_base_filter else ""
    
    # Combine topic fragments with OR
    topic_fragments = [t.get("query_fragment", "") for t in topics if t.get("query_fragment")]
    
    if not topic_fragments:
        return BASE_AGING_FILTER if include_base_filter else ""
    
    # Join topic fragments
    topics_query = " OR ".join(f"({frag})" for frag in topic_fragments)
    
    # Build main query
    if include_base_filter:
        main_query = f"{BASE_AGING_FILTER} AND ({topics_query})"
    else:
        main_query = f"({topics_query})"
    
    # Add exclusion NOT clauses
    if exclusions:
        exclusion_clauses = " ".join(f'NOT {term}[tiab]' for term in exclusions if term)
        main_query = f"{main_query} {exclusion_clauses}"
    
    return main_query


def get_query_summary(
    topics: List[Dict],
    exclusions: List[str]
) -> str:
    """
    Generate a human-readable summary of the query parameters.
    
    Args:
        topics: List of selected topic dicts
        exclusions: List of exclusion terms
    
    Returns:
        Human-readable summary string
    """
    topic_names = [t.get("name", "Unknown") for t in topics]
    
    summary_parts = []
    
    if topic_names:
        summary_parts.append(f"**Topics:** {', '.join(topic_names)}")
    else:
        summary_parts.append("**Topics:** None selected")
    
    if exclusions:
        summary_parts.append(f"**Exclusions:** {', '.join(exclusions)}")
    else:
        summary_parts.append("**Exclusions:** None")
    
    return " | ".join(summary_parts)


def validate_query(query: str) -> Dict:
    """
    Basic validation of a PubMed query string.
    
    Args:
        query: PubMed query string
    
    Returns:
        Dict with 'valid' (bool), 'warnings' (list), 'char_count' (int)
    """
    warnings = []
    
    # Check for balanced parentheses
    if query.count("(") != query.count(")"):
        warnings.append("Unbalanced parentheses in query")
    
    # Check for empty query
    if not query.strip():
        warnings.append("Query is empty")
    
    # Check for very long query (PubMed has limits)
    if len(query) > 4000:
        warnings.append(f"Query is very long ({len(query)} chars) - may hit PubMed limits")
    
    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
        "char_count": len(query)
    }
