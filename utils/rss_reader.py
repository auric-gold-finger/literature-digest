"""
RSS feed reader utilities for longevity news aggregation.

Fetches and parses RSS feeds from longevity-focused sources.
"""

import os
import hashlib
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class FeedItem:
    """Represents a single RSS feed item."""
    title: str
    url: str
    source: str
    source_url: str
    published: Optional[datetime]
    summary: str
    guid: str  # Unique identifier for deduplication
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "source_url": self.source_url,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
            "guid": self.guid,
        }


# RSS Feed Configuration
RSS_FEEDS = [
    {
        "name": "Lifespan.io",
        "url": "https://www.lifespan.io/feed/",
        "category": "news",
        "priority": "high",
    },
    {
        "name": "Fight Aging!",
        "url": "https://www.fightaging.org/feed/",
        "category": "news",
        "priority": "high",
    },
    {
        "name": "r/longevity",
        "url": "https://www.reddit.com/r/longevity/.rss",
        "category": "reddit",
        "priority": "high",
    },
    {
        "name": "Buck Institute",
        "url": "https://www.buckinstitute.org/feed/",
        "category": "research",
        "priority": "medium",
    },
    {
        "name": "r/Peptides",
        "url": "https://www.reddit.com/r/Peptides/.rss",
        "category": "reddit",
        "priority": "medium",
    },
]


def _parse_date(entry: Dict) -> Optional[datetime]:
    """Parse date from RSS entry."""
    # Try various date fields
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        if hasattr(entry, field) and getattr(entry, field):
            try:
                time_tuple = getattr(entry, field)
                return datetime(*time_tuple[:6])
            except Exception:
                continue
    
    # Try string parsing as fallback
    for field in ["published", "updated", "created"]:
        if hasattr(entry, field) and getattr(entry, field):
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(getattr(entry, field))
            except Exception:
                continue
    
    return None


def _generate_guid(entry: Dict, feed_name: str) -> str:
    """Generate a unique ID for deduplication."""
    # Use entry's own ID if available
    if hasattr(entry, "id") and entry.id:
        return hashlib.md5(entry.id.encode()).hexdigest()
    
    # Fall back to URL + title hash
    content = f"{feed_name}:{entry.get('link', '')}:{entry.get('title', '')}"
    return hashlib.md5(content.encode()).hexdigest()


def _clean_summary(summary: str, max_length: int = 500) -> str:
    """Clean and truncate summary text."""
    if not summary:
        return ""
    
    # Remove HTML tags (simple approach)
    import re
    clean = re.sub(r'<[^>]+>', '', summary)
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&')
    clean = clean.replace('&lt;', '<').replace('&gt;', '>')
    clean = ' '.join(clean.split())  # Normalize whitespace
    
    if len(clean) > max_length:
        clean = clean[:max_length-3] + "..."
    
    return clean


def fetch_feed(feed_config: Dict, verbose: bool = False) -> List[FeedItem]:
    """
    Fetch and parse a single RSS feed.
    
    Args:
        feed_config: Dict with 'name', 'url', 'category', 'priority'
        verbose: Print progress
    
    Returns:
        List of FeedItem objects
    """
    name = feed_config["name"]
    url = feed_config["url"]
    
    if verbose:
        print(f"  Fetching {name}...")
    
    try:
        # Add user agent to avoid blocks
        feed = feedparser.parse(url, agent="LongevityDigest/1.0")
        
        if feed.bozo and not feed.entries:
            if verbose:
                print(f"    ⚠️ Feed error: {feed.bozo_exception}")
            return []
        
        items = []
        for entry in feed.entries:
            item = FeedItem(
                title=entry.get("title", "Untitled"),
                url=entry.get("link", ""),
                source=name,
                source_url=feed.feed.get("link", url),
                published=_parse_date(entry),
                summary=_clean_summary(entry.get("summary", "")),
                guid=_generate_guid(entry, name),
            )
            items.append(item)
        
        if verbose:
            print(f"    ✓ {len(items)} items")
        
        return items
        
    except Exception as e:
        if verbose:
            print(f"    ❌ Error: {e}")
        return []


def fetch_all_feeds(
    feeds: Optional[List[Dict]] = None,
    hours_back: int = 24,
    verbose: bool = False
) -> List[FeedItem]:
    """
    Fetch items from all RSS feeds.
    
    Args:
        feeds: List of feed configs (defaults to RSS_FEEDS)
        hours_back: Only include items from this many hours ago
        verbose: Print progress
    
    Returns:
        List of FeedItem objects, sorted by date (newest first)
    """
    if feeds is None:
        feeds = RSS_FEEDS
    
    cutoff = datetime.now() - timedelta(hours=hours_back)
    all_items = []
    
    if verbose:
        print(f"Fetching {len(feeds)} RSS feeds (last {hours_back}h)...")
    
    for feed_config in feeds:
        items = fetch_feed(feed_config, verbose=verbose)
        
        # Filter by date
        for item in items:
            if item.published is None or item.published >= cutoff:
                all_items.append(item)
    
    # Sort by date (newest first), handling None dates
    all_items.sort(
        key=lambda x: x.published or datetime.min,
        reverse=True
    )
    
    if verbose:
        print(f"\nTotal: {len(all_items)} items in last {hours_back}h")
    
    return all_items


def filter_seen_items(
    items: List[FeedItem],
    seen_guids: set
) -> List[FeedItem]:
    """Filter out items that have already been posted."""
    return [item for item in items if item.guid not in seen_guids]


def get_feed_stats(items: List[FeedItem]) -> Dict:
    """Get statistics about fetched items by source."""
    stats = {}
    for item in items:
        if item.source not in stats:
            stats[item.source] = 0
        stats[item.source] += 1
    return stats
