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
    Format a single paper as Slack Block Kit sections with critical appraisal.
    
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
    
    # Scores
    relevance = paper.get("triage_score", -1)
    evidence = paper.get("evidence_score", -1)
    actionability = paper.get("actionability_score", -1)
    altmetric_data = paper.get("altmetric", {})
    altmetric_score = altmetric_data.get("score", 0)
    twitter_count = altmetric_data.get("twitter", 0)
    news_count = altmetric_data.get("news", 0)
    
    # Summary (from AI critical appraisal)
    summary = paper.get("summary", {})
    study_type = summary.get("study_type", "")
    population = summary.get("population", "")
    intervention = summary.get("intervention_exposure", "")
    key_finding = summary.get("key_finding", "")
    clinical_magnitude = summary.get("clinical_magnitude", "")
    methods_notes = summary.get("methodological_notes", "")
    bottom_line = summary.get("bottom_line", "")
    why_selected = summary.get("why_selected", "")
    attia_take = summary.get("attia_take", "")
    
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
    
    # Score line with social attention
    if relevance >= 0:
        score_parts = [f"Rel {relevance}", f"Evid {evidence}", f"Action {actionability}"]
        scores_line = " · ".join(score_parts)
        
        # Add social attention if notable (show Twitter/news counts)
        attention_parts = []
        if twitter_count >= 10:
            attention_parts.append(f"{twitter_count} tweets")
        if news_count >= 1:
            attention_parts.append(f"{news_count} news")
        if altmetric_score >= 20 and not attention_parts:
            attention_parts.append(f"Altmetric {altmetric_score}")
        
        if attention_parts:
            scores_line += f" · _Attention: {', '.join(attention_parts)}_"
    else:
        scores_line = "_Scores unavailable_"
    
    # Build appraisal - prioritize readability
    appraisal_lines = []
    
    # Study type as a clean tag
    if study_type:
        appraisal_lines.append(study_type.upper())
        appraisal_lines.append("")
    
    # Key finding first - this is what readers want
    if key_finding:
        appraisal_lines.append(key_finding)
        appraisal_lines.append("")
    
    # Attia's Take - the opinionated podcast-style commentary (prominent placement)
    if attia_take:
        appraisal_lines.append(f"*PA:* _{attia_take}_")
        appraisal_lines.append("")
    
    # Context paragraph: magnitude + population + methods (condensed)
    context_parts = []
    if clinical_magnitude:
        context_parts.append(clinical_magnitude)
    if population:
        context_parts.append(population)
    if methods_notes:
        context_parts.append(methods_notes)
    
    if context_parts:
        appraisal_lines.append(" ".join(context_parts))
        appraisal_lines.append("")
    
    # Bottom line stands out
    if bottom_line:
        appraisal_lines.append(f"*{bottom_line}*")
    
    appraisal_text = "\n".join(appraisal_lines).strip()
    
    # Truncate authors
    if len(authors) > 80:
        authors = authors[:77] + "..."
    
    # Combine all parts
    text_parts = [
        f"*{rank}. <{url}|{title}>*",
        meta_line,
        scores_line,
    ]
    
    if appraisal_text:
        text_parts.append("")
        text_parts.append(appraisal_text)
    
    text_parts.append("")
    text_parts.append(f"― _{authors}_")
    
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(text_parts)
        }
    }


def build_digest_message(papers: List[Dict], days: int = 7, usage_stats: Optional[Dict] = None) -> Dict:
    """
    Build complete Slack message payload for daily digest.
    
    Args:
        papers: List of top papers to include
        days: Number of days the search covered
        usage_stats: Optional dict with API usage statistics
    
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
    
    # Footer with score legend and usage stats
    blocks.append({"type": "divider"})
    
    footer_text = "Rel = clinical relevance · Evid = study quality · Action = practice applicability"
    
    if usage_stats:
        api_calls = usage_stats.get("api_calls", 0)
        total_tokens = usage_stats.get("total_input_tokens", 0) + usage_stats.get("total_output_tokens", 0)
        errors = usage_stats.get("errors", 0)
        
        footer_text += f"\n_API: {api_calls} Gemini calls"
        if total_tokens > 0:
            footer_text += f", ~{total_tokens:,} tokens"
        if errors > 0:
            footer_text += f", {errors} errors"
        footer_text += "_"
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": footer_text
            }
        ]
    })
    
    return {"blocks": blocks}


def post_digest(papers: List[Dict], days: int = 7, usage_stats: Optional[Dict] = None) -> bool:
    """
    Post paper digest to Slack channel via webhook.
    
    Args:
        papers: List of top papers to post
        days: Number of days the search covered
        usage_stats: Optional dict with API usage statistics
    
    Returns:
        True if successful, False otherwise
    """
    webhook_url = get_webhook_url()
    payload = build_digest_message(papers, days, usage_stats)
    
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
