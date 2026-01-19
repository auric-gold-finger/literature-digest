"""
PubMed search and fetch utilities for headless execution (non-Streamlit).

Same functionality as pubmed.py but without Streamlit dependencies.
"""

import os
from datetime import datetime, timedelta
from Bio import Entrez
from typing import List, Dict


def get_entrez_email() -> str:
    """Get NCBI email from environment variable."""
    return os.environ.get("NCBI_EMAIL", "user@example.com")


def search_pubmed(query: str, days: int = 7, max_results: int = 200) -> List[str]:
    """
    Search PubMed for articles matching the query published in the last N days.
    
    Args:
        query: PubMed search query string
        days: Number of days to look back
        max_results: Maximum number of PMIDs to return
    
    Returns:
        List of PubMed IDs (PMIDs)
    """
    Entrez.email = get_entrez_email()
    
    since = (datetime.today() - timedelta(days=days)).strftime("%Y/%m/%d")
    full_query = f"{query} AND ({since}[Date - Publication] : 3000[Date - Publication])"
    
    handle = Entrez.esearch(
        db="pubmed",
        term=full_query,
        retmax=max_results,
        sort="relevance"
    )
    record = Entrez.read(handle)
    handle.close()
    
    return record.get("IdList", [])


def fetch_pubmed_details(pmids: List[str]) -> List[Dict]:
    """
    Fetch article details for a list of PubMed IDs.
    
    Args:
        pmids: List of PubMed IDs
    
    Returns:
        List of article dictionaries
    """
    if not pmids:
        return []
    
    Entrez.email = get_entrez_email()
    
    ids = ",".join(pmids)
    handle = Entrez.efetch(db="pubmed", id=ids, rettype="abstract", retmode="xml")
    records = Entrez.read(handle)
    handle.close()
    
    articles = []
    
    for article in records.get("PubmedArticle", []):
        medline = article.get("MedlineCitation", {})
        article_data = medline.get("Article", {})
        
        # Extract title
        title = article_data.get("ArticleTitle", "No title available.")
        if isinstance(title, list):
            title = " ".join(str(t) for t in title)
        title = str(title)
        
        # Extract abstract
        abstract_block = article_data.get("Abstract")
        if abstract_block and "AbstractText" in abstract_block:
            abstract_parts = abstract_block["AbstractText"]
            if isinstance(abstract_parts, list):
                abstract = " ".join(str(part) for part in abstract_parts)
            else:
                abstract = str(abstract_parts)
        else:
            abstract = "No abstract available."
        
        # Extract publication date
        date_field = (
            article_data.get("ArticleDate")
            or medline.get("DateCompleted")
            or medline.get("DateCreated")
            or []
        )
        
        try:
            if date_field and len(date_field) > 0:
                date_obj = date_field[0] if isinstance(date_field, list) else date_field
                year = str(date_obj.get("Year", "2025"))
                month = str(date_obj.get("Month", "01")).zfill(2)
                day = str(date_obj.get("Day", "01")).zfill(2)
                pub_date = f"{year}-{month}-{day}"
            else:
                pub_date = "Unknown"
        except Exception:
            pub_date = "Unknown"
        
        # Extract DOI and PMID
        article_ids = article.get("PubmedData", {}).get("ArticleIdList", [])
        doi = None
        pmid = None
        
        for id_obj in article_ids:
            id_type = getattr(id_obj, "attributes", {}).get("IdType", "")
            if id_type == "doi":
                doi = str(id_obj)
            elif id_type == "pubmed":
                pmid = str(id_obj)
        
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "https://pubmed.ncbi.nlm.nih.gov/"
        
        # Extract authors
        author_list = article_data.get("AuthorList", [])
        authors = []
        for author in author_list[:5]:
            last_name = author.get("LastName", "")
            initials = author.get("Initials", "")
            if last_name:
                authors.append(f"{last_name} {initials}".strip())
        
        if len(author_list) > 5:
            authors.append("et al.")
        
        authors_str = ", ".join(authors) if authors else "Unknown authors"
        
        # Extract journal
        journal_info = article_data.get("Journal", {})
        journal = journal_info.get("Title", "Unknown journal")
        
        articles.append({
            "title": title,
            "abstract": abstract,
            "date": pub_date,
            "doi": doi,
            "pmid": pmid,
            "url": url,
            "authors": authors_str,
            "journal": journal,
            "source": "PubMed"
        })
    
    return articles
