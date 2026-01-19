#!/usr/bin/env python3
"""
Daily Literature Digest - Automated paper discovery and Slack posting.

This script runs as a scheduled job (via GitHub Actions) to:
1. Search PubMed for recent longevity research papers
2. Enrich with Altmetric attention scores
3. Score papers with Gemini AI for relevance, evidence, and actionability
4. Post top 5 papers to Slack
5. Log papers to Notion database

Environment variables required:
- NCBI_EMAIL: Email for PubMed API
- GEMINI_API_KEY: Google Gemini API key
- SLACK_WEBHOOK_URL: Slack incoming webhook URL
- NOTION_API_KEY: Notion integration token
- NOTION_DATABASE_ID: Notion database ID

Optional (for Google Sheets config):
- GSHEET_CONFIG_ID: Google Sheet ID for remote config
- GSHEET_TAB_TOPICS, GSHEET_TAB_WHITELIST, etc.
"""

import sys
import traceback

# Import headless utilities (no Streamlit dependencies)
from utils.config_loader import load_topics, load_whitelist, load_blacklist, load_exclusions
from utils.query_builder import build_pubmed_query
from utils.pubmed_headless import search_pubmed, fetch_pubmed_details
from utils.altmetric_headless import enrich_papers_with_altmetric
from utils.gemini_headless import batch_triage_papers
from utils.slack_poster import post_digest, post_error, post_no_papers_message
from utils.notion_logger import log_papers_deduplicated


# Configuration
DAYS_BACK = 7           # How many days to search
MAX_RESULTS = 200       # Max papers to fetch from PubMed
TOP_N_PAPERS = 5        # How many papers to post to Slack
MIN_COMBINED_SCORE = 15 # Minimum combined score (rel + evid + action) to include


def calculate_combined_score(paper: dict) -> int:
    """Calculate combined score from three dimensions."""
    rel = paper.get("triage_score", -1)
    evid = paper.get("evidence_score", -1)
    action = paper.get("actionability_score", -1)
    
    if rel < 0 or evid < 0 or action < 0:
        return 0
    
    return rel + evid + action


def run_daily_digest(verbose: bool = True) -> bool:
    """
    Run the complete daily digest pipeline.
    
    Args:
        verbose: Print progress information
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Step 1: Load configuration
        if verbose:
            print("Loading configuration...")
        
        topics = load_topics()
        whitelist = load_whitelist()
        blacklist = load_blacklist()
        exclusions = load_exclusions()
        
        if verbose:
            print(f"  Topics: {len(topics)}")
            print(f"  Whitelist: {len(whitelist)} authors")
            print(f"  Blacklist: {len(blacklist)} authors")
            print(f"  Exclusions: {len(exclusions)} terms")
        
        # Step 2: Build query
        if verbose:
            print("\nBuilding PubMed query...")
        
        query = build_pubmed_query(topics, exclusions)
        
        if verbose:
            print(f"  Query length: {len(query)} chars")
        
        # Step 3: Search PubMed
        if verbose:
            print(f"\nSearching PubMed (last {DAYS_BACK} days)...")
        
        pmids = search_pubmed(query, days=DAYS_BACK, max_results=MAX_RESULTS)
        
        if verbose:
            print(f"  Found {len(pmids)} papers")
        
        if not pmids:
            if verbose:
                print("No papers found. Posting notification...")
            post_no_papers_message(DAYS_BACK)
            return True
        
        # Step 4: Fetch paper details
        if verbose:
            print("\nFetching paper details...")
        
        papers = fetch_pubmed_details(pmids)
        
        if verbose:
            print(f"  Fetched {len(papers)} papers")
        
        # Step 5: Enrich with Altmetric
        if verbose:
            print("\nEnriching with Altmetric scores...")
        
        papers = enrich_papers_with_altmetric(papers, verbose=verbose)
        
        # Step 6: AI Triage scoring
        if verbose:
            print("\nRunning AI triage scoring...")
        
        papers = batch_triage_papers(
            papers,
            whitelist=whitelist,
            blacklist=blacklist,
            verbose=verbose
        )
        
        if verbose:
            print(f"  Scored {len(papers)} papers")
        
        # Step 7: Sort and filter top papers
        if verbose:
            print("\nSelecting top papers...")
        
        # Calculate combined scores
        for paper in papers:
            paper["combined_score"] = calculate_combined_score(paper)
        
        # Sort by combined score (descending)
        papers.sort(key=lambda p: p["combined_score"], reverse=True)
        
        # Filter by minimum score and take top N
        top_papers = [
            p for p in papers 
            if p["combined_score"] >= MIN_COMBINED_SCORE
        ][:TOP_N_PAPERS]
        
        if verbose:
            print(f"  Top {len(top_papers)} papers above threshold")
        
        if not top_papers:
            if verbose:
                print("No papers met the scoring threshold. Posting notification...")
            post_no_papers_message(DAYS_BACK)
            return True
        
        # Step 8: Post to Slack
        if verbose:
            print("\nPosting to Slack...")
        
        slack_success = post_digest(top_papers, days=DAYS_BACK)
        
        if verbose:
            print(f"  Slack post: {'Success' if slack_success else 'Failed'}")
        
        # Step 9: Log to Notion
        if verbose:
            print("\nLogging to Notion...")
        
        try:
            notion_results = log_papers_deduplicated(top_papers)
            if verbose:
                print(f"  Notion: {notion_results['success']} added, {notion_results['skipped']} skipped, {notion_results['failed']} failed")
        except Exception as e:
            print(f"  Notion logging failed (non-fatal): {e}")
        
        if verbose:
            print("\n✅ Daily digest completed successfully!")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        print(f"\n❌ Error: {error_msg}")
        print(error_trace)
        
        # Try to post error to Slack
        try:
            post_error(error_msg, context="Check GitHub Actions logs for full traceback.")
        except Exception as slack_err:
            print(f"Failed to post error to Slack: {slack_err}")
        
        return False


if __name__ == "__main__":
    success = run_daily_digest(verbose=True)
    sys.exit(0 if success else 1)
