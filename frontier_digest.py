#!/usr/bin/env python3
"""
Frontier Literature Digest - Weekly bleeding-edge research digest.

This script runs weekly to surface cutting-edge, paradigm-shifting longevity
research that may not score highly on traditional evidence metrics but has
high potential for future impact.

Key differences from daily_digest.py:
1. Lower score thresholds (12 vs 15) to capture emerging research
2. Includes bioRxiv/medRxiv preprints alongside PubMed
3. Uses frontier_score dimension to prioritize paradigm-shifting work
4. ITP results always included regardless of scoring
5. Separate Slack formatting with "🔬 Frontier" badges

Environment variables required:
- NCBI_EMAIL: Email for PubMed API
- GEMINI_API_KEY: Google Gemini API key
- SLACK_WEBHOOK_URL: Slack incoming webhook URL
- NOTION_API_KEY: Notion integration token
- NOTION_DATABASE_ID: Notion database ID
"""

import sys
import traceback

# Import utilities
from utils.config_loader import load_topics, load_whitelist, load_blacklist, load_exclusions
from utils.query_builder import build_pubmed_query
from utils.pubmed_headless import search_pubmed, fetch_pubmed_details
from utils.altmetric_headless import enrich_papers_with_altmetric
from utils.gemini_headless import batch_triage_papers, summarize_papers_batch, get_usage_stats, reset_usage_stats, generate_digest_summary
from utils.slack_poster import post_frontier_digest, post_error, post_no_papers_message
from utils.notion_logger import log_papers_deduplicated, get_posted_pmids
from utils.preprint import search_longevity_preprints, get_itp_preprints


# Frontier Configuration - more permissive than daily digest
DAYS_BACK = 14                  # Look back further for weekly digest
MAX_PUBMED_RESULTS = 300        # More results to catch niche topics
MAX_PREPRINT_RESULTS = 50       # Preprints to fetch
TOP_N_PAPERS = 7                # Slightly more papers in frontier digest
MIN_COMBINED_SCORE = 12         # Lower threshold for emerging research
MIN_FRONTIER_SCORE = 6          # Minimum frontier score to consider
ITP_AUTHOR_NAMES = ["Miller RA", "Strong R", "Harrison DE", "Nadon NL"]  # Always include


def calculate_combined_score(paper: dict) -> int:
    """Calculate combined score from relevance + evidence + actionability."""
    rel = paper.get("triage_score", -1)
    evid = paper.get("evidence_score", -1)
    action = paper.get("actionability_score", -1)
    
    if rel < 0 or evid < 0 or action < 0:
        return 0
    
    return rel + evid + action


def calculate_frontier_combined_score(paper: dict) -> int:
    """
    Calculate frontier-weighted score that values paradigm-shifting potential.
    
    Formula: relevance + (evidence * 0.5) + (actionability * 0.5) + (frontier * 1.5)
    
    This weights frontier potential more heavily while still considering
    evidence and actionability.
    """
    rel = paper.get("triage_score", 0)
    evid = paper.get("evidence_score", 0)
    action = paper.get("actionability_score", 0)
    frontier = paper.get("frontier_score", 0)
    
    if rel < 0:
        return 0
    
    return int(rel + (evid * 0.5) + (action * 0.5) + (frontier * 1.5))


def is_itp_paper(paper: dict) -> bool:
    """Check if paper is from ITP or ITP authors (always include)."""
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    authors = paper.get("authors", "")
    
    # Check for ITP in title/abstract
    itp_terms = ["interventions testing program", "itp", "nia itp"]
    if any(term in title or term in abstract for term in itp_terms):
        return True
    
    # Check for ITP authors
    for author in ITP_AUTHOR_NAMES:
        if author.lower() in authors.lower():
            return True
    
    return False


def run_frontier_digest(verbose: bool = True) -> bool:
    """
    Run the weekly frontier digest pipeline.
    
    Args:
        verbose: Print progress information
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Reset usage stats at start of run
        reset_usage_stats()
        
        # Step 1: Load configuration
        if verbose:
            print("🔬 FRONTIER DIGEST - Loading configuration...")
        
        topics = load_topics()
        whitelist = load_whitelist()
        blacklist = load_blacklist()
        exclusions = load_exclusions()
        
        if verbose:
            print(f"  Topics: {len(topics)}")
            print(f"  Whitelist: {len(whitelist)} authors")
        
        # Step 2: Build query and search PubMed
        if verbose:
            print(f"\n📚 Searching PubMed (last {DAYS_BACK} days)...")
        
        query = build_pubmed_query(topics, exclusions)
        pmids = search_pubmed(query, days=DAYS_BACK, max_results=MAX_PUBMED_RESULTS)
        
        if verbose:
            print(f"  Found {len(pmids)} PubMed papers")
        
        # Step 3: Fetch PubMed paper details
        pubmed_papers = []
        if pmids:
            pubmed_papers = fetch_pubmed_details(pmids)
            if verbose:
                print(f"  Fetched {len(pubmed_papers)} PubMed papers")
        
        # Step 4: Search preprints
        if verbose:
            print(f"\n📄 Searching preprints (bioRxiv/medRxiv)...")
        
        preprint_papers = search_longevity_preprints(
            days_back=DAYS_BACK,
            max_results=MAX_PREPRINT_RESULTS
        )
        
        if verbose:
            print(f"  Found {len(preprint_papers)} preprints")
        
        # Step 5: Specifically search for ITP preprints
        if verbose:
            print(f"\n🧪 Searching for ITP preprints...")
        
        itp_preprints = get_itp_preprints(days_back=30)  # Look back further for ITP
        
        if verbose:
            print(f"  Found {len(itp_preprints)} ITP-related preprints")
        
        # Combine all papers (dedupe by DOI/PMID)
        all_papers = pubmed_papers + preprint_papers + itp_preprints
        
        # Deduplicate by DOI (preprints may appear in PubMed later)
        seen_dois = set()
        seen_pmids = set()
        unique_papers = []
        
        for paper in all_papers:
            doi = paper.get("doi", "")
            pmid = paper.get("pmid", "")
            
            # Skip if we've seen this DOI or PMID
            if doi and doi in seen_dois:
                continue
            if pmid and pmid in seen_pmids:
                continue
            
            if doi:
                seen_dois.add(doi)
            if pmid:
                seen_pmids.add(pmid)
            
            unique_papers.append(paper)
        
        papers = unique_papers
        
        if verbose:
            print(f"\n  Total unique papers: {len(papers)}")
        
        if not papers:
            if verbose:
                print("No papers found. Posting notification...")
            post_no_papers_message(DAYS_BACK, digest_type="frontier")
            return True
        
        # Step 6: Enrich with Altmetric (skip preprints - they often don't have scores)
        if verbose:
            print("\n📊 Enriching with Altmetric scores...")
        
        papers = enrich_papers_with_altmetric(papers, verbose=verbose)
        
        # Step 7: AI Triage scoring
        if verbose:
            print("\n🤖 Running AI triage scoring...")
        
        papers = batch_triage_papers(
            papers,
            whitelist=whitelist,
            blacklist=blacklist,
            verbose=verbose
        )
        
        # Step 8: Filter previously posted papers
        if verbose:
            print("\n🔍 Filtering previously posted papers...")
        
        posted_pmids = get_posted_pmids(days_back=30)  # Longer window for weekly
        
        if posted_pmids:
            original_count = len(papers)
            papers = [p for p in papers if p.get("pmid", "") not in posted_pmids]
            filtered = original_count - len(papers)
            if verbose:
                print(f"  Filtered {filtered} previously posted papers")
        
        # Step 9: Select papers with frontier-weighted scoring
        if verbose:
            print("\n⚡ Selecting frontier papers...")
        
        # Calculate scores
        for paper in papers:
            paper["combined_score"] = calculate_combined_score(paper)
            paper["frontier_combined_score"] = calculate_frontier_combined_score(paper)
            paper["is_itp"] = is_itp_paper(paper)
        
        # ITP papers always get through (regardless of score)
        itp_papers = [p for p in papers if p.get("is_itp")]
        
        # Other papers: filter by frontier-weighted threshold
        other_papers = [
            p for p in papers 
            if not p.get("is_itp") 
            and p.get("frontier_combined_score", 0) >= MIN_COMBINED_SCORE
            and p.get("frontier_score", 0) >= MIN_FRONTIER_SCORE
        ]
        
        # Sort other papers by frontier_combined_score
        other_papers.sort(key=lambda p: p["frontier_combined_score"], reverse=True)
        
        # Combine: ITP first, then top frontier papers
        top_papers = itp_papers + other_papers
        top_papers = top_papers[:TOP_N_PAPERS]
        
        if verbose:
            print(f"  ITP papers: {len(itp_papers)}")
            print(f"  Other frontier papers: {len(other_papers)}")
            print(f"  Selected {len(top_papers)} total papers")
        
        if not top_papers:
            if verbose:
                print("No papers met the frontier threshold. Posting notification...")
            post_no_papers_message(DAYS_BACK, digest_type="frontier")
            return True
        
        # Step 10: Generate AI summaries
        if verbose:
            print("\n📝 Generating AI summaries...")
        
        top_papers = summarize_papers_batch(top_papers, verbose=verbose)
        
        # Step 11: Generate digest summary
        if verbose:
            print("\n✍️ Generating digest summary...")
        
        digest_summary = generate_digest_summary(top_papers)
        
        # Step 12: Post to Slack (frontier format)
        if verbose:
            print("\n📬 Posting to Slack (frontier format)...")
        
        usage_stats = get_usage_stats()
        slack_success = post_frontier_digest(
            top_papers,
            summary_text=digest_summary,
            usage_stats=usage_stats,
            verbose=verbose
        )
        
        if verbose:
            print(f"  Slack post: {'Success' if slack_success else 'Failed'}")
        
        # Step 13: Log to Notion
        if verbose:
            print("\n📓 Logging to Notion...")
        
        try:
            # Mark papers as frontier digest
            for paper in top_papers:
                paper["digest_type"] = "frontier"
            
            notion_results = log_papers_deduplicated(top_papers)
            if verbose:
                print(f"  Notion: {notion_results['success']} added, {notion_results['skipped']} skipped")
        except Exception as e:
            print(f"  Notion logging failed (non-fatal): {e}")
        
        # Print usage summary
        if verbose:
            print("\n📊 API Usage:")
            print(f"  Gemini calls: {usage_stats['api_calls']}")
            print(f"  Tokens: ~{usage_stats['total_input_tokens'] + usage_stats['total_output_tokens']:,}")
            if usage_stats['errors'] > 0:
                print(f"  Errors: {usage_stats['errors']}")
        
        if verbose:
            print("\n✅ Frontier digest completed successfully!")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        
        print(f"\n❌ Error: {error_msg}")
        print(error_trace)
        
        # Try to post error to Slack
        try:
            post_error(error_msg, context="Frontier Digest - Check logs for details.")
        except Exception:
            pass
        
        return False


if __name__ == "__main__":
    # Run the frontier digest
    verbose = "--quiet" not in sys.argv
    success = run_frontier_digest(verbose=verbose)
    sys.exit(0 if success else 1)
