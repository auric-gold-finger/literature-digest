"""
Literature Digest - Streamlit App

An automated research feed that scans PubMed for longevity research,
triages papers by relevance and evidence quality, and provides on-demand summaries.

Features a two-stage workflow:
1. Fetch: Search PubMed with configurable topics/exclusions + Altmetric enrichment
2. Score: AI triage with relevance, evidence, and actionability scores
"""

import streamlit as st
from datetime import date, datetime

from utils.pubmed import search_pubmed, fetch_pubmed_details
from utils.altmetric import enrich_papers_with_altmetric
from utils.gemini_helpers import batch_triage_papers, summarize_paper
from utils.gsheet_config import (
    load_topics, load_all_topics, load_whitelist, load_blacklist,
    load_exclusions, load_all_exclusions, load_presets, get_preset_by_name,
    refresh_config
)
from utils.query_builder import build_pubmed_query, get_query_summary, validate_query


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
    .whitelisted-badge {
        background-color: #FFD700;
        color: #000;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
        margin-left: 8px;
    }
    .stage-indicator {
        padding: 0.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .stage-fetch {
        background-color: #e3f2fd;
        border-left: 4px solid #2196F3;
    }
    .stage-score {
        background-color: #e8f5e9;
        border-left: 4px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)


# --- INITIALIZE SESSION STATE --- #
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "papers": None,
        "papers_scored": False,
        "summaries": {},
        "last_fetch": None,
        "last_score": None,
        "selected_topics": None,
        "selected_exclusions": None,
        "config_loaded": False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# --- LOAD CONFIG --- #
@st.cache_data(ttl=300, show_spinner=False)
def get_config():
    """Load configuration from Google Sheets or defaults."""
    return {
        "topics": load_all_topics(),
        "exclusions": load_all_exclusions(),
        "presets": load_presets(),
        "whitelist": load_whitelist(),
        "blacklist": load_blacklist()
    }


# Load config
config = get_config()

# Set default selections on first load
if st.session_state.selected_topics is None:
    active_topics = [t["name"] for t in config["topics"] if t.get("active", True)]
    st.session_state.selected_topics = active_topics

if st.session_state.selected_exclusions is None:
    active_exclusions = [e["term"] for e in config["exclusions"] if e.get("active", True)]
    st.session_state.selected_exclusions = active_exclusions


# --- SIDEBAR --- #
with st.sidebar:
    st.title("📚 Literature Digest")
    st.markdown("*Automated longevity research feed*")
    
    st.divider()
    
    # === CONFIG SECTION === #
    st.subheader("⚙️ Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Config", use_container_width=True):
            refresh_config()
            get_config.clear()
            st.session_state.config_loaded = False
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Data", use_container_width=True):
            st.session_state.papers = None
            st.session_state.papers_scored = False
            st.session_state.summaries = {}
            st.rerun()
    
    st.divider()
    
    # === PRESETS SECTION === #
    st.subheader("📚 Presets")
    
    preset_names = ["(Custom)"] + [p["preset_name"] for p in config["presets"]]
    selected_preset = st.selectbox(
        "Load preset",
        options=preset_names,
        index=0,
        help="Select a preset to auto-fill topics and exclusions"
    )
    
    # Apply preset if selected (not Custom)
    if selected_preset != "(Custom)":
        preset = get_preset_by_name(selected_preset)
        if preset and st.button("Apply Preset", use_container_width=True):
            # Parse CSV lists from preset
            preset_topics = [t.strip() for t in preset.get("topics_csv", "").split(",") if t.strip()]
            preset_exclusions = [e.strip() for e in preset.get("exclusions_csv", "").split(",") if e.strip()]
            
            st.session_state.selected_topics = preset_topics
            st.session_state.selected_exclusions = preset_exclusions
            st.session_state.days_back = preset.get("days_back", 7)
            st.session_state.max_results = preset.get("max_results", 200)
            st.rerun()
    
    st.divider()
    
    # === TOPICS SECTION === #
    st.subheader("🔍 Topics")
    
    topic_names = [t["name"] for t in config["topics"]]
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Select All", key="select_all_topics", use_container_width=True):
            st.session_state.selected_topics = topic_names
            st.rerun()
    with col2:
        if st.button("Clear", key="clear_topics", use_container_width=True):
            st.session_state.selected_topics = []
            st.rerun()
    
    selected_topics = st.multiselect(
        "Select topics to search",
        options=topic_names,
        default=st.session_state.selected_topics,
        help="Papers must match at least one of these topics"
    )
    st.session_state.selected_topics = selected_topics
    
    st.divider()
    
    # === EXCLUSIONS SECTION === #
    st.subheader("🚫 Exclusions")
    
    exclusion_terms = [e["term"] for e in config["exclusions"]]
    
    selected_exclusions = st.multiselect(
        "Exclude papers containing",
        options=exclusion_terms,
        default=st.session_state.selected_exclusions,
        help="Papers containing these terms will be excluded"
    )
    st.session_state.selected_exclusions = selected_exclusions
    
    # Custom exclusion input
    custom_exclusion = st.text_input(
        "Add custom exclusion",
        placeholder="e.g., 'mice' or 'zebrafish'",
        help="Add a custom term to exclude (press Enter)"
    )
    if custom_exclusion and custom_exclusion not in selected_exclusions:
        selected_exclusions.append(custom_exclusion)
        st.session_state.selected_exclusions = selected_exclusions
    
    st.divider()
    
    # === SEARCH SETTINGS === #
    st.subheader("📅 Search Settings")
    
    days_back = st.slider(
        "Days to search",
        min_value=1,
        max_value=30,
        value=st.session_state.get("days_back", 7),
        help="How many days back to search for new papers"
    )
    st.session_state.days_back = days_back
    
    max_results = st.slider(
        "Max results",
        min_value=50,
        max_value=500,
        value=st.session_state.get("max_results", 200),
        step=50,
        help="Maximum number of papers to fetch"
    )
    st.session_state.max_results = max_results
    
    st.divider()
    
    # === SORT OPTIONS === #
    st.subheader("📊 Sort & Filter")
    
    # Sort options depend on whether papers have been scored
    if st.session_state.papers_scored:
        sort_options = ["Relevance Score", "Evidence Score", "Actionability Score", "Altmetric Score", "Date"]
    else:
        sort_options = ["Altmetric Score", "Date"]
    
    sort_by = st.selectbox(
        "Sort by",
        options=sort_options,
        index=0
    )
    
    # === AI FILTERS (only shown after scoring) === #
    if st.session_state.papers_scored:
        st.divider()
        st.subheader("🎯 AI Filters")
        
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
        
        min_actionability = st.slider(
            "Min actionability score",
            min_value=0,
            max_value=10,
            value=0,
            help="Only show papers with actionability >= this value"
        )
    else:
        min_relevance = 0
        min_evidence = 0
        min_actionability = 0


# --- MAIN CONTENT --- #
st.title("📖 Longevity Research Digest")
st.markdown(f"*Generated on {date.today().strftime('%B %d, %Y')}*")


# --- BUILD AND SHOW QUERY --- #
# Get selected topic objects
selected_topic_objs = [t for t in config["topics"] if t["name"] in selected_topics]

# Build query
pubmed_query = build_pubmed_query(selected_topic_objs, selected_exclusions)
query_validation = validate_query(pubmed_query)

# Query preview expander
with st.expander("🔎 View PubMed Query", expanded=False):
    st.markdown(get_query_summary(selected_topic_objs, selected_exclusions))
    st.code(pubmed_query, language=None)
    
    if not query_validation["valid"]:
        for warning in query_validation["warnings"]:
            st.warning(warning)
    
    st.caption(f"Query length: {query_validation['char_count']} characters")


# --- STAGE 1: FETCH PAPERS --- #
def fetch_papers(query: str, days: int, max_results: int) -> list[dict]:
    """Fetch papers from PubMed and enrich with Altmetric scores."""
    
    with st.status("🔬 Fetching papers...", expanded=True) as status:
        # Step 1: Search PubMed
        st.write("📥 Searching PubMed...")
        pmids = search_pubmed(query, days=days, max_results=max_results)
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
        
        status.update(label="✅ Papers fetched!", state="complete")
    
    return papers


# --- STAGE 2: AI SCORING --- #
def score_papers(papers: list[dict], whitelist: list[str], blacklist: list[str]) -> list[dict]:
    """Score papers using AI triage with author list processing."""
    
    with st.status("🤖 AI scoring papers...", expanded=True) as status:
        st.write(f"📝 Scoring {len(papers)} papers...")
        st.write(f"   Whitelist: {len(whitelist)} authors | Blacklist: {len(blacklist)} authors")
        
        triage_progress = st.progress(0)
        
        def triage_progress_callback(current, total):
            triage_progress.progress(current / total)
        
        scored_papers = batch_triage_papers(
            papers,
            batch_size=10,
            progress_callback=triage_progress_callback,
            whitelist=whitelist,
            blacklist=blacklist
        )
        triage_progress.empty()
        
        # Count successful triages
        successful = sum(1 for p in scored_papers if p.get("triage_score", -1) >= 0)
        st.write(f"   Successfully scored {successful}/{len(scored_papers)} papers")
        
        whitelisted_count = sum(1 for p in scored_papers if p.get("whitelisted"))
        if whitelisted_count > 0:
            st.write(f"   ⭐ {whitelisted_count} papers from priority authors")
        
        status.update(label="✅ AI scoring complete!", state="complete")
    
    return scored_papers


# --- STAGE INDICATOR AND BUTTONS --- #
col1, col2 = st.columns(2)

with col1:
    fetch_disabled = len(selected_topics) == 0
    if st.button(
        "🔍 Fetch Papers",
        type="primary",
        use_container_width=True,
        disabled=fetch_disabled,
        help="Search PubMed and get Altmetric scores" if not fetch_disabled else "Select at least one topic"
    ):
        st.cache_data.clear()
        papers = fetch_papers(pubmed_query, days_back, max_results)
        st.session_state.papers = papers
        st.session_state.papers_scored = False
        st.session_state.last_fetch = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.rerun()

with col2:
    score_disabled = st.session_state.papers is None or len(st.session_state.papers) == 0
    if st.button(
        "🧠 Run AI Scoring",
        type="secondary",
        use_container_width=True,
        disabled=score_disabled,
        help="Score papers for relevance, evidence, and actionability" if not score_disabled else "Fetch papers first"
    ):
        scored_papers = score_papers(
            st.session_state.papers,
            config["whitelist"],
            config["blacklist"]
        )
        st.session_state.papers = scored_papers
        st.session_state.papers_scored = True
        st.session_state.last_score = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.rerun()


# Show stage status
if st.session_state.papers_scored:
    st.markdown(
        '<div class="stage-indicator stage-score">✅ <strong>Stage 2:</strong> Papers fetched and AI-scored</div>',
        unsafe_allow_html=True
    )
    if st.session_state.last_score:
        st.caption(f"Last scored: {st.session_state.last_score}")
elif st.session_state.papers is not None:
    st.markdown(
        '<div class="stage-indicator stage-fetch">📥 <strong>Stage 1:</strong> Papers fetched (click "Run AI Scoring" for relevance scores)</div>',
        unsafe_allow_html=True
    )
    if st.session_state.last_fetch:
        st.caption(f"Last fetched: {st.session_state.last_fetch}")


# --- DISPLAY PAPERS --- #
papers = st.session_state.papers

if papers:
    # Apply filters (only if scored)
    if st.session_state.papers_scored:
        filtered_papers = [
            p for p in papers
            if p.get("triage_score", 0) >= min_relevance
            and p.get("evidence_score", 0) >= min_evidence
            and p.get("actionability_score", 0) >= min_actionability
        ]
    else:
        filtered_papers = papers
    
    # Apply sorting
    sort_key_map = {
        "Relevance Score": lambda p: (p.get("triage_score", 0), p.get("altmetric", {}).get("score", 0)),
        "Evidence Score": lambda p: (p.get("evidence_score", 0), p.get("triage_score", 0)),
        "Actionability Score": lambda p: (p.get("actionability_score", 0), p.get("triage_score", 0)),
        "Altmetric Score": lambda p: p.get("altmetric", {}).get("score", 0),
        "Date": lambda p: p.get("date", "0000-00-00")
    }
    
    filtered_papers = sorted(
        filtered_papers,
        key=sort_key_map.get(sort_by, sort_key_map["Altmetric Score"]),
        reverse=True
    )
    
    # Display stats
    if st.session_state.papers_scored:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Papers", len(papers))
        with col2:
            st.metric("After Filters", len(filtered_papers))
        with col3:
            avg_relevance = sum(p.get("triage_score", 0) for p in filtered_papers) / max(len(filtered_papers), 1)
            st.metric("Avg Relevance", f"{avg_relevance:.1f}")
        with col4:
            high_actionability = sum(1 for p in filtered_papers if p.get("actionability_score", 0) >= 7)
            st.metric("High Actionability", high_actionability)
        with col5:
            whitelisted = sum(1 for p in filtered_papers if p.get("whitelisted"))
            st.metric("⭐ Priority Authors", whitelisted)
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Papers", len(papers))
        with col2:
            high_impact = sum(1 for p in papers if p.get("altmetric", {}).get("score", 0) > 10)
            st.metric("High Altmetric (>10)", high_impact)
        with col3:
            with_abstract = sum(1 for p in papers if p.get("abstract", "").strip() and p.get("abstract") != "No abstract available.")
            st.metric("With Abstract", with_abstract)
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["📊 Top Papers", "📋 All Results"])
    
    with tab1:
        st.subheader("Top 10 Papers")
        if st.session_state.papers_scored:
            st.caption("Sorted by AI scores. Click 'Summarize' for AI-generated summaries.")
        else:
            st.caption("⚠️ Papers not yet scored. Showing by Altmetric attention.")
        
        top_papers = filtered_papers[:10]
        
        for i, paper in enumerate(top_papers):
            with st.expander(
                f"{i+1}. {paper['title'][:100]}{'...' if len(paper['title']) > 100 else ''}" + (" ⭐" if paper.get("whitelisted") else ""),
                expanded=(i < 3)
            ):
                # Metrics row - different based on scoring stage
                if st.session_state.papers_scored:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Relevance", f"{paper.get('triage_score', 'N/A')}/10")
                    with col2:
                        st.metric("Evidence", f"{paper.get('evidence_score', 'N/A')}/10")
                    with col3:
                        st.metric("Actionability", f"{paper.get('actionability_score', 'N/A')}/10")
                    with col4:
                        altmetric = paper.get("altmetric", {})
                        st.metric("Altmetric", altmetric.get("score", 0))
                    with col5:
                        st.metric("Date", paper.get("date", "Unknown"))
                else:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        altmetric = paper.get("altmetric", {})
                        st.metric("Altmetric", altmetric.get("score", 0))
                    with col2:
                        st.metric("Date", paper.get("date", "Unknown"))
                    with col3:
                        st.metric("Journal", paper.get("journal", "Unknown")[:20])
                
                # Paper details
                authors_display = paper.get('authors', 'Unknown')
                if paper.get("whitelisted"):
                    st.markdown(f"**Authors:** {authors_display} ⭐")
                else:
                    st.markdown(f"**Authors:** {authors_display}")
                st.markdown(f"**Journal:** {paper.get('journal', 'Unknown')}")
                
                # Social metrics
                altmetric = paper.get("altmetric", {})
                st.caption(f"🐦 Twitter: {altmetric.get('twitter', 0)} | 📰 News: {altmetric.get('news', 0)}")
                
                # Abstract
                with st.container():
                    st.markdown("**Abstract:**")
                    abstract_text = paper.get("abstract", "No abstract available.")
                    st.markdown(abstract_text[:1000] + ("..." if len(abstract_text) > 1000 else ""))
                
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
        st.subheader(f"All Results ({len(filtered_papers)} papers)")
        
        # Create a table view
        for i, paper in enumerate(filtered_papers):
            if st.session_state.papers_scored:
                col1, col2, col3, col4, col5, col6 = st.columns([4, 1, 1, 1, 1, 1])
            else:
                col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
            
            with col1:
                title_suffix = " ⭐" if paper.get("whitelisted") else ""
                st.markdown(f"**{paper['title'][:80]}{'...' if len(paper['title']) > 80 else ''}**{title_suffix}")
                st.caption(f"{paper.get('authors', 'Unknown')[:50]}")
            
            if st.session_state.papers_scored:
                with col2:
                    st.metric("Rel", paper.get("triage_score", "?"), label_visibility="collapsed")
                with col3:
                    st.metric("Evid", paper.get("evidence_score", "?"), label_visibility="collapsed")
                with col4:
                    st.metric("Act", paper.get("actionability_score", "?"), label_visibility="collapsed")
                with col5:
                    st.metric("Alt", paper.get("altmetric", {}).get("score", 0), label_visibility="collapsed")
                with col6:
                    st.link_button("Open", paper.get("url", "#"), use_container_width=True)
            else:
                with col2:
                    st.metric("Alt", paper.get("altmetric", {}).get("score", 0), label_visibility="collapsed")
                with col3:
                    st.caption(paper.get("date", "Unknown"))
                with col4:
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
  .paper.whitelisted {{ border-left-color: #FFD700; }}
  .metrics {{ color: #666; font-size: 0.9em; }}
  .badge {{ background-color: #FFD700; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; }}
  a {{ color: #1a73e8; }}
</style></head><body>
<h1>📚 Literature Digest - {date.today()}</h1>
<p>Generated with AI triage scoring</p>
"""
            for p in papers_to_export:
                summary = st.session_state.summaries.get(p.get("pmid") or p.get("title"), "")
                summary_html = f"<p><strong>Summary:</strong> {summary}</p>" if summary else ""
                whitelisted_class = " whitelisted" if p.get("whitelisted") else ""
                whitelisted_badge = ' <span class="badge">⭐ Priority Author</span>' if p.get("whitelisted") else ""
                
                if st.session_state.papers_scored:
                    metrics = f"Relevance: {p.get('triage_score', '?')}/10 | Evidence: {p.get('evidence_score', '?')}/10 | Actionability: {p.get('actionability_score', '?')}/10 | Altmetric: {p.get('altmetric', {}).get('score', 0)}"
                else:
                    metrics = f"Altmetric: {p.get('altmetric', {}).get('score', 0)}"
                
                html += f"""
<div class="paper{whitelisted_class}">
  <h3><a href="{p.get('url', '#')}">{p['title']}</a>{whitelisted_badge}</h3>
  <p class="metrics">{metrics}</p>
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
        
        if st.session_state.papers_scored:
            df_data = [{
                "Title": p["title"],
                "Authors": p.get("authors", ""),
                "Journal": p.get("journal", ""),
                "Date": p.get("date", ""),
                "Relevance": p.get("triage_score", ""),
                "Evidence": p.get("evidence_score", ""),
                "Actionability": p.get("actionability_score", ""),
                "Altmetric": p.get("altmetric", {}).get("score", 0),
                "Priority Author": "Yes" if p.get("whitelisted") else "No",
                "URL": p.get("url", ""),
                "DOI": p.get("doi", "")
            } for p in filtered_papers]
        else:
            df_data = [{
                "Title": p["title"],
                "Authors": p.get("authors", ""),
                "Journal": p.get("journal", ""),
                "Date": p.get("date", ""),
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
    st.info("👆 Select topics and click **Fetch Papers** to get started.")
    
    # Show config summary
    with st.expander("📋 Current Configuration", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Whitelist Authors (Priority):**")
            if config["whitelist"]:
                for author in config["whitelist"][:10]:
                    st.write(f"⭐ {author}")
                if len(config["whitelist"]) > 10:
                    st.caption(f"...and {len(config['whitelist']) - 10} more")
            else:
                st.caption("No whitelist configured")
        
        with col2:
            st.markdown("**Blacklist Authors (Excluded):**")
            if config["blacklist"]:
                for author in config["blacklist"][:10]:
                    st.write(f"🚫 {author}")
            else:
                st.caption("No blacklist configured")


# --- FOOTER --- #
st.divider()
st.caption(
    "Built with Streamlit • Data from PubMed & Altmetric • AI scoring by Gemini 2.0 Flash • "
    "Config via Google Sheets"
)
