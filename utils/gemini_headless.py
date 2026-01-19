"""
Gemini utilities for headless execution (non-Streamlit).

Batch triage scoring without Streamlit dependencies.
"""

import os
import json
import google.generativeai as genai
from typing import List, Dict, Optional


_model_cache = {}


def get_gemini_model(model_name: str = "gemini-2.0-flash"):
    """Get Gemini model instance (cached)."""
    if model_name not in _model_cache:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=api_key)
        _model_cache[model_name] = genai.GenerativeModel(model_name)
    return _model_cache[model_name]


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
    model = get_gemini_model("gemini-2.0-flash")
    
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
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1000
                )
            )
            
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
            print(f"Batch {batch_idx + 1} triage failed: {e}")
    
    # Apply whitelist boost (+2 to relevance, capped at 10)
    for paper in papers:
        if paper.get("whitelisted") and paper["triage_score"] >= 0:
            paper["triage_score"] = min(10, paper["triage_score"] + 2)
    
    return papers


# --- Paper Summarization ---

SUMMARIZE_PROMPT = """You are a scientific analyst summarizing research for a longevity-focused medical team.

Given a paper's title and abstract, provide a structured summary with these exact fields:

1. **study_type**: The type of study (e.g., "RCT", "Meta-analysis", "Cohort study", "Cross-sectional", "Case-control", "Systematic review", "Animal study", "In vitro", "Case report", "Editorial/Opinion")

2. **tldr**: A single sentence (max 25 words) capturing the key finding or conclusion.

3. **key_points**: 1-2 bullet points of actionable or clinically meaningful findings. Each bullet should be a single sentence.

4. **why_selected**: One sentence explaining why this paper matters for a longevity-focused clinician—what makes it worth reading (clinical relevance, novel finding, practice implications, etc.)

Return ONLY valid JSON with these exact keys: study_type, tldr, key_points (array), why_selected.
No markdown, no extra text, just the JSON object.

Title: {title}
Abstract: {abstract}
"""


def summarize_paper(title: str, abstract: str) -> dict:
    """
    Generate a structured summary of a paper using Gemini.
    
    Args:
        title: Paper title
        abstract: Paper abstract
    
    Returns:
        Dict with keys: study_type, tldr, key_points, why_selected
        On failure, returns dict with fallback values using first sentence of abstract.
    """
    # Fallback: extract first sentence of abstract
    def get_fallback():
        first_sentence = abstract.split(". ")[0] if abstract else "No abstract available"
        if not first_sentence.endswith("."):
            first_sentence += "."
        return {
            "study_type": "Study",
            "tldr": first_sentence[:150] + ("..." if len(first_sentence) > 150 else ""),
            "key_points": [],
            "why_selected": "Scored highly for relevance, evidence quality, and actionability."
        }
    
    if not abstract or len(abstract.strip()) < 50:
        return get_fallback()
    
    try:
        model = get_gemini_model("gemini-2.0-flash")
        
        prompt = SUMMARIZE_PROMPT.format(
            title=title,
            abstract=abstract[:2000]  # Truncate very long abstracts
        )
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=500
            )
        )
        
        content = response.text.strip()
        
        # Parse JSON response (handle markdown code blocks)
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        summary = json.loads(content)
        
        # Validate required fields
        required = ["study_type", "tldr", "key_points", "why_selected"]
        if not all(k in summary for k in required):
            return get_fallback()
        
        # Ensure key_points is a list
        if not isinstance(summary["key_points"], list):
            summary["key_points"] = [summary["key_points"]] if summary["key_points"] else []
        
        return summary
        
    except Exception as e:
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
