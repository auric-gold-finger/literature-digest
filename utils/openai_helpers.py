"""
OpenAI utilities for batch triage scoring and paper summarization.
"""

import json
import streamlit as st
from openai import OpenAI


@st.cache_resource
def get_openai_client() -> OpenAI:
    """Get cached OpenAI client instance."""
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


BATCH_TRIAGE_PROMPT = """You are an expert assistant for a longevity-focused research team.

Given a batch of research papers (title, abstract, altmetric score), score each paper on two dimensions:

1. **Relevance Score (0-10)**: How important is this paper for longevity, healthspan, or clinical/personal decision-making?
   - Boost for human studies, clinical trials, meta-analyses, or highly discussed papers (high altmetric)
   - Reduce for animal-only, mechanistic, or unrelated fields
   - Reduce for rare diseases, post-operative outcomes, or topics that don't apply broadly
   - Papers with no abstract should be severely penalized (score 0-2)

2. **Evidence Quality Score (0-10)**: How strong and credible is the evidence?
   - Human RCTs, large meta-analyses: 9-10
   - Observational human studies, small trials: 6-8
   - Animal studies, in vitro: 0-5

Return a JSON array with objects containing:
- "index": the paper's index from the input (0-based)
- "relevance": relevance score (integer 0-10)
- "evidence": evidence quality score (integer 0-10)

Return ONLY the JSON array, no other text.

Papers to score:
"""


def batch_triage_papers(
    papers: list[dict],
    batch_size: int = 10,
    progress_callback=None
) -> list[dict]:
    """
    Score papers for relevance and evidence quality using batched GPT calls.
    
    Args:
        papers: List of paper dicts with 'title', 'abstract', 'altmetric' keys
        batch_size: Number of papers per API call
        progress_callback: Optional callback(current_batch, total_batches)
    
    Returns:
        Papers list with 'triage_score' and 'evidence_score' added
    """
    client = get_openai_client()
    
    # Initialize scores
    for paper in papers:
        paper["triage_score"] = -1
        paper["evidence_score"] = -1
    
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
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
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
                    
        except Exception as e:
            st.warning(f"Batch {batch_idx + 1} triage failed: {e}")
        
        if progress_callback:
            progress_callback(batch_idx + 1, total_batches)
    
    return papers


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
    Generate a GPT-4 summary of a paper.
    
    Args:
        title: Paper title
        abstract: Paper abstract
    
    Returns:
        2-3 sentence summary
    """
    client = get_openai_client()
    
    prompt = SUMMARIZE_PROMPT.format(title=title, abstract=abstract)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Summary unavailable: {e}"
