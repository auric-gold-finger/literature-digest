"""
Tests for utils/query_builder.py

Tests the PubMed query construction logic.
"""

import pytest
from utils.query_builder import (
    build_pubmed_query,
    build_intersection_query,
    get_query_summary,
    validate_query,
    BASE_AGING_FILTER,
    INTERSECTION_TEMPLATES
)


class TestBuildPubmedQuery:
    """Tests for build_pubmed_query function."""

    def test_empty_topics_returns_base_filter(self):
        """Empty topics list should return base aging filter."""
        result = build_pubmed_query([], [])
        assert result == BASE_AGING_FILTER

    def test_empty_topics_without_base_filter(self):
        """Empty topics without base filter should return empty string."""
        result = build_pubmed_query([], [], include_base_filter=False)
        assert result == ""

    def test_single_topic(self):
        """Single topic should be wrapped correctly."""
        topics = [{"name": "CVD", "query_fragment": "cardiovascular[tiab]"}]
        result = build_pubmed_query(topics, [])

        assert "cardiovascular[tiab]" in result
        assert BASE_AGING_FILTER in result
        assert " AND " in result

    def test_multiple_topics_combined_with_or(self):
        """Multiple topics should be combined with OR."""
        topics = [
            {"name": "CVD", "query_fragment": "cardiovascular[tiab]"},
            {"name": "Metabolism", "query_fragment": "metabolism[tiab]"}
        ]
        result = build_pubmed_query(topics, [])

        assert "cardiovascular[tiab]" in result
        assert "metabolism[tiab]" in result
        assert " OR " in result

    def test_exclusions_add_not_clauses(self):
        """Exclusions should add NOT clauses."""
        topics = [{"name": "CVD", "query_fragment": "cardiovascular[tiab]"}]
        exclusions = ["pediatric", "neonatal"]
        result = build_pubmed_query(topics, exclusions)

        assert "NOT pediatric[tiab]" in result
        assert "NOT neonatal[tiab]" in result

    def test_topics_with_empty_fragment_ignored(self):
        """Topics with empty query_fragment should be ignored."""
        topics = [
            {"name": "CVD", "query_fragment": "cardiovascular[tiab]"},
            {"name": "Empty", "query_fragment": ""}
        ]
        result = build_pubmed_query(topics, [])

        assert "cardiovascular[tiab]" in result
        # Empty fragment should not cause issues

    def test_without_base_filter(self):
        """Should work without base filter when specified."""
        topics = [{"name": "CVD", "query_fragment": "cardiovascular[tiab]"}]
        result = build_pubmed_query(topics, [], include_base_filter=False)

        assert "cardiovascular[tiab]" in result
        assert BASE_AGING_FILTER not in result


class TestBuildIntersectionQuery:
    """Tests for build_intersection_query function."""

    def test_empty_groups_returns_empty(self):
        """Empty concept groups should return empty string."""
        result = build_intersection_query([])
        assert result == ""

    def test_empty_groups_with_base_filter(self):
        """Empty groups with base filter should return base filter."""
        result = build_intersection_query([], include_base_filter=True)
        assert result == BASE_AGING_FILTER

    def test_single_group_no_and(self):
        """Single concept group should not have AND between groups."""
        groups = [['term1[tiab]', 'term2[tiab]']]
        result = build_intersection_query(groups)

        assert "term1[tiab]" in result
        assert "term2[tiab]" in result
        # Should have OR within group, but no AND between groups
        assert " OR " in result

    def test_two_groups_combined_with_and(self):
        """Two concept groups should be combined with AND."""
        groups = [
            ['GLP-1[tiab]', 'semaglutide[tiab]'],
            ['sarcopenia[tiab]', 'muscle[tiab]']
        ]
        result = build_intersection_query(groups)

        assert "GLP-1[tiab]" in result
        assert "sarcopenia[tiab]" in result
        assert " AND " in result

    def test_exclusions_added(self):
        """Exclusions should add NOT clauses to intersection query."""
        groups = [['term1[tiab]'], ['term2[tiab]']]
        exclusions = ["pediatric"]
        result = build_intersection_query(groups, exclusions)

        assert "NOT pediatric[tiab]" in result

    def test_default_no_base_filter(self):
        """By default, intersection queries should NOT include base filter."""
        groups = [['term1[tiab]'], ['term2[tiab]']]
        result = build_intersection_query(groups)

        assert BASE_AGING_FILTER not in result


class TestIntersectionTemplates:
    """Tests for pre-defined intersection templates."""

    def test_all_templates_have_required_fields(self):
        """All templates should have name and groups fields."""
        for key, template in INTERSECTION_TEMPLATES.items():
            assert "name" in template, f"Template {key} missing 'name'"
            assert "groups" in template, f"Template {key} missing 'groups'"
            assert len(template["groups"]) >= 2, f"Template {key} should have at least 2 groups"

    def test_all_templates_generate_valid_queries(self):
        """All templates should generate valid queries."""
        for key, template in INTERSECTION_TEMPLATES.items():
            result = build_intersection_query(template["groups"])
            validation = validate_query(result)
            assert validation["valid"], f"Template {key} generated invalid query: {validation['warnings']}"

    def test_template_keys_match_expected(self):
        """Template keys should match expected set."""
        expected_keys = {
            "glp1_muscle", "menopause_bone", "exercise_cognition",
            "statins_muscle", "apob_interventions", "protein_aging",
            "sleep_cognition", "vo2max_mortality", "hrt_cardiovascular",
            "zone2_mitochondria"
        }
        assert set(INTERSECTION_TEMPLATES.keys()) == expected_keys


class TestValidateQuery:
    """Tests for validate_query function."""

    def test_valid_query(self):
        """Valid query should pass validation."""
        query = '(aging[MeSH]) AND (exercise[tiab])'
        result = validate_query(query)

        assert result["valid"] is True
        assert result["warnings"] == []
        assert result["char_count"] == len(query)

    def test_unbalanced_parentheses(self):
        """Unbalanced parentheses should generate warning."""
        query = '(aging[MeSH] AND (exercise[tiab])'
        result = validate_query(query)

        assert result["valid"] is False
        assert any("parentheses" in w.lower() for w in result["warnings"])

    def test_empty_query(self):
        """Empty query should generate warning."""
        result = validate_query("")

        assert result["valid"] is False
        assert any("empty" in w.lower() for w in result["warnings"])

    def test_very_long_query(self):
        """Very long query should generate warning."""
        query = "a" * 5000
        result = validate_query(query)

        assert result["valid"] is False
        assert any("long" in w.lower() for w in result["warnings"])


class TestGetQuerySummary:
    """Tests for get_query_summary function."""

    def test_with_topics_and_exclusions(self):
        """Summary should include topics and exclusions."""
        topics = [
            {"name": "CVD"},
            {"name": "Metabolism"}
        ]
        exclusions = ["pediatric", "animals"]
        result = get_query_summary(topics, exclusions)

        assert "CVD" in result
        assert "Metabolism" in result
        assert "pediatric" in result
        assert "animals" in result

    def test_empty_topics(self):
        """Empty topics should show 'None selected'."""
        result = get_query_summary([], [])
        assert "None selected" in result

    def test_empty_exclusions(self):
        """Empty exclusions should show 'None'."""
        topics = [{"name": "CVD"}]
        result = get_query_summary(topics, [])
        assert "None" in result
