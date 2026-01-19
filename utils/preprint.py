"""
Preprint search utilities for bioRxiv and medRxiv.

Searches preprint servers for cutting-edge longevity research
that hasn't yet been indexed in PubMed.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time


# bioRxiv/medRxiv API endpoint
BIORXIV_API = "https://api.biorxiv.org/details"


def search_preprints(
    query_terms: List[str],
    days_back: int = 14,
    server: str = "medrxiv",
    max_results: int = 100
) -> List[Dict]:
    """
    Search bioRxiv/medRxiv for recent preprints matching query terms.
    
    The API doesn't support complex boolean queries, so we fetch recent
    preprints and filter locally by title/abstract.
    
    Args:
        query_terms: List of terms to search for (OR logic, case-insensitive)
        days_back: How many days back to search
        server: "biorxiv" or "medrxiv"
        max_results: Maximum number of matching preprints to return
    
    Returns:
        List of preprint dicts with keys: doi, title, abstract, authors,
        pub_date, url, server, category
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Normalize query terms for matching
    query_lower = [term.lower() for term in query_terms]
    
    # Fetch preprints page by page
    all_preprints = []
    cursor = 0
    page_size = 100
    
    while len(all_preprints) < max_results:
        url = f"{BIORXIV_API}/{server}/{start_str}/{end_str}/{cursor}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Preprint API error: {e}")
            break
        
        messages = data.get("messages", [])
        if not messages:
            break
        
        # Check if we got results
        total_count = messages[0].get("count", 0) if messages else 0
        if total_count == 0:
            break
        
        # Get the collection of preprints
        collection = data.get("collection", [])
        if not collection:
            break
        
        # Filter by query terms (match in title or abstract)
        for preprint in collection:
            title = preprint.get("title", "").lower()
            abstract = preprint.get("abstract", "").lower()
            
            # Check if any query term matches
            if any(term in title or term in abstract for term in query_lower):
                # Convert to standard format
                formatted = _format_preprint(preprint, server)
                all_preprints.append(formatted)
                
                if len(all_preprints) >= max_results:
                    break
        
        # Move to next page
        cursor += page_size
        
        # Don't exceed the total available
        if cursor >= total_count:
            break
        
        # Rate limiting
        time.sleep(0.5)
    
    return all_preprints


def _format_preprint(preprint: Dict, server: str) -> Dict:
    """Convert bioRxiv/medRxiv API response to standard paper format."""
    doi = preprint.get("doi", "")
    
    # Build author string from author list
    authors = preprint.get("authors", "")
    
    return {
        "doi": doi,
        "pmid": f"preprint_{doi.replace('/', '_')}",  # Fake PMID for dedup
        "title": preprint.get("title", "Untitled"),
        "abstract": preprint.get("abstract", ""),
        "authors": authors,
        "journal": f"{server.capitalize()} (Preprint)",
        "pub_date": preprint.get("date", ""),
        "url": f"https://doi.org/{doi}" if doi else "",
        "server": server,
        "category": preprint.get("category", ""),
        "is_preprint": True
    }


def search_longevity_preprints(days_back: int = 14, max_results: int = 50) -> List[Dict]:
    """
    Search for longevity-related preprints on both bioRxiv and medRxiv.
    
    Uses a curated list of longevity-relevant terms.
    
    Args:
        days_back: How many days back to search
        max_results: Maximum total results (split between servers)
    
    Returns:
        List of preprint dicts, sorted by date (most recent first)
    """
    # Core longevity terms to search for
    longevity_terms = [
        # Interventions
        "rapamycin", "sirolimus", "metformin", "senolytics", "senolytic",
        "dasatinib", "quercetin", "fisetin", "nmn", "nicotinamide riboside",
        "nad+", "spermidine", "alpha-ketoglutarate",
        
        # Mechanisms
        "mtor", "ampk", "sirtuin", "autophagy", "senescence", "senescent cells",
        "telomere", "telomerase", "mitochondrial", "epigenetic clock",
        "biological age", "dna methylation", "cellular reprogramming",
        
        # ITP and key studies
        "interventions testing program", "itp aging", "lifespan extension",
        
        # Other cutting-edge
        "parabiosis", "young blood", "plasma dilution",
        "klotho", "foxo", "yamanaka", "partial reprogramming",
        
        # Longevity general
        "longevity", "healthspan", "lifespan", "aging intervention"
    ]
    
    results_per_server = max_results // 2
    
    # Search both servers
    medrxiv_results = search_preprints(
        longevity_terms,
        days_back=days_back,
        server="medrxiv",
        max_results=results_per_server
    )
    
    biorxiv_results = search_preprints(
        longevity_terms,
        days_back=days_back,
        server="biorxiv",
        max_results=results_per_server
    )
    
    # Combine and sort by date
    all_results = medrxiv_results + biorxiv_results
    all_results.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    
    return all_results[:max_results]


def get_itp_preprints(days_back: int = 30) -> List[Dict]:
    """
    Specifically search for ITP (Interventions Testing Program) preprints.
    
    These always get included regardless of scoring.
    
    Args:
        days_back: How many days back to search
    
    Returns:
        List of ITP-related preprints
    """
    itp_terms = [
        "interventions testing program",
        "itp aging",
        "nia itp",
        "mouse lifespan",
        "lifespan extension"
    ]
    
    # Search both servers for ITP content
    medrxiv = search_preprints(itp_terms, days_back=days_back, server="medrxiv", max_results=20)
    biorxiv = search_preprints(itp_terms, days_back=days_back, server="biorxiv", max_results=20)
    
    return medrxiv + biorxiv
