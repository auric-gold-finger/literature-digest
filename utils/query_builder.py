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


def build_intersection_query(
    concept_groups: List[List[str]],
    exclusions: List[str] = None,
    include_base_filter: bool = False
) -> str:
    """
    Build a PubMed query requiring papers to match ALL concept groups (AND logic).
    
    This enables multi-domain intersection searches like:
    "Papers about GLP-1 AND muscle/sarcopenia"
    
    Note: By default, the base aging filter is NOT included because intersection
    queries are already highly focused. Adding "AND aging" would over-restrict
    and miss clinically relevant papers (e.g., GLP-1 + muscle studies that don't
    explicitly mention aging). Set include_base_filter=True if you want the
    additional aging/longevity requirement.
    
    Args:
        concept_groups: List of concept groups, where each group is a list of 
                       query fragments to be ORed together, then ANDed with other groups
        exclusions: List of exclusion term strings
        include_base_filter: Whether to include the aging/longevity base filter (default: False)
    
    Returns:
        Complete PubMed query string with AND between concept groups
    
    Example:
        >>> groups = [
        ...     ['"GLP-1"[tiab]', 'semaglutide[tiab]'],  # Group 1: GLP-1 drugs
        ...     ['sarcopenia[tiab]', '"muscle mass"[tiab]']  # Group 2: Muscle
        ... ]
        >>> build_intersection_query(groups)
        '(("GLP-1"[tiab] OR semaglutide[tiab])) AND ((sarcopenia[tiab] OR "muscle mass"[tiab]))'
    """
    if not concept_groups:
        return BASE_AGING_FILTER if include_base_filter else ""
    
    # Build each concept group with OR logic internally
    group_queries = []
    for group in concept_groups:
        if group:
            # Join terms within a group with OR
            group_query = " OR ".join(f"{term}" for term in group if term)
            if group_query:
                group_queries.append(f"({group_query})")
    
    if not group_queries:
        return BASE_AGING_FILTER if include_base_filter else ""
    
    # Join all groups with AND
    intersection_query = " AND ".join(group_queries)
    
    # Build main query
    if include_base_filter:
        main_query = f"{BASE_AGING_FILTER} AND {intersection_query}"
    else:
        main_query = intersection_query
    
    # Add exclusion NOT clauses
    if exclusions:
        exclusion_clauses = " ".join(f'NOT {term}[tiab]' for term in exclusions if term)
        main_query = f"{main_query} {exclusion_clauses}"
    
    return main_query


# Pre-defined intersection query templates for common multi-domain searches
INTERSECTION_TEMPLATES = {
    "glp1_muscle": {
        "name": "GLP-1 & Muscle/Body Composition",
        "groups": [
            ['"GLP-1"[tiab]', 'semaglutide[tiab]', 'tirzepatide[tiab]', 'liraglutide[tiab]', '"incretin"[tiab]', '"GLP-1 receptor"[tiab]'],
            ['sarcopenia[tiab]', '"muscle mass"[tiab]', '"lean mass"[tiab]', '"body composition"[tiab]', '"lean body mass"[tiab]', '"skeletal muscle"[tiab]', '"fat-free mass"[tiab]']
        ]
    },
    "menopause_bone": {
        "name": "Menopause & Bone Health",
        "groups": [
            ['menopause[tiab]', 'postmenopausal[tiab]', 'perimenopause[tiab]', '"menopausal"[tiab]'],
            ['osteoporosis[tiab]', '"bone density"[tiab]', 'fracture[tiab]', '"bone loss"[tiab]', '"bone mineral"[tiab]', '"bone health"[tiab]']
        ]
    },
    "exercise_cognition": {
        "name": "Exercise & Cognitive Health",
        "groups": [
            ['exercise[tiab]', '"physical activity"[tiab]', '"resistance training"[tiab]', '"aerobic exercise"[tiab]', '"physical exercise"[tiab]'],
            ['cognition[tiab]', '"cognitive decline"[tiab]', 'dementia[tiab]', '"brain health"[tiab]', '"cognitive function"[tiab]', '"memory"[tiab]']
        ]
    },
    "statins_muscle": {
        "name": "Statins & Muscle Effects",
        "groups": [
            ['statin*[tiab]', 'atorvastatin[tiab]', 'rosuvastatin[tiab]', '"HMG-CoA"[tiab]'],
            ['myopathy[tiab]', '"muscle pain"[tiab]', 'rhabdomyolysis[tiab]', '"muscle weakness"[tiab]', 'myalgia[tiab]', '"muscle symptoms"[tiab]']
        ]
    },
    "apob_interventions": {
        "name": "ApoB & Interventions",
        "groups": [
            ['ApoB[tiab]', '"apolipoprotein B"[tiab]', '"LDL-C"[tiab]', '"LDL cholesterol"[tiab]'],
            ['treatment[tiab]', 'intervention[tiab]', 'therapy[tiab]', 'reduction[tiab]', 'lowering[tiab]']
        ]
    },
    "protein_aging": {
        "name": "Protein & Older Adults",
        "groups": [
            ['"protein intake"[tiab]', '"dietary protein"[tiab]', 'leucine[tiab]', '"amino acid"[tiab]', '"protein supplementation"[tiab]'],
            ['"older adults"[tiab]', 'aging[tiab]', 'elderly[tiab]', 'sarcopenia[tiab]', '"aged"[tiab]', '"older people"[tiab]']
        ]
    },
    "sleep_cognition": {
        "name": "Sleep & Cognitive Health",
        "groups": [
            ['sleep[tiab]', '"sleep quality"[tiab]', '"sleep duration"[tiab]', 'insomnia[tiab]', '"sleep disorders"[tiab]'],
            ['cognition[tiab]', '"cognitive function"[tiab]', 'dementia[tiab]', '"Alzheimer"[tiab]', '"cognitive decline"[tiab]', '"memory"[tiab]']
        ]
    },
    "vo2max_mortality": {
        "name": "Cardiorespiratory Fitness & Mortality",
        "groups": [
            ['VO2[tiab]', '"cardiorespiratory fitness"[tiab]', '"aerobic capacity"[tiab]', '"VO2max"[tiab]', '"VO2 max"[tiab]', '"peak oxygen"[tiab]'],
            ['mortality[tiab]', 'survival[tiab]', '"all-cause mortality"[tiab]', 'longevity[tiab]', '"death"[tiab]']
        ]
    },
    "hrt_cardiovascular": {
        "name": "HRT & Cardiovascular Risk",
        "groups": [
            ['"hormone therapy"[tiab]', '"hormone replacement"[tiab]', 'estrogen[tiab]', '"menopausal hormone"[tiab]', 'HRT[tiab]'],
            ['"cardiovascular"[tiab]', '"heart disease"[tiab]', '"coronary"[tiab]', '"CVD"[tiab]', 'stroke[tiab]', '"cardiovascular risk"[tiab]']
        ]
    },
    "zone2_mitochondria": {
        "name": "Endurance Training & Mitochondria",
        "groups": [
            ['"endurance training"[tiab]', '"aerobic training"[tiab]', '"zone 2"[tiab]', '"endurance exercise"[tiab]', '"aerobic exercise"[tiab]'],
            ['mitochondri*[tiab]', '"mitochondrial function"[tiab]', '"mitochondrial biogenesis"[tiab]', '"oxidative capacity"[tiab]']
        ]
    }
}


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
