# ⚔️ EvidenceArena

**Adversarial Evidence Synthesis & High-Fidelity Scientific Audit**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://evidence-arena.streamlit.app/)

EvidenceArena is a clinical-grade research orchestration system that uses dual-agent adversarial AI to stress-test medical hypotheses against real-world evidence from PubMed. 

Unlike standard "search and summarize" tools, EvidenceArena spawns two opposing agents (**PRO** and **CON**) that engage in a 3-round "ruthless" debate, citing hyperlinked scientific evidence to destroy each other's arguments.

---

## 🚀 Key Features

### 1. **Adversarial Synthesis (The AI Fight)**
- **PRO-AGENT:** Advocates for the research vision, prioritizing Level 1 (Meta-analysis) and Level 2 (RCT) evidence.
- **CON-AGENT:** Skeptical auditor that weaponizes study limitations, small sample sizes, and implementation barriers.
- **3-Round Combat:** Agents cross-examine each other's citations, performing "Rigor Attacks" on methodological flaws.

### 2. **High-Fidelity Evidence Audit**
- **⚖️ Scientific Weighting:** Automatically extracts the **Level of Evidence (1-5)** for every paper. An agent's "Score" is weighted by the quality of their evidence, not just volume.
- **🛡️ Iron-Clad Facts:** Identifies claims that survived 3 rounds of adversarial attack with a high "Survival Score."
- **💥 Conflict Map:** Visualizes "Direct Collisions" where both agents use the same PMID but draw opposite scientific conclusions.
- **🚧 Implementation Gaps:** Audits real-world barriers like cost, infrastructure, and ethics.

### 3. **Deep Transparency & Auditability**
- **🖥️ Live Thinking Console:** Side-by-side terminal logs show the agents' internal reasoning and execution steps in real-time.
- **🔗 Clickable PMIDs:** Every citation is a live hyperlink to the original source on `pubmed.ncbi.nlm.nih.gov`.
- **🤖 AI Librarian:** Translates raw user vision into optimized Boolean PubMed queries (MeSH terms included).
- **🧠 Semantic Re-Ranking:** Pulls ~150 candidates and re-ranks them to select the top 50-70 most relevant abstracts before the debate begins.

### 4. **Self-Healing Architecture**
- **Tenacity Retries:** Automated exponential backoff for all API calls.
- **JSON Repair:** Fallback regex-based parsing to handle complex or malformed LLM outputs.

---

## 🛠️ Technical Setup

### **Requirements**
- **Operating System:** Windows/macOS/Linux
- **Credentials:** Google Cloud ADC (Application Default Credentials) configured on the local machine.
- **Project Access:** Vertex AI enabled on a Google Cloud Project (e.g., `gen-lang-client-...`).

### **Installation**
```powershell
# 1. Navigate to the folder
cd evidence-arena

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

### **Usage**
```powershell
streamlit run app.py
```
1.  In the Sidebar, click **🔄 Refresh Models** to dynamically fetch Gemini models available in your Vertex AI project.
2.  Select your model (e.g., `gemini-1.5-pro` or `gemini-2.0-flash`).
3.  Enter your **Research Vision** and click **⚔️ INITIATE ADVERSARIAL AUDIT**.
4.  Watch the **Live Console** to audit the AI's reasoning as it happens.

---

## 📁 Project Structure
- `app.py`: Streamlit UI with Live Thinking Console and Tabbed Synthesis.
- `core/orchestrator.py`: Pipeline manager (Search -> Rank -> Debate -> Synthesis).
- `services/pubmed_service.py`: PubMed API integration with semantic ranking & XML parsing.
- `services/debate_agent.py`: PRO/CON/Judge agents with rigorous prompt strategies.
- `models/schemas.py`: Pydantic models for structured scientific data.

---

## ✅ Recent Enhancements (May 2026)
- **Self-Healing Parsing:** Implemented granular, item-by-item parsing in the `SynthesisAgent` to prevent "blank output" failures.
- **Robust Role Validation:** Added case-insensitive handling for `AgentRole` to ensure compatibility with various LLM response styles.
- **Advanced Rigor Attacks:** Updated the orchestrator to pass explicit citation lists between agents, fostering direct evidence-based conflict.
- **Human-Centric UI:** Redesigned the results page with an Executive Summary, chat-based transcripts, and a Plain Language Glossary.

---

## 🗺️ Future Roadmap (Next Session)

The following architectural improvements are prioritized for the next phase of development:

### 1. **Multi-Model Heterogeneity (The "Agent Mix")**
To maximize epistemic diversity and eliminate positional bias:
- **PRO-AGENT:** Gemini 2.5 Pro (Deep synthesis).
- **CON-AGENT:** Groq + Llama 3 70B Versatile (Aggressive skepticism).

### 2. **Dynamic & Stratified Evidence Pooling**
- Transition to a **35–45 abstract "Sweet Spot"** for higher attention density.
- Implement **Stratified Sampling** to ensure Level 1 (Meta-analysis) evidence is always prioritized in the debate pool regardless of raw semantic rank.
- Add a **Dynamic Relevance Cutoff** (e.g., Score >= 6/10) to adapt to varying topic densities.

### 3. **Hallucination Prevention**
- Implement a strict **PMID-Locking** constraint for non-grounded models to ensure the CON agent only reinterprets existing evidence rather than fabricating citations.

---

*EvidenceArena: Moving beyond discovery to true scientific scrutiny.*

---

## ⚖️ Legal & Licensing

**Copyright (c) 2026 Kushagra Shiromani. All Rights Reserved.**

This project is **Proprietary Software**. No license is granted for public use, modification, or distribution. 

*   **View Only:** This code is published on GitHub for architectural demonstration and peer review purposes only.
*   **Permissions:** You may NOT run, copy, or modify this code without explicit written permission from the author.
*   **Contact:** If you are interested in using EvidenceArena for research or commercial purposes, please contact the author via GitHub.
