# Quick Start: EvidenceArena

## Launch Commands
```powershell
# 1. Navigate to the folder
cd evidence-arena

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

## Requirements
- Google Cloud ADC configured (for Gemini access) - already done
- PubMed API key in .env - already configured

## How It Works
1. Enter a research vision
2. System searches PubMed and builds an evidence pool
3. PRO and CON agents debate for up to 3 rounds
4. Between rounds, you can provide feedback to both agents
5. After 3 rounds, a Meta-Agent generates synthesis