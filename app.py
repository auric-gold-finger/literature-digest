"""
Literature Digest - Streamlit App

An automated research feed that scans PubMed for longevity research,
triages papers by relevance and evidence quality, and provides on-demand summaries.
"""

import streamlit as st
from datetime import date

from utils.pubmed import search_pubmed, fetch_pubmed_details, DEFAULT_TOPIC
from utils.altmetric import enrich_papers_with_altmetric
from utils.openai_helpers import batch_triage_papers, summarize_paper


# --- PAGE CONFIG --- #
st.set_page_config(
    page_title="Literature Digest",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS --- #
st.markdown("""
<style>
    .paper-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 4px solid #4CAF50;
    }
    .metric-row {
        display: flex;
        gap: 1rem;
        margin: 0.5rem 0;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# --- INITIALIZE SESSION STATE --- #
if "papers" not in st.session_state:
    st.session_state.papers = None
if "summaries" not in st.session_state:
    st.session_state.summaries = {}
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None


# --- SIDEBAR --- #
with st.sidebar:
    st.title("📚 Literature Digest")
    st.markdown("*Automated longevity research feed*")
    
    st.divider()
    
    # Search parameters
    st.subheader("🔍 Search Settings")
    
    days_back = st.slider(
        "Days to search",
        min_value=1,
        max_value=30,
        value=7,
        help="How many days back to search for new papers"
    )
    
    max_results = st.slider(
        "Max results",
        min_value=50,
        max_value=500,
        value=200,
        step=50,
        help="Maximum number of papers to fetch"
    )
    
    st.divider()
    
    # Filters
    st.subheader("🎛️ Filters")
    
    min_relevance = st.slider(
        "Min relevance score",
        min_value=0,
        max_value=10,
        value=5,
        help="Only show papers with relevance >= this value"
    )
    
    min_evidence = st.slider(
        "Min evidence score",
        min_value=0,
        max_value=10,
        value=0,
        help="Only show papers with evidence quality >= this value"
    )
    
    sort_by = st.selectbox(
        "Sort by",
        options=["Relevance Score", "Evidence Score", "Altmetric Score", "Date"],
        index=0
    )
    
    st.divider()
    
    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        # Clear cached data
        st.cache_data.clear()
        st.session_state.papers = None
        st.session_state.summaries = {}
        st.rerun()
    
    if st.session_state.last_refresh:
        st.caption(f"Last refresh: {st.session_state.last_refresh}")


# --- MAIN CONTENT --- #
st.title("📖 Weekly Longevity Research Digest")
st.markdown(f"*Generated on {date.today().strftime('%B %d, %Y')}*")


def fetch_and_process_papers(days: int, max_results: int) -> list[dict]:
    """Fetch papers from PubMed, enrich with Altmetric, and triage with AI."""
    
    with st.status("🔬 Fetching and processing papers...", expanded=True) as status:
        # Step 1: Search PubMed
        st.write("📥 Searching PubMed...")
        pmids = search_pubmed(DEFAULT_TOPIC, days=days, max_results=max_results)
        st.write(f"   Found {len(pmids)} papers")
        
        if not pmids:
            status.update(label="No papers found", state="error")
            return []
        
        # Step 2: Fetch details
        st.write("📄 Fetching paper details...")
        papers = fetch_pubmed_details(pmids)
        st.write(f"   Retrieved {len(papers)} papers with abstracts")
        
        # Step 3: Deduplicate
        seen_titles = set()
        seen_dois = set()
        unique_papers = []
        
        for paper in papers:
            title_key = paper["title"].lower()[:100]
            doi = paper.get("doi")
            
            if title_key not in seen_titles and (not doi or doi not in seen_dois):
                seen_titles.add(title_key)
                if doi:
                    seen_dois.add(doi)
                unique_papers.append(paper)
        
        st.write(f"   {len(unique_papers)} unique papers after deduplication")
        
        # Step 4: Altmetric enrichment
        st.write("📊 Fetching Altmetric scores...")
        progress_bar = st.progress(0)
        
        def altmetric_progress(current, total):
            progress_bar.progress(current / total)
        
        papers = enrich_papers_with_altmetric(unique_papers, altmetric_progress)
        progress_bar.empty()
        
        # Step 5: AI triage
        st.write("🤖 AI scoring papers (batched)...")
        triage_progress = st.progress(0)
        
        def triage_progress_callback(current, total):
            triage_progress.progress(current / total)
        
        papers = batch_triage_papers(papers, batch_size=10, progress_callback=triage_progress_callback)
        triage_progress.empty()
        
        # Count successful triages
        successful = sum(1 for p in papers if p.get("triage_score", -1) >= 0)
        st.write(f"   Successfully scored {successful}/{len(papers)} papers")
        
        status.update(label="✅ Processing complete!", state="complete")
    
    return papers


# Load or fetch papers
if st.session_state.papers is None:
    papers = fetch_and_process_papers(days_back, max_results)
    st.session_state.papers = papers
    st.session_state.last_refresh = date.today().strftime("%Y-%m-%d %H:%M")
else:
    papers = st.session_state.papers


# Filter and sort papers
if papers:
    # Apply filters
    filtered_papers = [
        p for p in papers
        if p.get("triage_score", 0) >= min_relevance
        and p.get("evidence_score", 0) >= min_evidence
    ]
    
    # Apply sorting
    sort_key_map = {
        "Relevance Score": lambda p: (p.get("triage_score", 0), p.get("altmetric", {}).get("score", 0)),
        "Evidence Score": lambda p: (p.get("evidence_score", 0), p.get("triage_score", 0)),
        "Altmetric Score": lambda p: p.get("altmetric", {}).get("score", 0),
        "Date": lambda p: p.get("date", "0000-00-00")
    }
    
    filtered_papers = sorted(
        filtered_papers,
        key=sort_key_map[sort_by],
        reverse=True
    )
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Papers", len(papers))
    with col2:
        st.metric("After Filters", len(filtered_papers))
    with col3:
        avg_relevance = sum(p.get("triage_score", 0) for p in filtered_papers) / max(len(filtered_papers), 1)
        st.metric("Avg Relevance", f"{avg_relevance:.1f}")
    with col4:
        high_impact = sum(1 for p in filtered_papers if p.get("altmetric", {}).get("score", 0) > 10)
        st.metric("High Altmetric (>10)", high_impact)
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["📊 Top Papers", "📋 All Results"])
    
    with tab1:
        st.subheader("Top 10 Papers")
        st.caption("Click 'Summarize' to generate an AI summary for any paper")
        
        top_papers = filtered_papers[:10]
        
        for i, paper in enumerate(top_papers):
            with st.expander(
                f"**{i+1}. {paper['title'][:100]}{'...' if len(paper['title']) > 100 else ''}**",
                expanded=(i < 3)  # Expand top 3 by default
            ):
                # Metrics row
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Relevance", f"{paper.get('triage_score', 'N/A')}/10")
                with col2:
                    st.metric("Evidence", f"{paper.get('evidence_score', 'N/A')}/10")
                with col3:
                    altmetric = paper.get("altmetric", {})
                    st.metric("Altmetric", altmetric.get("score", 0))
                with col4:
                    st.metric("Date", paper.get("date", "Unknown"))
                
                # Paper details
                st.markdown(f"**Authors:** {paper.get('authors', 'Unknown')}")
                st.markdown(f"**Journal:** {paper.get('journal', 'Unknown')}")
                
                # Social metrics
                altmetric = paper.get("altmetric", {})
                st.caption(f"🐦 Twitter: {altmetric.get('twitter', 0)} | 📰 News: {altmetric.get('news', 0)}")
                
                # Abstract
                with st.container():
                    st.markdown("**Abstract:**")
                    st.markdown(paper.get("abstract", "No abstract available.")[:1000] + "...")
                
                # Summary section
                paper_key = paper.get("pmid") or paper.get("title")
                
                if paper_key in st.session_state.summaries:
                    st.success("**AI Summary:**")
                    st.markdown(st.session_state.summaries[paper_key])
                else:
                    if st.button(f"✨ Generate Summary", key=f"sum_{i}"):
                        with st.spinner("Generating summary..."):
                            summary = summarize_paper(paper["title"], paper["abstract"])
                            st.session_state.summaries[paper_key] = summary
                            st.rerun()
                
                # Link to paper
                st.link_button("📄 Read on PubMed", paper.get("url", "https://pubmed.ncbi.nlm.nih.gov/"))
    
    with tab2:
        st.subheader(f"All Filtered Results ({len(filtered_papers)} papers)")
        
        # Create a dataframe-like view
        for i, paper in enumerate(filtered_papers):
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{paper['title'][:80]}{'...' if len(paper['title']) > 80 else ''}**")
                st.caption(f"{paper.get('authors', 'Unknown')[:50]}")
            with col2:
                st.metric("Rel", paper.get("triage_score", "?"), label_visibility="collapsed")
            with col3:
                st.metric("Evid", paper.get("evidence_score", "?"), label_visibility="collapsed")
            with col4:
                st.metric("Alt", paper.get("altmetric", {}).get("score", 0), label_visibility="collapsed")
            with col5:
                st.link_button("Open", paper.get("url", "#"), use_container_width=True)
            
            if i < len(filtered_papers) - 1:
                st.divider()
    
    # Export section
    st.divider()
    st.subheader("📥 Export")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Generate HTML export
        def generate_html_export(papers_to_export):
            html = f"""<html><head><meta charset='UTF-8'><title>Literature Digest - {date.today()}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; margin: 2em; background-color: #f9f9f9; color: #222; line-height: 1.6; }}
  h1 {{ font-size: 2em; }}
  .paper {{ border-left: 4px solid #4CAF50; padding: 1rem; margin: 1rem 0; background: white; }}
  .metrics {{ color: #666; font-size: 0.9em; }}
  a {{ color: #1a73e8; }}
</style></head><body>
<h1>📚 Literature Digest - {date.today()}</h1>
<p>Generated with AI triage scoring</p>
"""
            for p in papers_to_export:
                summary = st.session_state.summaries.get(p.get("pmid") or p.get("title"), "")
                summary_html = f"<p><strong>Summary:</strong> {summary}</p>" if summary else ""
                
                html += f"""
<div class="paper">
  <h3><a href="{p.get('url', '#')}">{p['title']}</a></h3>
  <p class="metrics">Relevance: {p.get('triage_score', '?')}/10 | Evidence: {p.get('evidence_score', '?')}/10 | Altmetric: {p.get('altmetric', {}).get('score', 0)}</p>
  <p><em>{p.get('authors', 'Unknown')}</em> - {p.get('journal', 'Unknown')} ({p.get('date', 'Unknown')})</p>
  {summary_html}
  <p>{p.get('abstract', '')[:500]}...</p>
</div>
"""
            html += "</body></html>"
            return html
        
        html_export = generate_html_export(filtered_papers[:20])
        st.download_button(
            label="📄 Download HTML Digest",
            data=html_export,
            file_name=f"literature_digest_{date.today()}.html",
            mime="text/html",
            use_container_width=True
        )
    
    with col2:
        # CSV export
        import pandas as pd
        
        df_data = [{
            "Title": p["title"],
            "Authors": p.get("authors", ""),
            "Journal": p.get("journal", ""),
            "Date": p.get("date", ""),
            "Relevance": p.get("triage_score", ""),
            "Evidence": p.get("evidence_score", ""),
            "Altmetric": p.get("altmetric", {}).get("score", 0),
            "URL": p.get("url", ""),
            "DOI": p.get("doi", "")
        } for p in filtered_papers]
        
        df = pd.DataFrame(df_data)
        csv = df.to_csv(index=False).encode("utf-8")
        
        st.download_button(
            label="📊 Download CSV",
            data=csv,
            file_name=f"literature_digest_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    st.warning("No papers found. Try adjusting your search parameters or click Refresh.")


# --- FOOTER --- #
st.divider()
st.caption(
    "Built with Streamlit • Data from PubMed & Altmetric • AI scoring by GPT-4o-mini • "
    "[View on GitHub](https://github.com/yourusername/literature-digest)"
)
