from google import genai
from google.auth import default
from typing import List, Dict, Any, Optional
from models.schemas import (
    AgentRole, AgentTurn, Argument, Citation,
    DebateRound, Synthesis, ConsensusItem, UnresolvedItem,
    NewGap, ArgumentCollision, IronCladFact, ImplementationGap
)
from services.pubmed_service import PubMedService
from core.config import Config
import json
import re
from tenacity import retry, stop_after_attempt, wait_exponential


class BaseAgent:
    def __init__(self):
        credentials, project = Config.get_gcp_credentials()
        self.client = genai.Client(
            vertexai=True,
            project=project or Config.GOOGLE_CLOUD_PROJECT,
            location=Config.GOOGLE_CLOUD_LOCATION,
            credentials=credentials
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def call_gemini(self, prompt: str, is_json: bool = True) -> str:
        config = {'max_output_tokens': 8192}
        if is_json:
            config['response_mime_type'] = 'application/json'
            
        response = self.client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=config
        )
        return response.text

    def _safe_json_parse(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Attempt to extract JSON from the text
            # Use non-greedy match to find the first JSON-like block
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            if json_match:
                try:
                    # Basic cleaning: remove common LLM artifacts
                    cleaned = json_match.group(1)
                    # Handle common truncation or trailing comma issues
                    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
                    return json.loads(cleaned)
                except Exception:
                    pass
            return {}


class SearchAgent(BaseAgent):
    async def generate_query(self, vision: str) -> str:
        prompt = f"Optimize this research vision for PubMed Boolean search: {vision}. Return ONLY the query string."
        return await self.call_gemini(prompt, is_json=False)

    async def rank_relevance(self, vision: str, metadata: List[Dict]) -> List[str]:
        """Semantic Relevance Ranking: Pick top 50-70 most relevant PMIDs"""
        if not metadata: return []
        
        metadata_str = "\n".join([f"PMID: {m['pmid']} | Title: {m['title']}" for m in metadata])
        prompt = f"""VISION: {vision}
LITERATURE:
{metadata_str}

TASK: Score every PMID for relevance to the VISION (0-10). 
Return JSON: {{"scores": [{{"pmid": "...", "score": 8.5}}]}}
"""
        try:
            res_text = await self.call_gemini(prompt, is_json=True)
            data = json.loads(res_text)
            scores = data.get("scores", [])
            # Sort by score descending and return PMIDs
            ranked = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)
            return [str(r["pmid"]) for r in ranked if r.get("score", 0) > 4][:70] 
        except Exception:
            # Fallback: return first 50
            return [m['pmid'] for m in metadata[:50]]


class DebateAgent(BaseAgent):
    def __init__(self, role: AgentRole):
        super().__init__()
        self.role = role
        self.pubmed = PubMedService()
        self.persona = "PRO-AGENT (Aggressive, cites Level 1/2)" if role == AgentRole.PRO else "CON-AGENT (Skeptical, cites implementation gaps)"

    async def execute_round(self, round_num, vision, pooled_citations, opponent_args, human_input, joker_queries=None) -> AgentTurn:
        thinking_log = [f"📡 Round {round_num} Active"]
        
        # Build prompt with semantic-ranked citations
        cit_text = "\n\n".join([f"PMID: {c.pmid} | Level {c.quality.level_of_evidence}\nTitle: {c.title}\nAbstract: {c.abstract[:500]}..." for c in pooled_citations[:70]])
        
        prompt = f"""{self.persona}
VISION: {vision}
ROUND: {round_num}
{opponent_args}

EVIDENCE POOL:
{cit_text}

TASK: Return a JSON object with this structure. 
IMPORTANT: 
- Do NOT repeat arguments from previous rounds.
- Use simple, crisp language.
- If technical terms are necessary, define them in 'glossary'.
- RIGOR ATTACK: Look at the OPPONENT'S CITED PMIDs. Find those papers in the EVIDENCE POOL and attack their methodology, sample size, or interpretation. This is your primary weapon.
- Citing the SAME paper as your opponent but giving a different interpretation is encouraged (creates a Direct Collision).

{{
  "opening_statement": "Your summary of this round's position. Be concise and sharp.",
  "arguments": [
    {{
      "claim": "The scientific claim being made",
      "evidence_pmids": ["PMID1", "PMID2"],
      "strength": 8.5,
      "critique": "Your own critical assessment of this evidence",
      "rigor_attack": "Direct methodological attack on opponent's specific citations"
    }}
  ],
  "joker_queries": ["query1"],
  "glossary": {{
    "Technical Term": "Simple definition"
  }}
}}"""
        
        res_text = await self.call_gemini(prompt, is_json=True)
        data = self._safe_json_parse(res_text)
        if not data:
             data = {"opening_statement": "Self-healing fallback active due to parsing error."}

        return self._parse_response(data, round_num, thinking_log)

    def _parse_response(self, data, round_num, thinking_log) -> AgentTurn:
        args = [Argument(**a) for a in data.get("arguments", [])]
        pmids = []
        for a in args: pmids.extend(a.evidence_pmids)
        return AgentTurn(
            round_num=round_num, role=self.role, opening_statement=data.get("opening_statement", ""),
            arguments=args, citations_used=list(set(pmids)), fresh_queries=data.get("joker_queries", []), 
            thinking_log=thinking_log, glossary=data.get("glossary", {})
        )


class SynthesisAgent(BaseAgent):
    async def generate_synthesis(self, vision: str, rounds: List[DebateRound], shared_pmids: List[str] = None) -> Synthesis:
        history_parts = []
        for r in rounds:
            pro_cits = ", ".join(r.pro_turn.citations_used)
            con_cits = ", ".join(r.con_turn.citations_used)
            history_parts.append(f"ROUND {r.round_num}:")
            history_parts.append(f"PRO-AGENT: {r.pro_turn.opening_statement}\nCITED PMIDs: {pro_cits}")
            history_parts.append(f"CON-AGENT: {r.con_turn.opening_statement}\nCITED PMIDs: {con_cits}")
        
        history = "\n".join(history_parts)
        collision_context = f"DIRECT COLLISIONS (Shared PMIDs): {', '.join(shared_pmids)}" if shared_pmids else ""
        
        prompt = f"""JUDGE VISION: {vision}
HISTORY:
{history}

{collision_context}

TASK: Perform a final synthesis for a clinical researcher and layperson. Return a JSON object with this structure:
IMPORTANT: 
- Use simple, crisp language. Avoid abbreviations.
- Provide a 'glossary' for any remaining complex terms.

{{
  "consensus_items": [
    {{"statement": "High-level summary of agreed facts in simple terms", "confidence": 0.0-10.0, "supporting_agents": ["pro", "con"]}}
  ],
  "unresolved_items": [
    {{"issue": "Key point of contention", "pro_position": "...", "con_position": "...", "evidence_gap": "What is missing to resolve this?"}}
  ],
  "new_gaps": [
    {{"gap_description": "...", "identified_by": "pro/con", "suggested_search": "..."}}
  ],
  "collisions": [
    {{"pmid": "Identify from shared PMIDs if possible", "pro_interpretation": "How PRO used it", "con_interpretation": "How CON used it", "collision_point": "Why do they disagree?", "contradiction_severity": 0.0-10.0}}
  ],
  "iron_clad_facts": [
    {{"fact": "Claims that survived 3 rounds of attack", "supporting_evidence": ["List of PMIDs from the HISTORY that verify this fact"], "attack_count": 0, "survival_score": 0.0-10.0}}
  ],
  "implementation_gaps": [
    {{"barrier": "Practical hurdle", "severity": 0.0-10.0, "mitigation_suggested": "Strategic action"}}
  ],
  "echo_chamber_warning": "Warning if agents were too agreeable",
  "glossary": {{
    "Technical Term": "Simple definition"
  }}
}}"""
        
        res_text = await self.call_gemini(prompt, is_json=True)
        data = self._safe_json_parse(res_text)

        def safe_list(key, model):
            items = []
            for item in data.get(key, []):
                try:
                    items.append(model(**item))
                except Exception:
                    continue
            return items

        return Synthesis(
            consensus_items=safe_list("consensus_items", ConsensusItem),
            unresolved_items=safe_list("unresolved_items", UnresolvedItem),
            new_gaps=safe_list("new_gaps", NewGap),
            collisions=safe_list("collisions", ArgumentCollision),
            iron_clad_facts=safe_list("iron_clad_facts", IronCladFact),
            implementation_gaps=safe_list("implementation_gaps", ImplementationGap),
            echo_chamber_warning=data.get("echo_chamber_warning"),
            glossary=data.get("glossary", {})
        )
