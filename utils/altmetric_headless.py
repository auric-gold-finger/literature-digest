"""
Altmetric API utilities for headless execution (non-Streamlit).

Same functionality as altmetric.py but without Streamlit caching.
"""

import requests
from typing import List, Dict, Optional


def get_altmetric_by_doi(doi: Optional[str]) -> Dict:
    """
    Fetch Altmetric data for a paper by its DOI.
    
    Args:
        doi: Digital Object Identifier for the paper
    
    Returns:
        Dictionary with score, twitter count, and news count
    """
    default = {"score": 0, "twitter": 0, "news": 0}
    
    if not doi:
        return default
    
    try:
        url = f"https://api.altmetric.com/v1/doi/{doi}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "score": data.get("score", 0),
                "twitter": data.get("cited_by_tweeters_count", 0),
                "news": data.get("cited_by_msm_count", 0)
            }
        else:
            return default
            
    except Exception:
        return default


def enrich_papers_with_altmetric(papers: List[Dict], verbose: bool = False) -> List[Dict]:
    """
    Add Altmetric data to a list of papers.
    
    Args:
        papers: List of paper dictionaries (must have 'doi' key)
        verbose: Print progress information
    
    Returns:
        Papers list with 'altmetric' key added to each paper
    """
    total = len(papers)
    
    for i, paper in enumerate(papers):
        paper["altmetric"] = get_altmetric_by_doi(paper.get("doi"))
        
        if verbose and (i + 1) % 20 == 0:
            print(f"Altmetric enrichment: {i + 1}/{total}")
    
    return papers
