from models.schemas import (
    DebateReport, DebateRound, AgentRole, AgentTurn,
    Citation, Synthesis
)
from services.pubmed_service import PubMedService
from services.debate_agent import DebateAgent, SynthesisAgent, SearchAgent
from core.config import Config
from tenacity import retry, stop_after_attempt, wait_exponential


class DebateOrchestrator:
    def __init__(self):
        self.pubmed = PubMedService()
        self.pro_agent = DebateAgent(AgentRole.PRO)
        self.con_agent = DebateAgent(AgentRole.CON)
        self.synthesis_agent = SynthesisAgent()
        self.search_agent = SearchAgent()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
    async def run_full_pipeline(self, vision: str):
        """Self-healing orchestrator pipeline"""
        # 1. AI-Optimized Query
        query = await self.search_agent.generate_query(vision)
        
        # 2. Broad Search (150 PMIDs)
        pmids = await self.pubmed.initial_search(query)
        if not pmids:
            # Healing attempt: simple search
            pmids = await self.pubmed.search(vision.split()[:5], max_results=50)
            
        # 3. Semantic Relevance Ranking
        # Fetch basic metadata for all 150 first (fast)
        basic_meta = await self.pubmed.fetch_basic_metadata(pmids)
        ranked_pmids = await self.search_agent.rank_relevance(vision, basic_meta)
        
        # 4. Deep Fetch for Top Papers (50-70 most relevant)
        citations = await self.pubmed.fetch_abstracts(ranked_pmids)
        
        return query, citations

    async def run_round(
        self,
        round_num: int,
        vision: str,
        pooled_citations: list[Citation],
        previous_pro: AgentTurn = None,
        previous_con: AgentTurn = None
    ) -> DebateRound:
        """Execute one debate round with self-healing retries"""
        
        pro_opponent_pmids = previous_con.citations_used if previous_con else []
        pro_args = f"OPPONENT'S PREVIOUS ARGUMENT: {previous_con.opening_statement if previous_con else ''}\nOPPONENT'S CITED PMIDs: {', '.join(pro_opponent_pmids)}"
        
        pro_turn = await self.pro_agent.execute_round(
            round_num=round_num, vision=vision, pooled_citations=pooled_citations,
            opponent_args=pro_args, human_input="", joker_queries=None
        )

        con_opponent_pmids = pro_turn.citations_used
        con_args = f"OPPONENT'S CURRENT ARGUMENT: {pro_turn.opening_statement}\nOPPONENT'S CITED PMIDs: {', '.join(con_opponent_pmids)}"
        
        con_turn = await self.con_agent.execute_round(
            round_num=round_num, vision=vision, pooled_citations=pooled_citations,
            opponent_args=con_args, human_input="", joker_queries=pro_turn.fresh_queries
        )

        return DebateRound(round_num=round_num, pro_turn=pro_turn, con_turn=con_turn)

    async def generate_synthesis(self, vision: str, rounds: list[DebateRound]) -> Synthesis:
        # Detect Direct Collisions: Same PMID used by both PRO and CON across all rounds
        pro_pmids = set()
        con_pmids = set()
        for r in rounds:
            pro_pmids.update(r.pro_turn.citations_used)
            con_pmids.update(r.con_turn.citations_used)
        
        shared_pmids = list(pro_pmids.intersection(con_pmids))
        
        return await self.synthesis_agent.generate_synthesis(vision, rounds, shared_pmids)

    def calculate_evidence_weights(self, rounds: list[DebateRound], citations: list[Citation]) -> tuple[float, float]:
        cit_map = {c.pmid: c for c in citations}
        def get_score(turn: AgentTurn):
            if not turn.citations_used: return 50.0
            total_weight, count = 0, 0
            for pmid in turn.citations_used:
                cit = cit_map.get(pmid)
                if cit:
                    # Non-linear weighting: Level 1=100, 2=70, 3=40, 4=15, 5=5
                    lvl = cit.quality.level_of_evidence
                    weight = 100 if lvl == 1 else 70 if lvl == 2 else 40 if lvl == 3 else 15 if lvl == 4 else 5
                    total_weight += weight
                    count += 1
            return min(total_weight / count, 100.0) if count > 0 else 50.0
        return get_score(rounds[-1].pro_turn), get_score(rounds[-1].con_turn)
