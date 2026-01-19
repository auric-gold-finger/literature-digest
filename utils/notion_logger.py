"""
Notion database logging for Literature Digest.

Logs posted papers to a Notion database for persistence and review.
"""

import os
from datetime import datetime
from typing import List, Dict
from notion_client import Client


def get_notion_client() -> Client:
    """Get authenticated Notion client."""
    api_key = os.environ.get("NOTION_API_KEY", "")
    if not api_key:
        raise ValueError("NOTION_API_KEY environment variable not set")
    return Client(auth=api_key)


def get_database_id() -> str:
    """Get Notion database ID from environment."""
    db_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not db_id:
        raise ValueError("NOTION_DATABASE_ID environment variable not set")
    return db_id


def log_paper(client: Client, database_id: str, paper: Dict) -> bool:
    """
    Log a single paper to Notion database.
    
    Args:
        client: Notion client instance
        database_id: Target database ID
        paper: Paper dict with all fields
    
    Returns:
        True if successful, False otherwise
    """
    # Extract paper fields
    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "Unknown")
    authors = paper.get("authors", "Unknown")
    pmid = paper.get("pmid", "")
    doi = paper.get("doi", "")
    url = paper.get("url", "")
    pub_date = paper.get("date", "")
    abstract = paper.get("abstract", "")
    
    # Scores
    relevance = paper.get("triage_score", -1)
    evidence = paper.get("evidence_score", -1)
    actionability = paper.get("actionability_score", -1)
    altmetric = paper.get("altmetric", {}).get("score", 0)
    whitelisted = paper.get("whitelisted", False)
    
    # Combined score for sorting
    combined_score = relevance + evidence + actionability if relevance >= 0 else 0
    
    try:
        client.pages.create(
            parent={"database_id": database_id},
            properties={
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": title[:2000]  # Notion title limit
                            }
                        }
                    ]
                },
                "Journal": {
                    "rich_text": [
                        {
                            "text": {
                                "content": journal[:2000]
                            }
                        }
                    ]
                },
                "Authors": {
                    "rich_text": [
                        {
                            "text": {
                                "content": authors[:2000]
                            }
                        }
                    ]
                },
                "PMID": {
                    "rich_text": [
                        {
                            "text": {
                                "content": pmid or ""
                            }
                        }
                    ]
                },
                "DOI": {
                    "rich_text": [
                        {
                            "text": {
                                "content": doi or ""
                            }
                        }
                    ]
                },
                "URL": {
                    "url": url if url else None
                },
                "Publication Date": {
                    "rich_text": [
                        {
                            "text": {
                                "content": pub_date or ""
                            }
                        }
                    ]
                },
                "Date Added": {
                    "date": {
                        "start": datetime.now().strftime("%Y-%m-%d")
                    }
                },
                "Relevance": {
                    "number": relevance if relevance >= 0 else None
                },
                "Evidence": {
                    "number": evidence if evidence >= 0 else None
                },
                "Actionability": {
                    "number": actionability if actionability >= 0 else None
                },
                "Combined Score": {
                    "number": combined_score if combined_score > 0 else None
                },
                "Altmetric": {
                    "number": altmetric if altmetric > 0 else None
                },
                "Priority Author": {
                    "checkbox": whitelisted
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "Abstract"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": abstract[:2000] if abstract else "No abstract available."
                                }
                            }
                        ]
                    }
                }
            ]
        )
        return True
    except Exception as e:
        print(f"Failed to log paper to Notion: {e}")
        return False


def log_papers(papers: List[Dict]) -> Dict[str, int]:
    """
    Log multiple papers to Notion database.
    
    Args:
        papers: List of paper dicts to log
    
    Returns:
        Dict with 'success' and 'failed' counts
    """
    client = get_notion_client()
    database_id = get_database_id()
    
    results = {"success": 0, "failed": 0}
    
    for paper in papers:
        if log_paper(client, database_id, paper):
            results["success"] += 1
        else:
            results["failed"] += 1
    
    return results


def check_duplicate(client: Client, database_id: str, pmid: str) -> bool:
    """
    Check if a paper with this PMID already exists in the database.
    
    Args:
        client: Notion client instance
        database_id: Target database ID
        pmid: PubMed ID to check
    
    Returns:
        True if duplicate exists, False otherwise
    """
    if not pmid:
        return False
    
    try:
        response = client.databases.query(
            database_id=database_id,
            filter={
                "property": "PMID",
                "rich_text": {
                    "equals": pmid
                }
            }
        )
        return len(response.get("results", [])) > 0
    except Exception:
        return False


def log_papers_deduplicated(papers: List[Dict]) -> Dict[str, int]:
    """
    Log papers to Notion, skipping duplicates based on PMID.
    
    Args:
        papers: List of paper dicts to log
    
    Returns:
        Dict with 'success', 'failed', and 'skipped' counts
    """
    client = get_notion_client()
    database_id = get_database_id()
    
    results = {"success": 0, "failed": 0, "skipped": 0}
    
    for paper in papers:
        pmid = paper.get("pmid", "")
        
        # Check for duplicates
        if check_duplicate(client, database_id, pmid):
            results["skipped"] += 1
            continue
        
        if log_paper(client, database_id, paper):
            results["success"] += 1
        else:
            results["failed"] += 1
    
    return results


def get_posted_pmids(days_back: int = 14) -> set:
    """
    Get PMIDs of papers posted to Notion in the last N days.
    Used for Slack deduplication—don't repost papers already in the digest.
    
    Args:
        days_back: How many days to look back (default 14)
    
    Returns:
        Set of PMID strings
    """
    try:
        client = get_notion_client()
        database_id = get_database_id()
        
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        response = client.databases.query(
            database_id=database_id,
            filter={
                "property": "Date Added",
                "date": {
                    "on_or_after": cutoff_date
                }
            }
        )
        
        pmids = set()
        for page in response.get("results", []):
            pmid_prop = page.get("properties", {}).get("PMID", {})
            rich_text = pmid_prop.get("rich_text", [])
            if rich_text:
                pmid = rich_text[0].get("text", {}).get("content", "")
                if pmid:
                    pmids.add(pmid)
        
        return pmids
        
    except Exception as e:
        print(f"Failed to fetch posted PMIDs from Notion: {e}")
        return set()  # On error, don't filter anything
