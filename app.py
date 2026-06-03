import streamlit as st
import asyncio
import pandas as pd
import re
import time
from core.orchestrator import DebateOrchestrator
from models.schemas import DebateReport, DebateRound, AgentRole, Citation

# --- PAGE SETUP ---
st.set_page_config(page_title="EvidenceArena", page_icon="⚔️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main-header { text-align: left; color: #1a1a2e; font-size: 2.5rem; font-weight: 800; margin-bottom: 0rem; }
    .vision-header { 
        background-color: #f0f2f6; 
        padding: 1.5rem; 
        border-radius: 10px; 
        border-left: 10px solid #1a1a2e;
        margin: 1rem 0;
        font-size: 1.2rem;
        font-weight: 500;
    }
    .live-thinking {
        font-family: 'Courier New', monospace;
        background-color: #1a1a2e;
        color: #00ff88;
        padding: 1rem;
        border-radius: 8px;
        font-size: 0.85rem;
        height: 300px;
        overflow-y: auto;
        border: 2px solid #333;
        margin-bottom: 1rem;
    }
    .thinking-label { font-weight: 700; margin-bottom: 0.5rem; color: #4a4a6a; }
    .agent-card { border-radius: 12px; padding: 1.5rem; height: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    .pro-card { background: linear-gradient(135deg, #e8f4fd 0%, #d4e9f7 100%); border-left: 5px solid #2196F3; }
    .con-card { background: linear-gradient(135deg, #fde8e8 0%, #f7d4d4 100%); border-left: 5px solid #F44336; }
    .opening-stmt { font-size: 1.1rem; line-height: 1.6; padding: 1rem; background: rgba(255,255,255,0.7); border-radius: 8px; margin: 1rem 0; }
    .rigor-attack { background: #fff3f3; border: 1px dashed #f44336; color: #b71c1c; padding: 0.75rem; border-radius: 6px; font-size: 0.95rem; margin-top: 0.5rem; font-style: italic; }
    .pmid-link { color: #1565C0; font-weight: 700; text-decoration: underline; }
    .iron-clad-card { background: #1a1a2e; color: white; border-left: 8px solid #ff9800; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)

def link_pmids(text):
    if not text: return ""
    # Match PMIDs like PMID: 1234567 or [1234567] or just 1234567 in a list
    # Robust pattern for various citation styles
    pattern = r'(PMID:?\s*)?(\d{7,9})'
    def replace(match):
        prefix = match.group(1) if match.group(1) else ""
        pmid = match.group(2)
        return f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" target="_blank" class="pmid-link">{prefix}{pmid}</a>'

    # Avoid double-linking by checking if already inside an <a> tag
    # This is a simple heuristic: if it looks like it's part of a URL or tag, skip it
    return re.sub(pattern, replace, text)


def get_level_explanation(level):
    explanations = {
        1: "🌟 **Level 1 (Gold Standard):** Meta-analysis or Systematic Review. These combine results from multiple high-quality studies for the highest certainty.",
        2: "💎 **Level 2 (High Quality):** Randomized Controlled Trials (RCTs). Gold standard for testing if a treatment or intervention actually works.",
        3: "📊 **Level 3 (Good Evidence):** Cohort or Case-Control studies. Observes large groups of people over time.",
        4: "📝 **Level 4 (Descriptive):** Case series or low-quality clinical trials. Mostly describes experiences and pilot results.",
        5: "💡 **Level 5 (Expert Opinion):** Expert reports or consensus from groups. Based on clinical experience rather than large trials."
    }
    return explanations.get(level, f"Level {level} Study")


# --- SESSION STATE ---

def type_write(container, text, delay=0.01):
    """Simulate a typewriter effect in a streamlit container"""
    typed_text = ""
    for char in text:
        typed_text += char
        container.markdown(f"<div class='live-thinking'>{typed_text}█</div>", unsafe_allow_html=True)
        time.sleep(delay)
    container.markdown(f"<div class='live-thinking'>{typed_text}</div>", unsafe_allow_html=True)


# --- SESSION STATE ---
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = DebateOrchestrator()
if "step" not in st.session_state:
    st.session_state.step = "input"
if "rounds" not in st.session_state:
    st.session_state.rounds = []
if "debate_report" not in st.session_state:
    st.session_state.debate_report = None

# --- MAIN UI ---
st.markdown("<div class='main-header'>⚔️ EvidenceArena</div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Configuration")
    from core.config import Config
    if "available_models" not in st.session_state:
        st.session_state.available_models = Config.get_available_gemini_models()
    selected_model = st.selectbox("Select Model", options=st.session_state.available_models, index=0)
    Config.GEMINI_MODEL = selected_model
    if st.button("🔄 Refresh Models"):
        st.session_state.available_models = Config.get_available_gemini_models()
        st.rerun()

# --- STEP 1: VISION INPUT ---
if st.session_state.step == "input":
    user_vision = st.text_area("What research vision shall we audit?", placeholder="e.g., Effectiveness of AI for TB screening...", height=150)
    
    if st.button("⚔️ INITIATE ADVERSARIAL AUDIT", type="primary"):
        if user_vision and Config.GEMINI_MODEL:
            st.session_state.vision = user_vision
            st.session_state.rounds = []
            
            # --- LIVE THINKING CONSOLE ---
            st.markdown("### 🖥️ Live Audit Console")
            log_col1, log_col2 = st.columns(2)
            with log_col1:
                st.markdown("<div class='thinking-label'>🔵 PRO-AGENT LOG</div>", unsafe_allow_html=True)
                pro_log = st.empty()
                pro_log.markdown("<div class='live-thinking'>Waiting for pipeline...</div>", unsafe_allow_html=True)
            with log_col2:
                st.markdown("<div class='thinking-label'>🔴 CON-AGENT LOG</div>", unsafe_allow_html=True)
                con_log = st.empty()
                con_log.markdown("<div class='live-thinking'>Waiting for pipeline...</div>", unsafe_allow_html=True)

            status = st.status("🚀 Starting EvidenceArena Pipeline...", expanded=True)

            # 1. Search & Rank
            status.update(label="🤖 AI Librarian ranking evidence...", state="running")
            try:
                query, citations = run_async(st.session_state.orchestrator.run_full_pipeline(user_vision))
                st.session_state.search_query = query
                st.session_state.pooled_citations = citations
                msg = f"> Optimized Query: {query}\n> Found {len(citations)} relevant papers.\n> Ready for adversarial audit."
                pro_log.markdown(f"<div class='live-thinking'>{msg}</div>", unsafe_allow_html=True)
                con_log.markdown(f"<div class='live-thinking'>{msg}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Pipeline Failure: {e}")
                st.stop()

            # 2. Debate Rounds
            for r in range(1, 4):
                status.update(label=f"⚔️ Round {r}/3: Cross-Examining evidence...", state="running")
                
                prev_pro = st.session_state.rounds[-1].pro_turn if st.session_state.rounds else None
                prev_con = st.session_state.rounds[-1].con_turn if st.session_state.rounds else None
                
                # Execute Round
                round_res = run_async(st.session_state.orchestrator.run_round(r, user_vision, citations, prev_pro, prev_con))
                st.session_state.rounds.append(round_res)
                
                # Update Side-by-Side Logs
                pro_msg = "\n".join([f"> {t}" for t in round_res.pro_turn.thinking_log])
                pro_msg += f"\n\n> ARGUMENT READY: {round_res.pro_turn.opening_statement[:150]}..."
                
                con_msg = "\n".join([f"> {t}" for t in round_res.con_turn.thinking_log])
                con_msg += f"\n\n> REBUTTAL READY: {round_res.con_turn.opening_statement[:150]}..."
                
                pro_log.markdown(f"<div class='live-thinking'>{pro_msg}</div>", unsafe_allow_html=True)
                con_log.markdown(f"<div class='live-thinking'>{con_msg}</div>", unsafe_allow_html=True)
                time.sleep(0.5)

            # 3. Final Synthesis
            status.update(label="⚖️ Generating final synthesis...", state="running")
            synthesis = run_async(st.session_state.orchestrator.generate_synthesis(user_vision, st.session_state.rounds))
            w_pro, w_con = st.session_state.orchestrator.calculate_evidence_weights(st.session_state.rounds, citations)
            
            last_r = st.session_state.rounds[-1]
            b_pro = sum(a.strength for a in last_r.pro_turn.arguments) / max(len(last_r.pro_turn.arguments), 1) * 10
            b_con = sum(a.strength for a in last_r.con_turn.arguments) / max(len(last_r.con_turn.arguments), 1) * 10

            st.session_state.debate_report = DebateReport(
                vision=user_vision, rounds=st.session_state.rounds, synthesis=synthesis,
                burn_meter_pro=b_pro, burn_meter_con=b_con,
                evidence_weight_pro=w_pro, evidence_weight_con=w_con
            )
            st.session_state.step = "results"
            status.update(label="✅ Audit Complete!", state="complete")
            st.rerun()

# --- STEP 3: RESULTS ---
elif st.session_state.step == "results" and st.session_state.debate_report:
    st.markdown(f"<div class='vision-header'>🎯 Research Vision: {st.session_state.vision}</div>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.divider()
        with st.expander("🔍 Search Strategy"):
            st.code(st.session_state.search_query, language="text")

    report = st.session_state.debate_report
    
    # --- EXECUTIVE SUMMARY ---
    with st.container(border=True):
        st.markdown("### 📋 Executive Summary")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            # Generate a brief summary based on consensus
            top_consensus = report.synthesis.consensus_items[0].statement if report.synthesis.consensus_items else "No clear consensus reached."
            st.markdown(f"**Primary Finding:** {top_consensus}")
            st.markdown(f"**Audit Rigor:** 3 Rounds of adversarial attack completed using {len(st.session_state.pooled_citations)} peer-reviewed sources.")
        with c2:
            st.metric("PRO Confidence", f"{int(report.burn_meter_pro)}%", f"{int(report.evidence_weight_pro)}% Evidence")
        with c3:
            st.metric("CON Skepticism", f"{int(report.burn_meter_con)}%", f"{int(report.evidence_weight_con)}% Evidence", delta_color="inverse")

    st.divider()
    tabs = st.tabs(["⚖️ Synthesis", "🛡️ Iron-Clad Facts", "💥 Conflicts", "📖 Glossary", "📜 Full Transcript", "📚 Evidence Pool"])
    
    with tabs[0]:
        s = report.synthesis
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("✅ Consensus Points")
            if not s.consensus_items:
                st.info("The adversarial audit did not yield a stable consensus on this vision. Both agents maintain distinct, non-overlapping perspectives.")
            for item in s.consensus_items:
                with st.container(border=True):
                    st.markdown(link_pmids(f"**{item.statement}**"), unsafe_allow_html=True)
                    st.caption(f"Confidence Score: {int(item.confidence*10)}/100 | Supported by: {', '.join([r.upper() for r in item.supporting_agents])}")

        with col_right:
            st.subheader("🚧 Implementation Barriers")
            if not s.implementation_gaps:
                st.success("No critical implementation barriers were identified during the debate.")
            for g in s.implementation_gaps:
                with st.expander(f"🚩 {g.barrier}"):
                    st.markdown(f"**Impact Severity:** {int(g.severity)}/10")
                    st.markdown(f"**How to address this:** {link_pmids(g.mitigation_suggested)}", unsafe_allow_html=True)

        if s.unresolved_items:
            st.subheader("❓ Unresolved Debates")
            for u in s.unresolved_items:
                with st.container(border=True):
                    st.markdown(f"**The Contention:** {u.issue}")
                    st.markdown(f"*One perspective:* {u.pro_position}")
                    st.markdown(f"*Counter perspective:* {u.con_position}")
                    st.warning(f"What we still need to know: {u.evidence_gap}")

    with tabs[1]:
        st.subheader("🛡️ Iron-Clad Facts")
        st.info("These key findings survived 3 rounds of intense adversarial debate and cross-examination.")
        for fact in report.synthesis.iron_clad_facts:
            st.markdown(f'<div class="iron-clad-card"><b>{fact.fact}</b><br>Stability Score: {fact.survival_score}/10 | Verified by: {link_pmids(", ".join(fact.supporting_evidence))}</div>', unsafe_allow_html=True)

    with tabs[2]:
        st.subheader("💥 Evidence Conflict Map")
        st.warning("Cases where both agents looked at the SAME study but drew opposite conclusions.")
        if not report.synthesis.collisions:
            st.write("No direct evidence collisions identified.")
        for c in report.synthesis.collisions:
            with st.container(border=True):
                st.markdown(f"**Study ID (PMID):** {link_pmids(c.pmid)} | **Point of Clash:** {c.collision_point}", unsafe_allow_html=True)
                cc1, cc2 = st.columns(2)
                with cc1: st.info(f"🔵 **PRO Interpretation:** {c.pro_interpretation}")
                with cc2: st.error(f"🔴 **CON Interpretation:** {c.con_interpretation}")

    with tabs[3]:
        st.subheader("📖 Plain Language Glossary")
        st.markdown("We've translated technical terms used by the agents into simple language.")
        
        # Merge all glossaries from all turns and synthesis
        full_glossary = {}
        full_glossary.update(report.synthesis.glossary)
        for r in report.rounds:
            full_glossary.update(r.pro_turn.glossary)
            full_glossary.update(r.con_turn.glossary)
        
        if not full_glossary:
            st.write("No technical terms identified for this audit.")
        else:
            for term, definition in sorted(full_glossary.items()):
                st.markdown(f"**{term}**: {definition}")
        
        st.divider()
        st.subheader("🔬 Understanding Evidence Levels")
        for i in range(1, 6):
            st.write(get_level_explanation(i))

    with tabs[4]:
        for r in report.rounds:
            st.markdown(f"### 🥊 Round {r.round_num}")
            
            with st.chat_message("human", avatar="🔵"):
                st.markdown(f"**PRO-AGENT (Vision Advocate)**")
                st.markdown(link_pmids(r.pro_turn.opening_statement), unsafe_allow_html=True)
                for a in r.pro_turn.arguments:
                    if a.rigor_attack: st.markdown(f'<div class="rigor-attack">🛡️ Critical Audit: {a.rigor_attack}</div>', unsafe_allow_html=True)
            
            with st.chat_message("assistant", avatar="🔴"):
                st.markdown(f"**CON-AGENT (Skeptical Auditor)**")
                st.markdown(link_pmids(r.con_turn.opening_statement), unsafe_allow_html=True)
                for a in r.con_turn.arguments:
                    if a.rigor_attack: st.markdown(f'<div class="rigor-attack">🛡️ Critical Audit: {a.rigor_attack}</div>', unsafe_allow_html=True)
            st.divider()

    with tabs[5]:
        st.subheader(f"📚 Full Evidence Pool ({len(st.session_state.pooled_citations)} papers)")
        st.info("The top 70 most relevant papers identified by the AI Librarian.")
        for c in st.session_state.pooled_citations:
            with st.expander(f"📄 Level {c.quality.level_of_evidence} | {c.title}"):
                st.markdown(f"**Journal:** {c.journal} ({c.year})")
                st.markdown(f"**Study Type:** {c.study_type}")
                st.markdown(f"**PMID:** {link_pmids(c.pmid)}", unsafe_allow_html=True)
                st.markdown(f"**Abstract:** {c.abstract}")
                st.markdown(f"**Evidence Rating:** {get_level_explanation(c.quality.level_of_evidence)}")
    if st.button("🔄 NEW AUDIT", use_container_width=True, type="primary"):
        st.session_state.step = "input"
        st.session_state.rounds = []
        st.session_state.debate_report = None
        st.rerun()
