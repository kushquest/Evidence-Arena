import aiohttp
import asyncio
from typing import List, Optional, Tuple, Dict
from models.schemas import Citation, EvidenceQuality
from core.config import Config
import xml.etree.ElementTree as ET
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class PubMedService:
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.api_key = Config.PUBMED_API_KEY

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def search(self, query: str, max_results: int = 150) -> List[str]:
        """Search PubMed and return PMIDs with retry logic"""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/esearch.fcgi", params=params, timeout=15) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("esearchresult", {}).get("idlist", [])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def fetch_basic_metadata(self, pmids: List[str]) -> List[Dict]:
        """Fetch just titles and years for semantic ranking (efficient)"""
        if not pmids: return []
        
        chunk_size = 50
        results = []
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(pmids), chunk_size):
                chunk = pmids[i:i + chunk_size]
                params = {
                    "db": "pubmed",
                    "id": ",".join(chunk),
                    "retmode": "xml"
                }
                if self.api_key: params["api_key"] = self.api_key

                try:
                    async with session.get(f"{self.base_url}/efetch.fcgi", params=params, timeout=20) as resp:
                        if resp.status != 200: continue
                        xml_text = await resp.text()
                        
                    root = ET.fromstring(xml_text)
                    for article in root.findall(".//PubmedArticle"):
                        pmid_elem = article.find(".//PMID")
                        pmid = pmid_elem.text if pmid_elem is not None else ""
                        
                        title_elem = article.find(".//ArticleTitle")
                        title = title_elem.text if title_elem is not None else "No Title Found"
                        
                        if pmid:
                            results.append({"pmid": pmid, "title": title})
                except Exception as e:
                    print(f"⚠️ Error fetching basic metadata chunk: {e}")
                    continue
        return results

    async def fetch_abstracts(self, pmids: List[str]) -> List[Citation]:
        """Fetch full abstracts for the final ranked list"""
        if not pmids: return []
        
        chunk_size = 20
        all_citations = []
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(pmids), chunk_size):
                chunk = pmids[i:i + chunk_size]
                try:
                    citations = await self._fetch_chunk(session, chunk)
                    all_citations.extend(citations)
                except Exception as e:
                    print(f"⚠️ Failed to fetch abstract chunk: {e}")
        return all_citations

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_chunk(self, session: aiohttp.ClientSession, pmids: List[str]) -> List[Citation]:
        params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
        if self.api_key: params["api_key"] = self.api_key
        
        async with session.get(f"{self.base_url}/efetch.fcgi", params=params, timeout=20) as resp:
            if resp.status != 200: return []
            xml_text = await resp.text()
            
        citations = []
        try:
            root = ET.fromstring(xml_text)
            for article in root.findall(".//PubmedArticle"):
                cit = self._parse_article_xml(article)
                if cit: citations.append(cit)
        except Exception as e:
            print(f"⚠️ XML Parsing error in chunk: {e}")
        return citations

    def _parse_article_xml(self, article: ET.Element) -> Optional[Citation]:
        try:
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None
            if not pmid: return None

            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            if not title: return None # Skip studies with no title
            
            abstract_parts = []
            for abs_text in article.findall(".//AbstractText"):
                if abs_text is not None and abs_text.text:
                    abstract_parts.append(abs_text.text.strip())
            
            if not abstract_parts:
                return None # Strictly skip studies with no abstract text
            
            abstract = "\n".join(abstract_parts)
            if len(abstract) < 30: # Heuristic: discard very short/stub abstracts
                return None

            year = 2024
            # Try multiple locations for the year
            year_elem = article.find(".//PubDate/Year") or article.find(".//ArticleDate/Year")
            if year_elem is not None: 
                try:
                    year = int(year_elem.text)
                except:
                    pass

            journal_elem = article.find(".//Journal/Title")
            journal_title = journal_elem.text if journal_elem is not None else "Unknown Journal"

            pub_types = article.findall(".//PublicationType")
            study_type, level = self._determine_study_level(pub_types)

            return Citation(
                pmid=pmid, title=title, abstract=abstract,
                journal=journal_title,
                year=year, authors=[], study_type=study_type,
                quality=EvidenceQuality(
                    study_design=study_type, 
                    sample_size=0, 
                    peer_reviewed=True, 
                    quality_score=float(10-level), 
                    level_of_evidence=level
                ),
                affiliations=[], limitations=None
            )
        except Exception as e: 
            print(f"⚠️ Error parsing article {pmid if 'pmid' in locals() else 'unknown'}: {e}")
            return None

    def _determine_study_level(self, pub_types: List[ET.Element]) -> Tuple[str, int]:
        types = [pt.text.lower() for pt in pub_types if pt.text]
        if any(x in types for x in ["meta-analysis", "systematic review"]): return "Systematic Review", 1
        if any(x in types for x in ["randomized controlled trial", "rct"]): return "RCT", 2
        if any(x in types for x in ["clinical trial"]): return "Clinical Trial", 3
        return "Observational", 4

    async def initial_search(self, query: str, max_results: int = 150) -> List[str]:
        return await self.search(query, max_results)
