"""
Configuration loader for headless execution (non-Streamlit).

Loads config from environment variables or local defaults.json.
Used by daily_digest.py when running outside Streamlit context.
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional


# Path to local defaults
DEFAULTS_PATH = Path(__file__).parent / "defaults.json"


def _get_sheet_url(sheet_id: str, gid: str = "0") -> str:
    """Construct CSV export URL for a Google Sheet tab."""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def _load_defaults() -> Dict:
    """Load fallback configuration from local defaults.json."""
    try:
        with open(DEFAULTS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load defaults.json: {e}")
        return {
            "topics": [],
            "authors_whitelist": [],
            "authors_blacklist": [],
            "exclusions": [],
            "presets": []
        }


def _load_sheet_tab(sheet_id: str, gid: str) -> Optional[pd.DataFrame]:
    """
    Load a single tab from a public Google Sheet.
    
    Args:
        sheet_id: The Google Sheet ID from the URL
        gid: The tab's GID (found in URL after #gid=)
    
    Returns:
        DataFrame with sheet contents, or None if failed
    """
    url = _get_sheet_url(sheet_id, gid)
    try:
        df = pd.read_csv(url)
        return df
    except Exception:
        return None


def load_config() -> Dict:
    """
    Load all configuration from Google Sheet or fall back to defaults.
    Uses environment variables instead of st.secrets.
    
    Environment variables:
    - GSHEET_CONFIG_ID: Google Sheet ID
    - GSHEET_TAB_TOPICS: GID for topics tab
    - GSHEET_TAB_WHITELIST: GID for whitelist tab
    - GSHEET_TAB_BLACKLIST: GID for blacklist tab
    - GSHEET_TAB_EXCLUSIONS: GID for exclusions tab
    - GSHEET_TAB_PRESETS: GID for presets tab
    
    Returns:
        Dict with keys: topics, authors_whitelist, authors_blacklist, exclusions, presets
    """
    sheet_id = os.environ.get("GSHEET_CONFIG_ID", "")
    
    if not sheet_id:
        # No sheet configured, use defaults
        return _load_defaults()
    
    # Tab GIDs from environment
    tab_gids = {
        "topics": os.environ.get("GSHEET_TAB_TOPICS", "0"),
        "authors_whitelist": os.environ.get("GSHEET_TAB_WHITELIST", ""),
        "authors_blacklist": os.environ.get("GSHEET_TAB_BLACKLIST", ""),
        "exclusions": os.environ.get("GSHEET_TAB_EXCLUSIONS", ""),
        "presets": os.environ.get("GSHEET_TAB_PRESETS", "")
    }
    
    config = {}
    defaults = _load_defaults()
    all_failed = True
    
    for tab_name, gid in tab_gids.items():
        if gid:
            df = _load_sheet_tab(sheet_id, gid)
            if df is not None and not df.empty:
                config[tab_name] = df.to_dict("records")
                all_failed = False
            else:
                config[tab_name] = defaults.get(tab_name, [])
        else:
            config[tab_name] = defaults.get(tab_name, [])
    
    if all_failed and sheet_id:
        print("Warning: Could not load from Google Sheet. Using local defaults.")
    
    return config


def load_topics() -> List[Dict]:
    """
    Get list of active search topics.
    
    Returns:
        List of dicts with keys: name, query_fragment, active
    """
    config = load_config()
    topics = config.get("topics", [])
    return [t for t in topics if t.get("active", True)]


def load_whitelist() -> List[str]:
    """
    Get list of whitelisted (priority) author names.
    
    Returns:
        List of author name strings
    """
    config = load_config()
    authors = config.get("authors_whitelist", [])
    return [a.get("author_name", "") for a in authors if a.get("active", True) and a.get("author_name")]


def load_blacklist() -> List[str]:
    """
    Get list of blacklisted author names.
    
    Returns:
        List of author name strings
    """
    config = load_config()
    authors = config.get("authors_blacklist", [])
    return [a.get("author_name", "") for a in authors if a.get("active", True) and a.get("author_name")]


def load_exclusions() -> List[str]:
    """
    Get list of exclusion terms for PubMed NOT clauses.
    
    Returns:
        List of exclusion term strings
    """
    config = load_config()
    exclusions = config.get("exclusions", [])
    return [e.get("term", "") for e in exclusions if e.get("active", True) and e.get("term")]
