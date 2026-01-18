# 📚 Literature Digest

An automated research feed that scans PubMed for longevity research, triages papers by relevance and evidence quality using AI, and presents the most interesting findings in a clean, filterable interface.

## Features

- **PubMed Search**: Automatically fetches recent papers matching longevity/healthspan research topics
- **AI Triage**: GPT-4o-mini scores papers on relevance (0-10) and evidence quality (0-10)
- **Altmetric Integration**: Shows social attention scores (Twitter mentions, news coverage)
- **On-Demand Summaries**: Generate GPT-4o summaries for papers you're interested in
- **Filtering & Sorting**: Filter by minimum scores, sort by relevance/evidence/altmetric/date
- **Export**: Download as HTML digest or CSV

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/literature-digest.git
cd literature-digest
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your API keys
Create `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "sk-your-openai-api-key"
NCBI_EMAIL = "your-email@example.com"
```

### 4. Run the app
```bash
streamlit run app.py
```

## Deployment to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Add your secrets in the Streamlit Cloud dashboard (Settings → Secrets)
5. Deploy!

## Project Structure

```
literature-digest/
├── app.py                  # Main Streamlit application
├── utils/
│   ├── pubmed.py           # PubMed search & fetch functions
│   ├── altmetric.py        # Altmetric API integration
│   └── openai_helpers.py   # AI triage & summarization
├── .streamlit/
│   └── secrets.toml.example # Template for API keys
├── requirements.txt
└── README.md
```

## Configuration

The default search query targets longevity research including:
- Aging interventions (rapamycin, metformin, senolytics, NAD+, etc.)
- Biomarkers (epigenetic clocks, metabolomics, proteomics)
- Metabolic health (insulin resistance, GLP-1, cardiovascular)
- Neurodegeneration (dementia, Alzheimer's)
- Exercise science (VO2max, HIIT, resistance training)

Edit `utils/pubmed.py` → `DEFAULT_TOPIC` to customize the search query.

## Tech Stack

- **Frontend**: Streamlit
- **APIs**: PubMed (Entrez), Altmetric, OpenAI (GPT-4o-mini, GPT-4o)
- **Language**: Python 3.11+

## License

MIT
