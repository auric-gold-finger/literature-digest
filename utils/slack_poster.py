"""
Slack posting utilities for Literature Digest daily digest.

Posts formatted paper digests to Slack via incoming webhook.
"""

import os
import requests
from datetime import datetime
from typing import List, Dict, Optional


def get_webhook_url() -> str:
    """Get Slack webhook URL from environment."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        raise ValueError("SLACK_WEBHOOK_URL environment variable not set")
    return url


def format_date(date_str: str) -> str:
    """
    Format date string to readable format (e.g., 'Jan 2026').
    
    Args:
        date_str: Date in YYYY-MM-DD or YYYY/MM/DD format
    
    Returns:
        Formatted date string like 'Jan 2026'
    """
    if not date_str:
        return ""
    try:
        # Handle various date formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y"]:
            try:
                dt = datetime.strptime(date_str[:10], fmt)
                return dt.strftime("%b %Y")
            except ValueError:
                continue
        return date_str[:7]  # Fallback to YYYY-MM
    except Exception:
        return ""


def format_paper_block(paper: Dict, rank: int) -> List[Dict]:
    """
    Format a single paper as Slack Block Kit sections with clean typography.
    
    Args:
        paper: Paper dict with title, journal, authors, scores, url, summary, etc.
        rank: Paper rank (1-5)
    
    Returns:
        List of Slack Block Kit block dicts
    """
    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "Unknown journal")
    authors = paper.get("authors", "Unknown authors")
    url = paper.get("url", "")
    doi = paper.get("doi", "")
    pub_date = paper.get("pub_date", "")
    pmid = paper.get("pmid", "")
    
    # Scores
    relevance = paper.get("triage_score", -1)
    evidence = paper.get("evidence_score", -1)
    actionability = paper.get("actionability_score", -1)
    altmetric = paper.get("altmetric", {}).get("score", 0)
    
    # Summary (from AI)
    summary = paper.get("summary", {})
    study_type = summary.get("study_type", "")
    tldr = summary.get("tldr", "")
    key_points = summary.get("key_points", [])
    why_selected = summary.get("why_selected", "")
    
    # Format date
    date_display = format_date(pub_date)
    
    # Build metadata line: Journal · Date · DOI · PubMed
    meta_parts = [f"_{journal}_"]
    if date_display:
        meta_parts.append(date_display)
    if doi:
        doi_url = f"https://doi.org/{doi}" if not doi.startswith("http") else doi
        meta_parts.append(f"<{doi_url}|DOI>")
    if url:
        meta_parts.append(f"<{url}|PubMed>")
    meta_line = " · ".join(meta_parts)
    
    # Score line
    if relevance >= 0:
        score_parts = [f"Rel {relevance}", f"Evid {evidence}", f"Action {actionability}"]
        if altmetric > 0:
            score_parts.append(f"Altmetric {altmetric}")
        scores_line = " · ".join(score_parts)
    else:
        scores_line = "_Scores unavailable_"
    
    # Build summary section
    summary_lines = []
    if study_type and tldr:
        summary_lines.append(f"*{study_type}* — {tldr}")
    elif tldr:
        summary_lines.append(tldr)
    
    for point in key_points[:2]:  # Max 2 bullet points
        summary_lines.append(f"→ {point}")
    
    if why_selected:
        summary_lines.append(f"\n_Why selected: {why_selected}_")
    
    summary_text = "\n".join(summary_lines) if summary_lines else ""
    
    # Truncate authors if too long
    if len(authors) > 100:
        authors = authors[:97] + "..."
    authors_line = f"― {authors}"
    
    # Combine all parts
    text_parts = [
        f"*{rank}. <{url}|{title}>*",
        meta_line,
        scores_line,
    ]
    
    if summary_text:
        text_parts.append("")  # Blank line
        text_parts.append(summary_text)
    
    text_parts.append("")  # Blank line before authors
    text_parts.append(authors_line)
    
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(text_parts)
        }
    }


def build_digest_message(papers: List[Dict], days: int = 7) -> Dict:
    """
    Build complete Slack message payload for daily digest.
    
    Args:
        papers: List of top papers to include
        days: Number of days the search covered
    
    Returns:
        Slack message payload dict
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Literature Digest",
                "emoji": False
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Top {len(papers)} papers from the past {days} days, ranked by relevance, evidence quality, and actionability."
                }
            ]
        },
        {"type": "divider"}
    ]
    
    # Add each paper
    for i, paper in enumerate(papers, 1):
        blocks.append(format_paper_block(paper, i))
        if i < len(papers):
            blocks.append({"type": "divider"})
    
    # Footer with score legend
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Rel = clinical relevance · Evid = study quality · Action = practice applicability"
            }
        ]
    })
    
    return {"blocks": blocks}


def post_digest(papers: List[Dict], days: int = 7) -> bool:
    """
    Post paper digest to Slack channel via webhook.
    
    Args:
        papers: List of top papers to post
        days: Number of days the search covered
    
    Returns:
        True if successful, False otherwise
    """
    webhook_url = get_webhook_url()
    payload = build_digest_message(papers, days)
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Failed to post digest to Slack: {e}")
        return False


def post_error(error_message: str, context: Optional[str] = None) -> bool:
    """
    Post error notification to Slack channel.
    
    Args:
        error_message: Main error message
        context: Optional additional context
    
    Returns:
        True if successful, False otherwise
    """
    webhook_url = get_webhook_url()
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Literature Digest — Error",
                "emoji": False
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"The daily digest encountered an error:\n```{error_message}```"
            }
        }
    ]
    
    if context:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": context
                }
            ]
        })
    
    payload = {"blocks": blocks}
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Failed to post error to Slack: {e}")
        return False


def post_no_papers_message(days: int = 7) -> bool:
    """
    Post message when no papers meet the threshold.
    
    Args:
        days: Number of days the search covered
    
    Returns:
        True if successful, False otherwise
    """
    webhook_url = get_webhook_url()
    
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Literature Digest",
                    "emoji": False
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"No papers from the past {days} days met the scoring threshold today."
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Failed to post to Slack: {e}")
        return False
