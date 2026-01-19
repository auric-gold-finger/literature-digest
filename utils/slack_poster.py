"""
Slack posting utilities for Literature Digest daily digest.

Posts formatted paper digests to Slack via incoming webhook.
"""

import os
import requests
from typing import List, Dict, Optional


def get_webhook_url() -> str:
    """Get Slack webhook URL from environment."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        raise ValueError("SLACK_WEBHOOK_URL environment variable not set")
    return url


def format_paper_block(paper: Dict, rank: int) -> Dict:
    """
    Format a single paper as a Slack Block Kit section.
    
    Args:
        paper: Paper dict with title, journal, authors, scores, url, etc.
        rank: Paper rank (1-5)
    
    Returns:
        Slack Block Kit block dict
    """
    title = paper.get("title", "Untitled")
    journal = paper.get("journal", "Unknown journal")
    authors = paper.get("authors", "Unknown authors")
    url = paper.get("url", "")
    doi = paper.get("doi", "")
    
    # Scores
    relevance = paper.get("triage_score", -1)
    evidence = paper.get("evidence_score", -1)
    actionability = paper.get("actionability_score", -1)
    altmetric = paper.get("altmetric", {}).get("score", 0)
    
    # Whitelisted indicator
    whitelisted = "⭐ " if paper.get("whitelisted") else ""
    
    # Score display
    if relevance >= 0:
        scores_text = f"📊 Rel: *{relevance}* | Evid: *{evidence}* | Action: *{actionability}*"
        if altmetric > 0:
            scores_text += f" | Altmetric: {altmetric}"
    else:
        scores_text = "📊 _Scores unavailable_"
    
    # Truncate authors if too long
    if len(authors) > 80:
        authors = authors[:77] + "..."
    
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*{rank}. {whitelisted}<{url}|{title}>*\n"
                f"_{journal}_ • {authors}\n"
                f"{scores_text}"
            )
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
                "text": "📚 Literature Digest",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Top {len(papers)} papers from the last {days} days, scored by AI for relevance, evidence quality, and actionability."
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
    
    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Scores: _Relevance (clinical importance)_ • _Evidence (study quality)_ • _Actionability (practice change)_ | ⭐ = Priority author"
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
                "text": "⚠️ Literature Digest Error",
                "emoji": True
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
                    "text": "📚 Literature Digest",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"No papers from the last {days} days met the scoring threshold today. Check back tomorrow! 🔍"
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
