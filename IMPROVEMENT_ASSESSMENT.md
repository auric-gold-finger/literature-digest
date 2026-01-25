# Literature Digest - Improvement Assessment

**Date:** 2026-01-25
**Branch:** `claude/assess-improvements-2Hocf`

---

## Executive Summary

This assessment identifies key improvements to enhance code quality, maintainability, and performance of the Literature Digest codebase. The project is well-structured for its purpose but has technical debt that should be addressed.

---

## Critical Issues

### 1. Code Duplication (High Priority)

**Problem:** Nearly identical code exists in Streamlit and headless versions:

| Streamlit File | Headless File | Duplication |
|----------------|---------------|-------------|
| `utils/pubmed.py` | `utils/pubmed_headless.py` | ~95% |
| `utils/altmetric.py` | `utils/altmetric_headless.py` | ~95% |
| `utils/gemini_helpers.py` | `utils/gemini_headless.py` | ~70% |

**Impact:**
- Bug fixes must be applied twice
- Inconsistencies between versions (see model name issue below)
- Higher maintenance burden

**Recommendation:** Create shared core modules with thin wrappers:
```
utils/
├── core/
│   ├── pubmed_core.py      # Pure Python logic
│   ├── altmetric_core.py   # Pure Python logic
│   └── gemini_core.py      # Pure Python logic
├── pubmed.py               # Streamlit wrapper with @st.cache_data
├── pubmed_headless.py      # Thin import re-export
└── ...
```

### 2. Model Name Inconsistency (High Priority)

**Problem:** Different Gemini models used in different contexts:
- `gemini_helpers.py` (Streamlit): Uses `gemini-2.5-pro`
- `gemini_headless.py` (Automated): Uses `gemini-2.0-flash`

**Impact:** Inconsistent scoring behavior between UI and automated pipelines.

**Recommendation:** Centralize model selection in a constants module.

### 3. Prompt Inconsistency (High Priority)

**Problem:** Scoring prompts differ between versions:
- `gemini_helpers.py`: Scores on 3 dimensions (relevance, evidence, actionability)
- `gemini_headless.py`: Scores on 4 dimensions (adds frontier score)

**Impact:** Papers scored differently in UI vs automated digest.

**Recommendation:** Use the same 4-dimension scoring everywhere.

---

## Missing Infrastructure

### 4. No Test Suite (High Priority)

**Problem:** Zero unit tests found in the codebase.

**Impact:**
- Regression risk on API changes
- Difficult to validate refactoring
- No confidence in code correctness

**Recommendation:** Add pytest infrastructure with tests for:
- `query_builder.py` (pure functions, easy to test)
- `config_loader.py` (mock file/env inputs)
- JSON parsing in gemini modules

### 5. No Structured Logging (Medium Priority)

**Problem:** Uses `print()` statements for logging.

**Impact:**
- Difficult to parse logs in GitHub Actions
- No log levels (debug, info, warning, error)
- No timestamps in output

**Recommendation:** Use Python's `logging` module with structured output.

---

## Code Quality Issues

### 6. Magic Numbers (Medium Priority)

**Location:** Various files

| Value | Location | Purpose |
|-------|----------|---------|
| `10` | batch_size in gemini modules | Papers per API call |
| `1500` | Abstract truncation | Character limit |
| `3000` | Summary abstract limit | Character limit |
| `5` | Author display limit | Max authors shown |
| `7` | Days back (default) | Search window |
| `200` | Max results | PubMed result limit |
| `15` | Daily score threshold | Minimum combined score |
| `12` | Frontier score threshold | Minimum combined score |

**Recommendation:** Create `utils/constants.py` with named constants.

### 7. Missing Type Hints (Low Priority)

**Problem:** Some functions lack return type hints.

**Recommendation:** Add comprehensive type hints for IDE support.

---

## Performance Opportunities

### 8. Sequential API Calls (Medium Priority)

**Problem:** Altmetric and Gemini summary calls are sequential.

**Impact:**
- 200 papers × 1 Altmetric call = 200+ seconds
- 5 papers × 1 summary call = ~15 seconds

**Recommendation:** Use `concurrent.futures.ThreadPoolExecutor` for parallel API calls with rate limiting.

### 9. No Result Caching Between Runs (Low Priority)

**Problem:** Every automated run fetches full PubMed results.

**Recommendation:** Consider caching PubMed results with timestamp validation (optional optimization).

---

## Documentation Gaps

### 10. Notion Schema Not Documented

**Problem:** The Notion database must have specific property names, but these aren't documented.

**Recommendation:** Add required schema to README.

### 11. API Rate Limits Not Documented

**Problem:** No documentation on why specific limits (batch size, delays) were chosen.

**Recommendation:** Add rate limit table to README.

---

## Security Considerations

### 12. No Input Sanitization for Custom Exclusions

**Problem:** Custom exclusion terms from UI are passed directly to PubMed query.

**Impact:** Potential for malformed queries (not a major security risk for PubMed).

**Recommendation:** Sanitize/validate user input before query construction.

---

## Implemented Improvements (This Branch)

### ✅ Added Constants Module
- Created `utils/constants.py` with centralized configuration values
- Documents the purpose of each constant

### ✅ Added Test Infrastructure
- Created `tests/` directory with pytest configuration
- Added tests for `query_builder.py` functions
- Added tests for constant values validation

### ✅ Fixed Model Inconsistency
- Updated `gemini_helpers.py` to use consistent model name

---

## Recommended Priority Order

1. **Immediate** (this PR):
   - ✅ Constants module
   - ✅ Basic test infrastructure
   - ✅ Fix model inconsistency

2. **Short-term** (next sprint):
   - Unify Streamlit/headless code with shared core
   - Expand test coverage to gemini modules
   - Add structured logging

3. **Medium-term**:
   - Parallel API calls for Altmetric
   - Document Notion schema
   - Add input validation

4. **Long-term**:
   - Result caching
   - Full type hint coverage
   - Observability/monitoring
