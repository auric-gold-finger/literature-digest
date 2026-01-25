"""
Tests for utils/constants.py

Validates that constants have sensible values and types.
"""

import pytest
from utils.constants import (
    # Gemini config
    DEFAULT_GEMINI_MODEL,
    TRIAGE_BATCH_SIZE,
    TRIAGE_ABSTRACT_MAX_CHARS,
    SUMMARY_ABSTRACT_MAX_CHARS,
    TRIAGE_MAX_OUTPUT_TOKENS,
    SUMMARY_MAX_OUTPUT_TOKENS,
    TRIAGE_TEMPERATURE,
    SUMMARY_TEMPERATURE,
    # PubMed config
    DEFAULT_DAYS_BACK,
    DEFAULT_MAX_RESULTS,
    INTERSECTION_MAX_RESULTS,
    MAX_AUTHORS_DISPLAY,
    # Scoring thresholds
    DAILY_MIN_COMBINED_SCORE,
    FRONTIER_MIN_COMBINED_SCORE,
    DAILY_TOP_N_PAPERS,
    FRONTIER_TOP_N_PAPERS,
    WHITELIST_RELEVANCE_BOOST,
    MAX_RELEVANCE_SCORE,
    # Deduplication
    DEDUP_LOOKBACK_DAYS,
    # Retry config
    MAX_RETRIES,
    INITIAL_RETRY_DELAY_SECONDS,
)


class TestGeminiConstants:
    """Tests for Gemini AI configuration constants."""

    def test_model_name_is_string(self):
        """Model name should be a non-empty string."""
        assert isinstance(DEFAULT_GEMINI_MODEL, str)
        assert len(DEFAULT_GEMINI_MODEL) > 0
        assert "gemini" in DEFAULT_GEMINI_MODEL.lower()

    def test_batch_size_reasonable(self):
        """Batch size should be between 1 and 50."""
        assert 1 <= TRIAGE_BATCH_SIZE <= 50

    def test_abstract_limits_reasonable(self):
        """Abstract character limits should be reasonable."""
        assert 500 <= TRIAGE_ABSTRACT_MAX_CHARS <= 5000
        assert 1000 <= SUMMARY_ABSTRACT_MAX_CHARS <= 10000
        # Summary should allow more chars than triage
        assert SUMMARY_ABSTRACT_MAX_CHARS >= TRIAGE_ABSTRACT_MAX_CHARS

    def test_temperature_in_range(self):
        """Temperature should be between 0 and 1."""
        assert 0.0 <= TRIAGE_TEMPERATURE <= 1.0
        assert 0.0 <= SUMMARY_TEMPERATURE <= 1.0

    def test_output_tokens_positive(self):
        """Output token limits should be positive."""
        assert TRIAGE_MAX_OUTPUT_TOKENS > 0
        assert SUMMARY_MAX_OUTPUT_TOKENS > 0


class TestPubMedConstants:
    """Tests for PubMed configuration constants."""

    def test_days_back_reasonable(self):
        """Days back should be between 1 and 365."""
        assert 1 <= DEFAULT_DAYS_BACK <= 365

    def test_max_results_reasonable(self):
        """Max results should be between 10 and 1000."""
        assert 10 <= DEFAULT_MAX_RESULTS <= 1000
        assert 10 <= INTERSECTION_MAX_RESULTS <= 1000

    def test_authors_display_reasonable(self):
        """Max authors display should be between 1 and 10."""
        assert 1 <= MAX_AUTHORS_DISPLAY <= 10


class TestScoringConstants:
    """Tests for scoring threshold constants."""

    def test_combined_scores_reasonable(self):
        """Combined score thresholds should be reasonable."""
        # Max possible score is 30 (3 dimensions * 10)
        assert 0 <= DAILY_MIN_COMBINED_SCORE <= 30
        assert 0 <= FRONTIER_MIN_COMBINED_SCORE <= 30
        # Frontier threshold should be lower or equal to daily
        assert FRONTIER_MIN_COMBINED_SCORE <= DAILY_MIN_COMBINED_SCORE

    def test_top_n_papers_positive(self):
        """Top N papers should be positive integers."""
        assert DAILY_TOP_N_PAPERS > 0
        assert FRONTIER_TOP_N_PAPERS > 0

    def test_whitelist_boost_reasonable(self):
        """Whitelist boost should be between 1 and 5."""
        assert 1 <= WHITELIST_RELEVANCE_BOOST <= 5

    def test_max_relevance_score(self):
        """Max relevance score should be 10."""
        assert MAX_RELEVANCE_SCORE == 10


class TestDeduplicationConstants:
    """Tests for deduplication configuration constants."""

    def test_lookback_days_reasonable(self):
        """Lookback days should be between 7 and 90."""
        assert 7 <= DEDUP_LOOKBACK_DAYS <= 90


class TestRetryConstants:
    """Tests for retry configuration constants."""

    def test_max_retries_reasonable(self):
        """Max retries should be between 1 and 10."""
        assert 1 <= MAX_RETRIES <= 10

    def test_initial_delay_reasonable(self):
        """Initial retry delay should be between 1 and 120 seconds."""
        assert 1 <= INITIAL_RETRY_DELAY_SECONDS <= 120
