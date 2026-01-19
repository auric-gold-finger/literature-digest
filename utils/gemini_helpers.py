"""
Gemini utilities for batch triage scoring and paper summarization.

Includes three-dimensional scoring: relevance, evidence quality, and actionability.
"""

import json
import streamlit as st
from google import genai
from google.genai import types
from typing import List, Optional, Callable


@st.cache_resource
def get_genai_client():
    """Get cached Google GenAI client instance."""
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


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


def batch_triage_papers(
    papers: list[dict],
    batch_size: int = 10,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    whitelist: Optional[List[str]] = None,
    blacklist: Optional[List[str]] = None
) -> list[dict]:
    """
    Score papers for relevance, evidence quality, and actionability using batched Gemini calls.
    
    Also applies author whitelist boost (+2 relevance) and filters out blacklisted authors.
    
    Args:
        papers: List of paper dicts with 'title', 'abstract', 'altmetric', 'authors' keys
        batch_size: Number of papers per API call
        progress_callback: Optional callback(current_batch, total_batches)
        whitelist: List of whitelisted author names (get +2 relevance boost)
        blacklist: List of blacklisted author names (will be filtered out)
    
    Returns:
        Papers list with 'triage_score', 'evidence_score', 'actionability_score' added.
        Blacklisted papers are removed from the list.
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
        if filtered_count > 0:
            st.info(f"Filtered out {filtered_count} papers from blacklisted authors")
    
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
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1000
                )
            )
            
            content = response.text.strip()
            
            # Parse JSON response
            # Handle potential markdown code blocks
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
            st.warning(f"Batch {batch_idx + 1} triage failed: {e}")
        
        if progress_callback:
            progress_callback(batch_idx + 1, total_batches)
    
    # Apply whitelist boost (+2 to relevance, capped at 10)
    for paper in papers:
        if paper.get("whitelisted") and paper["triage_score"] >= 0:
            paper["triage_score"] = min(10, paper["triage_score"] + 2)
    
    return papers


def _author_in_list(authors_str: str, author_list: List[str]) -> bool:
    """Check if any author from the list appears in the authors string."""
    if not authors_str or not author_list:
        return False
    authors_lower = authors_str.lower()
    return any(author.lower() in authors_lower for author in author_list)


SUMMARIZE_PROMPT = """You are a scientific analyst summarizing research for a longevity-focused medical team.

Summarize the following abstract in 2-3 sentences:
1. Start with the study type (RCT, meta-analysis, cross-sectional, cohort, animal study, etc.)
2. Highlight findings that are actionable, clinically meaningful, or novel
3. Explain why it's relevant to someone interested in longevity and healthspan (like a Peter Attia audience)

Be concise but informative. Focus on practical takeaways.

Title: {title}
Abstract: {abstract}
"""


@st.cache_data(ttl="7d", show_spinner=False)
def summarize_paper(title: str, abstract: str) -> str:
    """
    Generate a Gemini summary of a paper.
    
    Args:
        title: Paper title
        abstract: Paper abstract
    
    Returns:
        2-3 sentence summary
    """
    client = get_genai_client()
    
    prompt = SUMMARIZE_PROMPT.format(title=title, abstract=abstract)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=300
            )
        )
        return response.text.strip()
    except Exception as e:
        return f"Summary unavailable: {e}"
