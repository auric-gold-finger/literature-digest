"""
Google Sheets configuration reader for Literature Digest.

Reads configuration from a public Google Sheet with fallback to local defaults.json.
"""

import json
import streamlit as st
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
        st.error(f"Failed to load defaults.json: {e}")
        return {
            "topics": [],
            "authors_whitelist": [],
            "authors_blacklist": [],
            "exclusions": [],
            "presets": []
        }


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
def load_config_from_sheets() -> Dict:
    """
    Load all configuration from Google Sheet or fall back to defaults.
    
    Expects sheet tabs with these GIDs (configure in secrets.toml):
    - topics: GID 0 (default first tab)
    - authors_whitelist: GID from GSHEET_TAB_WHITELIST
    - authors_blacklist: GID from GSHEET_TAB_BLACKLIST  
    - exclusions: GID from GSHEET_TAB_EXCLUSIONS
    - presets: GID from GSHEET_TAB_PRESETS
    
    Returns:
        Dict with keys: topics, authors_whitelist, authors_blacklist, exclusions, presets
    """
    sheet_id = st.secrets.get("GSHEET_CONFIG_ID")
    
    if not sheet_id:
        # No sheet configured, use defaults
        return _load_defaults()
    
    # Tab GIDs - configure these in secrets.toml
    tab_gids = {
        "topics": st.secrets.get("GSHEET_TAB_TOPICS", "0"),
        "authors_whitelist": st.secrets.get("GSHEET_TAB_WHITELIST", ""),
        "authors_blacklist": st.secrets.get("GSHEET_TAB_BLACKLIST", ""),
        "exclusions": st.secrets.get("GSHEET_TAB_EXCLUSIONS", ""),
        "presets": st.secrets.get("GSHEET_TAB_PRESETS", "")
    }
    
    config = {}
    defaults = _load_defaults()
    all_failed = True
    
    for tab_name, gid in tab_gids.items():
        if gid:
            df = _load_sheet_tab(sheet_id, gid)
            if df is not None and not df.empty:
                # Convert DataFrame to list of dicts
                config[tab_name] = df.to_dict("records")
                all_failed = False
            else:
                config[tab_name] = defaults.get(tab_name, [])
        else:
            config[tab_name] = defaults.get(tab_name, [])
    
    if all_failed and sheet_id:
        st.warning("⚠️ Could not load from Google Sheet. Using local defaults.")
    
    return config


def refresh_config():
    """Clear cached config to force reload from sheet."""
    _load_sheet_tab.clear()
    load_config_from_sheets.clear()


def load_topics() -> List[Dict]:
    """
    Get list of search topics.
    
    Returns:
        List of dicts with keys: name, query_fragment, active
    """
    config = load_config_from_sheets()
    topics = config.get("topics", [])
    # Filter to active topics only
    return [t for t in topics if t.get("active", True)]


def load_all_topics() -> List[Dict]:
    """
    Get all topics (including inactive) for UI display.
    
    Returns:
        List of all topic dicts
    """
    config = load_config_from_sheets()
    return config.get("topics", [])


def load_whitelist() -> List[str]:
    """
    Get list of whitelisted (priority) author names.
    
    Returns:
        List of author name strings (e.g., "Kaeberlein M")
    """
    config = load_config_from_sheets()
    authors = config.get("authors_whitelist", [])
    return [a.get("author_name", "") for a in authors if a.get("active", True) and a.get("author_name")]


def load_blacklist() -> List[str]:
    """
    Get list of blacklisted author names.
    
    Returns:
        List of author name strings
    """
    config = load_config_from_sheets()
    authors = config.get("authors_blacklist", [])
    return [a.get("author_name", "") for a in authors if a.get("active", True) and a.get("author_name")]


def load_exclusions() -> List[str]:
    """
    Get list of exclusion terms for PubMed NOT clauses.
    
    Returns:
        List of exclusion term strings
    """
    config = load_config_from_sheets()
    exclusions = config.get("exclusions", [])
    return [e.get("term", "") for e in exclusions if e.get("active", True) and e.get("term")]


def load_all_exclusions() -> List[Dict]:
    """
    Get all exclusions (including inactive) for UI display.
    
    Returns:
        List of all exclusion dicts
    """
    config = load_config_from_sheets()
    return config.get("exclusions", [])


def load_presets() -> List[Dict]:
    """
    Get list of search presets.
    
    Returns:
        List of preset dicts with keys: preset_name, topics_csv, exclusions_csv, days_back, max_results
    """
    config = load_config_from_sheets()
    return config.get("presets", [])


def get_preset_by_name(preset_name: str) -> Optional[Dict]:
    """
    Get a specific preset by name.
    
    Args:
        preset_name: Name of the preset to find
    
    Returns:
        Preset dict or None if not found
    """
    presets = load_presets()
    for preset in presets:
        if preset.get("preset_name") == preset_name:
            return preset
    return None


def check_author_status(authors_str: str, whitelist: List[str], blacklist: List[str]) -> Optional[str]:
    """
    Check if any author in the paper is whitelisted or blacklisted.
    
    Args:
        authors_str: Comma-separated author string from paper
        whitelist: List of whitelisted author names
        blacklist: List of blacklisted author names
    
    Returns:
        "whitelisted", "blacklisted", or None
    """
    if not authors_str:
        return None
    
    authors_lower = authors_str.lower()
    
    # Check blacklist first (takes priority for exclusion)
    for author in blacklist:
        if author.lower() in authors_lower:
            return "blacklisted"
    
    # Check whitelist
    for author in whitelist:
        if author.lower() in authors_lower:
            return "whitelisted"
    
    return None
