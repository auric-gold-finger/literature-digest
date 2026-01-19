"""
Gemini utilities for headless execution (non-Streamlit).

Batch triage scoring without Streamlit dependencies.
"""

import os
import json
from google import genai
from google.genai import types
from typing import List, Dict, Optional


_client_cache = {}

# Usage tracking
_usage_stats = {
    "api_calls": 0,
    "triage_calls": 0,
    "summary_calls": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "errors": 0
}


def get_usage_stats() -> dict:
    """Get current usage statistics for this session."""
    return _usage_stats.copy()


def reset_usage_stats():
    """Reset usage statistics (call at start of each run)."""
    global _usage_stats
    _usage_stats = {
        "api_calls": 0,
        "triage_calls": 0,
        "summary_calls": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "errors": 0
    }


def _track_usage(response, call_type: str = "other"):
    """Track token usage from a Gemini response."""
    _usage_stats["api_calls"] += 1
    
    if call_type == "triage":
        _usage_stats["triage_calls"] += 1
    elif call_type == "summary":
        _usage_stats["summary_calls"] += 1
    
    # Extract token counts if available
    try:
        if hasattr(response, 'usage_metadata'):
            metadata = response.usage_metadata
            _usage_stats["total_input_tokens"] += getattr(metadata, 'prompt_token_count', 0)
            _usage_stats["total_output_tokens"] += getattr(metadata, 'candidates_token_count', 0)
    except Exception:
        pass  # Token tracking is best-effort


def get_genai_client():
    """Get Google GenAI client instance (cached)."""
    if "client" not in _client_cache:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        _client_cache["client"] = genai.Client(api_key=api_key)
    return _client_cache["client"]


BATCH_TRIAGE_PROMPT = """You are an expert assistant for a longevity-focused research team (similar to Peter Attia's clinic).

Given a batch of research papers (title, abstract, altmetric score), score each paper on THREE dimensions:

1. **Relevance Score (0-10)**: How important is this paper for longevity, healthspan, or clinical decision-making?
   - 9-10: Directly addresses core longevity topics (cardiovascular, metabolism, exercise, sleep, neurodegeneration, cancer)
   - 7-8: Related to aging interventions, biomarkers, or healthspan optimization
   - 5-6: Tangentially relevant or narrow population
   - 0-4: Animal-only, mechanistic, rare diseases, or unrelated fields
   - Papers with no abstract should score 0-2

2. **Evidence Quality Score (0-10)**: How strong and credible is the evidence?
   - 9-10: Large human RCTs, high-quality meta-analyses, Mendelian randomization
   - 7-8: Well-designed observational studies, smaller RCTs, systematic reviews
   - 5-6: Cross-sectional studies, case-control, pilot trials
   - 0-4: Animal studies, in vitro, case reports, opinion pieces

3. **Actionability Score (0-10)**: How clinically actionable is this finding for a practicing physician TODAY?
   - 9-10: Immediate practice change warranted (new treatment, screening, risk factor)
   - 7-8: Reinforces or refines current clinical guidelines
   - 5-6: Useful for patient counseling or future consideration
   - 0-4: Basic science, requires more research, no clinical application yet

Return a JSON array with objects containing:
- "index": the paper's index from the input (0-based)
- "relevance": relevance score (integer 0-10)
- "evidence": evidence quality score (integer 0-10)
- "actionability": actionability score (integer 0-10)

Return ONLY the JSON array, no other text.

Papers to score:
"""


def _author_in_list(authors_str: str, author_list: List[str]) -> bool:
    """Check if any author from the list appears in the authors string."""
    if not authors_str or not author_list:
        return False
    authors_lower = authors_str.lower()
    return any(author.lower() in authors_lower for author in author_list)


def batch_triage_papers(
    papers: List[Dict],
    batch_size: int = 10,
    whitelist: Optional[List[str]] = None,
    blacklist: Optional[List[str]] = None,
    verbose: bool = False
) -> List[Dict]:
    """
    Score papers for relevance, evidence quality, and actionability using batched Gemini calls.
    
    Args:
        papers: List of paper dicts with 'title', 'abstract', 'altmetric', 'authors' keys
        batch_size: Number of papers per API call
        whitelist: List of whitelisted author names (get +2 relevance boost)
        blacklist: List of blacklisted author names (will be filtered out)
        verbose: Print progress information
    
    Returns:
        Papers list with scores added. Blacklisted papers are removed.
    """
    client = get_genai_client()
    
    whitelist = whitelist or []
    blacklist = blacklist or []
    
    # Filter out blacklisted authors first
    if blacklist:
        original_count = len(papers)
        papers = [
            p for p in papers 
            if not _author_in_list(p.get("authors", ""), blacklist)
        ]
        filtered_count = original_count - len(papers)
        if filtered_count > 0 and verbose:
            print(f"Filtered out {filtered_count} papers from blacklisted authors")
    
    # Initialize scores
    for paper in papers:
        paper["triage_score"] = -1
        paper["evidence_score"] = -1
        paper["actionability_score"] = -1
        paper["whitelisted"] = _author_in_list(paper.get("authors", ""), whitelist)
    
    # Process in batches
    total_batches = (len(papers) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(papers))
        batch = papers[start:end]
        
        if verbose:
            print(f"Processing batch {batch_idx + 1}/{total_batches}...")
        
        # Build batch prompt
        papers_text = ""
        for i, paper in enumerate(batch):
            altmetric_score = paper.get("altmetric", {}).get("score", 0)
            papers_text += f"""
---
Index: {i}
Title: {paper['title']}
Abstract: {paper['abstract'][:1500]}...
Altmetric Score: {altmetric_score}
"""
        
        prompt = BATCH_TRIAGE_PROMPT + papers_text
        
        try:
            response = client.models.generate_content(
                model='gemini-3-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1000
                )
            )
            
            _track_usage(response, call_type="triage")
            content = response.text.strip()
            
            # Parse JSON response
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            scores = json.loads(content)
            
            # Apply scores to papers
            for score_obj in scores:
                idx = score_obj.get("index", -1)
                if 0 <= idx < len(batch):
                    batch[idx]["triage_score"] = score_obj.get("relevance", -1)
                    batch[idx]["evidence_score"] = score_obj.get("evidence", -1)
                    batch[idx]["actionability_score"] = score_obj.get("actionability", -1)
                    
        except Exception as e:
            _usage_stats["errors"] += 1
            print(f"Batch {batch_idx + 1} triage failed: {e}")
    
    # Apply whitelist boost (+2 to relevance, capped at 10)
    for paper in papers:
        if paper.get("whitelisted") and paper["triage_score"] >= 0:
            paper["triage_score"] = min(10, paper["triage_score"] + 2)
    
    return papers


# --- Paper Summarization ---

SUMMARIZE_PROMPT = """You are Peter Attia, MD—a physician focused on the applied science of longevity. You think mechanistically, obsess over effect sizes, and refuse to accept statistical significance as a proxy for clinical relevance. You've read thousands of papers and have a finely tuned BS detector.

Your job: appraise this paper the way you would on your podcast or in your newsletter. Be direct, skeptical, and precise. No hedging, no academic throat-clearing. If a study is garbage, say so. If it's legitimately important, explain why in concrete terms.

Write in your voice: clear, conversational, occasionally wry. Use short sentences. Avoid jargon when plain language works. Think out loud about what this means for an actual patient sitting in front of you.

Given a paper's title and abstract, provide a structured appraisal with these exact fields:

1. **study_type**: Precise study design. Be specific—"Double-blind RCT" not just "RCT". Include sample size if it's notably large or small.

2. **population**: Who was actually studied? Sample size, age, health status, how they were selected. Flag generalizability issues—most studies are done on WEIRD populations or sick hospitalized patients. Would these results apply to a 55-year-old trying to optimize healthspan?

3. **intervention_exposure**: What exactly was tested? Dose, duration, comparator. The details matter—a 12-week trial of 500mg metformin tells you almost nothing about long-term use at therapeutic doses.

4. **key_finding**: The money shot. One sentence with the actual numbers—HR, OR, absolute risk reduction, mean difference. Include the confidence interval. If the abstract doesn't report effect sizes (a red flag), say so. Don't bury the lede.

5. **clinical_magnitude**: Here's where you earn your keep. Is this effect size actually meaningful? A statistically significant 2% relative risk reduction is noise. Compare to known interventions when possible. What's the NNT? Would you change what you do in clinic based on this?

6. **methodological_notes**: The fine print. Short follow-up? Surrogate endpoints? Residual confounding? Healthy user bias? Industry funding? Multiple comparisons? Call it out. If it's actually a well-designed study, say that too—good methodology deserves credit.

7. **bottom_line**: What do you actually do with this information? Be prescriptive: "This changes nothing" or "Worth discussing with patients who X" or "Finally, good evidence for Y" or "Hypothesis only—needs an RCT." No wishy-washy "more research needed" unless you specify what research.

8. **why_selected**: Why did this paper catch your attention? Novel mechanism? Challenges dogma? Large effect in rigorous design? Practice-changing potential? First human data on something interesting?

Remember: most papers aren't worth reading. Your job is to figure out if this one is, and why.

Return ONLY valid JSON with these exact keys: study_type, population, intervention_exposure, key_finding, clinical_magnitude, methodological_notes, bottom_line, why_selected.
No markdown, no extra text, just the JSON object.

Title: {title}
Abstract: {abstract}
"""


def summarize_paper(title: str, abstract: str) -> dict:
    """
    Generate a structured critical appraisal of a paper using Gemini.
    
    Args:
        title: Paper title
        abstract: Paper abstract
    
    Returns:
        Dict with keys: study_type, population, intervention_exposure, key_finding,
                        clinical_magnitude, methodological_notes, bottom_line, why_selected
        On failure, returns dict with fallback values using first sentence of abstract.
    """
    # Fallback: extract first sentence of abstract
    def get_fallback():
        first_sentence = abstract.split(". ")[0] if abstract else "No abstract available"
        if not first_sentence.endswith("."):
            first_sentence += "."
        return {
            "study_type": "Study",
            "population": "See abstract for details.",
            "intervention_exposure": "See abstract for details.",
            "key_finding": first_sentence[:200] + ("..." if len(first_sentence) > 200 else ""),
            "clinical_magnitude": "Unable to assess from available information.",
            "methodological_notes": "Full appraisal requires review of complete paper.",
            "bottom_line": "Review full text before drawing conclusions.",
            "why_selected": "Scored highly for relevance, evidence quality, and actionability."
        }
    
    if not abstract or len(abstract.strip()) < 50:
        return get_fallback()
    
    try:
        client = get_genai_client()
        
        prompt = SUMMARIZE_PROMPT.format(
            title=title,
            abstract=abstract[:3000]  # Allow longer abstracts for better context
        )
        
        response = client.models.generate_content(
            model='gemini-3-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Lower temp for more consistent critical analysis
                max_output_tokens=1000  # More tokens for detailed appraisal
            )
        )
        
        _track_usage(response, call_type="summary")
        content = response.text.strip()
        
        # Parse JSON response (handle markdown code blocks)
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        summary = json.loads(content)
        
        # Validate required fields
        required = ["study_type", "population", "intervention_exposure", "key_finding", 
                    "clinical_magnitude", "methodological_notes", "bottom_line", "why_selected"]
        if not all(k in summary for k in required):
            return get_fallback()
        
        return summary
        
    except Exception as e:
        _usage_stats["errors"] += 1
        print(f"Summarization failed: {e}")
        return get_fallback()


def summarize_papers_batch(papers: list, verbose: bool = False) -> list:
    """
    Summarize a list of papers, adding 'summary' field to each.
    
    Args:
        papers: List of paper dicts with 'title' and 'abstract' keys
        verbose: Print progress information
    
    Returns:
        Papers list with 'summary' dict added to each
    """
    for i, paper in enumerate(papers):
        if verbose:
            print(f"  Summarizing paper {i + 1}/{len(papers)}...")
        
        paper["summary"] = summarize_paper(
            paper.get("title", ""),
            paper.get("abstract", "")
        )
    
    return papers
