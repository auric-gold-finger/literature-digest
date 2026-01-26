#!/usr/bin/env python3
"""
RSS Longevity News Digest - Aggregates RSS feeds to Slack.

This script runs on a schedule to:
1. Fetch RSS feeds from longevity news sources
2. Filter out previously posted items
3. Post new items to Slack
4. Track posted items to avoid duplicates

Sources:
- Lifespan.io (news)
- Fight Aging! (analysis)
- r/longevity (community)
- Buck Institute (research)
- r/Peptides (peptide discussions)

Environment variables required:
- SLACK_WEBHOOK_URL: Slack incoming webhook URL

Optional:
- NOTION_API_KEY: For tracking posted items (if available)
- NOTION_RSS_DATABASE_ID: Separate database for RSS items
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set

from utils.rss_reader import (
    fetch_all_feeds,
    filter_seen_items,
    get_feed_stats,
    FeedItem,
    RSS_FEEDS,
)


# Configuration
HOURS_BACK = 24  # How far back to look for new items
MAX_ITEMS_PER_POST = 15  # Maximum items to post at once
SEEN_ITEMS_FILE = Path(__file__).parent / ".rss_seen_items.json"

# Source emoji mapping
SOURCE_EMOJI = {
    "Lifespan.io": "🧬",
    "Fight Aging!": "⚔️",
    "r/longevity": "📢",
    "Buck Institute": "🔬",
    "r/Peptides": "💊",
}


def load_seen_items() -> Set[str]:
    """Load previously seen item GUIDs from file."""
    if SEEN_ITEMS_FILE.exists():
        try:
            with open(SEEN_ITEMS_FILE, "r") as f:
                data = json.load(f)
                return set(data.get("guids", []))
        except Exception:
            pass
    return set()


def save_seen_items(guids: Set[str]):
    """Save seen item GUIDs to file."""
    # Keep only the most recent 1000 items to prevent unbounded growth
    guids_list = list(guids)[-1000:]
    try:
        with open(SEEN_ITEMS_FILE, "w") as f:
            json.dump({
                "guids": guids_list,
                "updated": datetime.now().isoformat(),
            }, f)
    except Exception as e:
        print(f"Warning: Could not save seen items: {e}")


def format_slack_message(items: List[FeedItem]) -> Dict:
    """
    Format RSS items as a Slack message using Block Kit.
    
    Args:
        items: List of FeedItem objects to format
    
    Returns:
        Slack message payload dict
    """
    blocks = []
    
    # Header
    now = datetime.now()
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"📰 Longevity News Roundup",
            "emoji": True
        }
    })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"*{len(items)} new items* from the longevity community · {now.strftime('%b %d, %Y')}"
            }
        ]
    })
    
    blocks.append({"type": "divider"})
    
    # Group items by source
    by_source = {}
    for item in items:
        if item.source not in by_source:
            by_source[item.source] = []
        by_source[item.source].append(item)
    
    # Format each source section
    for source, source_items in by_source.items():
        emoji = SOURCE_EMOJI.get(source, "📄")
        
        # Source header
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{emoji} {source}*"
            }
        })
        
        # Items as bullet list
        item_lines = []
        for item in source_items[:5]:  # Max 5 per source
            # Format title with link
            title = item.title[:100] + "..." if len(item.title) > 100 else item.title
            line = f"• <{item.url}|{title}>"
            
            # Add time ago if available
            if item.published:
                hours_ago = (datetime.now() - item.published).total_seconds() / 3600
                if hours_ago < 1:
                    time_str = "just now"
                elif hours_ago < 24:
                    time_str = f"{int(hours_ago)}h ago"
                else:
                    time_str = f"{int(hours_ago/24)}d ago"
                line += f" _({time_str})_"
            
            item_lines.append(line)
        
        if len(source_items) > 5:
            item_lines.append(f"_...and {len(source_items) - 5} more_")
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(item_lines)
            }
        })
    
    blocks.append({"type": "divider"})
    
    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Sources: Lifespan.io · Fight Aging! · r/longevity · Buck Institute · r/Peptides"
            }
        ]
    })
    
    return {"blocks": blocks}


def post_to_slack(message: Dict, verbose: bool = False) -> bool:
    """
    Post message to Slack webhook.
    
    Args:
        message: Slack message payload
        verbose: Print progress
    
    Returns:
        True if successful
    """
    import requests
    
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL environment variable not set")
    
    try:
        response = requests.post(
            webhook_url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            if verbose:
                print("✅ Posted to Slack successfully")
            return True
        else:
            print(f"❌ Slack error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Slack request failed: {e}")
        return False


def run_rss_digest(verbose: bool = True) -> bool:
    """
    Run the complete RSS digest pipeline.
    
    Args:
        verbose: Print progress information
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Step 1: Load previously seen items
        if verbose:
            print("Loading seen items...")
        
        seen_guids = load_seen_items()
        
        if verbose:
            print(f"  {len(seen_guids)} previously seen items")
        
        # Step 2: Fetch all RSS feeds
        if verbose:
            print(f"\nFetching RSS feeds...")
        
        all_items = fetch_all_feeds(
            feeds=RSS_FEEDS,
            hours_back=HOURS_BACK,
            verbose=verbose
        )
        
        if not all_items:
            if verbose:
                print("No items found in feeds.")
            return True
        
        # Step 3: Filter out seen items
        if verbose:
            print("\nFiltering seen items...")
        
        new_items = filter_seen_items(all_items, seen_guids)
        
        if verbose:
            print(f"  {len(new_items)} new items (of {len(all_items)} total)")
        
        if not new_items:
            if verbose:
                print("\nNo new items to post.")
            return True
        
        # Step 4: Limit to max items
        items_to_post = new_items[:MAX_ITEMS_PER_POST]
        
        if verbose:
            print(f"\nPosting {len(items_to_post)} items...")
            stats = get_feed_stats(items_to_post)
            for source, count in stats.items():
                print(f"  {source}: {count}")
        
        # Step 5: Format and post to Slack
        message = format_slack_message(items_to_post)
        success = post_to_slack(message, verbose=verbose)
        
        if success:
            # Step 6: Save posted items as seen
            new_guids = {item.guid for item in items_to_post}
            all_seen = seen_guids | new_guids
            save_seen_items(all_seen)
            
            if verbose:
                print(f"\n✅ RSS digest complete - posted {len(items_to_post)} items")
        
        return success
        
    except Exception as e:
        print(f"❌ RSS digest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    verbose = "--quiet" not in sys.argv
    success = run_rss_digest(verbose=verbose)
    sys.exit(0 if success else 1)
