"""
Centralized constants for the Literature Digest application.

This module consolidates magic numbers and configuration values used throughout
the codebase to improve maintainability and reduce duplication.
"""

# =============================================================================
# GEMINI AI CONFIGURATION
# =============================================================================

# Default model for AI scoring and summarization
# Options: "gemini-2.0-flash" (fast), "gemini-2.5-pro" (better quality)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# Number of papers to score in each API call
# Tradeoff: Larger batches = fewer API calls but higher token usage per call
TRIAGE_BATCH_SIZE = 10

# Maximum abstract length for triage scoring (characters)
# Longer abstracts are truncated to stay within token limits
TRIAGE_ABSTRACT_MAX_CHARS = 1500

# Maximum abstract length for detailed summarization (characters)
# Summaries need more context, so allow longer abstracts
SUMMARY_ABSTRACT_MAX_CHARS = 3000

# Maximum output tokens for triage response
TRIAGE_MAX_OUTPUT_TOKENS = 1000

# Maximum output tokens for summary response
SUMMARY_MAX_OUTPUT_TOKENS = 1000

# Temperature for triage scoring (lower = more consistent)
TRIAGE_TEMPERATURE = 0.3

# Temperature for summarization (slightly higher for varied output)
SUMMARY_TEMPERATURE = 0.3

# Temperature for digest summary (conversational)
DIGEST_SUMMARY_TEMPERATURE = 0.5

# Maximum output tokens for digest summary
DIGEST_SUMMARY_MAX_TOKENS = 200


# =============================================================================
# PUBMED CONFIGURATION
# =============================================================================

# Default number of days to search back
DEFAULT_DAYS_BACK = 7

# Maximum number of results to fetch from PubMed
DEFAULT_MAX_RESULTS = 200

# Maximum results for intersection queries (more targeted, fewer needed)
INTERSECTION_MAX_RESULTS = 50

# Number of authors to display before truncating with "et al."
MAX_AUTHORS_DISPLAY = 5

# Default email placeholder for NCBI Entrez API
DEFAULT_ENTREZ_EMAIL = "user@example.com"


# =============================================================================
# SCORING THRESHOLDS
# =============================================================================

# Minimum combined score (relevance + evidence + actionability) for daily digest
# Papers below this threshold are not included
DAILY_MIN_COMBINED_SCORE = 15

# Minimum combined score for frontier digest (lower bar for cutting-edge research)
FRONTIER_MIN_COMBINED_SCORE = 12

# Number of top papers to include in daily digest
DAILY_TOP_N_PAPERS = 5

# Number of top papers to include in frontier digest
FRONTIER_TOP_N_PAPERS = 7

# Relevance score boost for whitelisted authors
WHITELIST_RELEVANCE_BOOST = 2

# Maximum relevance score (cap after boost)
MAX_RELEVANCE_SCORE = 10


# =============================================================================
# DEDUPLICATION
# =============================================================================

# Days to look back for previously posted papers (Notion deduplication)
DEDUP_LOOKBACK_DAYS = 14

# Extended lookback for frontier digest
FRONTIER_DEDUP_LOOKBACK_DAYS = 30


# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

# Maximum retry attempts for transient API errors
MAX_RETRIES = 3

# Initial delay in seconds before first retry (doubles each attempt)
INITIAL_RETRY_DELAY_SECONDS = 30


# =============================================================================
# FRONTIER DIGEST CONFIGURATION
# =============================================================================

# Days to search for frontier digest (longer window for preprints)
FRONTIER_DAYS_BACK = 14

# Frontier scoring weights (different emphasis than daily)
# Formula: rel + (evid * 0.5) + (action * 0.5) + (frontier * 1.5)
FRONTIER_EVIDENCE_WEIGHT = 0.5
FRONTIER_ACTIONABILITY_WEIGHT = 0.5
FRONTIER_FRONTIER_WEIGHT = 1.5
