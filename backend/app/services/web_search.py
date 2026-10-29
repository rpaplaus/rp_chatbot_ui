import re
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Asynchronous web search service with multi-engine fallback (Tavily & DuckDuckGo)
    and Deep Page Scraping (HTML & Table-to-Markdown extraction for the top 2 results).
    """

    TOP_SCRAPE_COUNT = 2
    MAX_PAGE_CHARS = 4000
    SCRAPE_TIMEOUT_SECONDS = 6.0

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    def __init__(self):
        self.tavily_key = settings.TAVILY_API_KEY
        self.tavily_client = None
        if self.tavily_key and self.tavily_key.strip():
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.tavily_key.strip())
            except Exception as e:
                logger.warning(f"Could not initialize TavilyClient: {e}")

    def extract_search_query(self, message: str) -> str:
        """Extracts and cleans the core keyword search query from a prompt."""
        clean = message.strip()
        prefixes = [
            r'^(por favor\s*,?\s*)?(pesquise|busque|procure|veja na internet|procure na web|pesquisa)\s+(sobre\s+)?',
            r'^(please\s+)?(search|look up|google|find)\s+(for\s+|about\s+)?',
            r'^(você pode pesquisar|voce pode pesquisar|poderia buscar)\s+(sobre\s+)?'
        ]
        for p in prefixes:
            clean = re.sub(p, '', clean, flags=re.IGNORECASE).strip()
        return clean[:200]

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Executes search asynchronously across Tavily and DuckDuckGo,
        then performs concurrent Deep Scraping (Full Page + Markdown Tables) on the Top 2 URLs.
        """
        clean_query = self.extract_search_query(query)
        if not clean_query:
            return []

        results = await asyncio.to_thread(self._sync_search, clean_query, max_results)
        if not results:
            return []

        # Enrich the top N results with deep page text & structured Markdown tables
        await self._enrich_top_results(results, top_n=self.TOP_SCRAPE_COUNT)
        return results

    def _sync_search(self, clean_query: str, max_results: int) -> List[Dict[str, str]]:
        """Worker thread execution of search providers."""
        results: List[Dict[str, str]] = []

        # 1. Try Tavily if configured (with raw content extraction enabled)
        if self.tavily_client:
            try:
                response = self.tavily_client.search(
                    query=clean_query,
                    max_results=max_results,
                    search_depth="advanced",
                    include_raw_content=True
                )
                for r in response.get("results", []):
                    raw_content = r.get("raw_content") or ""
                    results.append({
                        "title": r.get("title", "Sem título"),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "full_content": raw_content[:self.MAX_PAGE_CHARS] if raw_content else ""
                    })
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Tavily search error: {e}. Falling back to DuckDuckGo.")

        # 2. Try DuckDuckGo
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            ddgs_instance = DDGS()
            raw_results = ddgs_instance.text(clean_query, max_results=max_results)
            if raw_results:
                for r in raw_results:
                    url = r.get("href") or r.get("url") or ""
                    title = r.get("title") or "Página da Web"
                    snippet = r.get("body") or r.get("snippet") or ""
                    if url:
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "full_content": ""
                        })
                if results:
                    return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")

        return results

    async def _enrich_top_results(self, results: List[Dict[str, str]], top_n: int = 2) -> None:
        """
        Concurrently fetches and parses full HTML & tables from the top N search result URLs.
        """
        targets = results[:top_n]
        if not targets:
            return

        async with httpx.AsyncClient(
            timeout=self.SCRAPE_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=self.DEFAULT_HEADERS
        ) as client:
            tasks = [
                self._fetch_and_extract_single_page(client, item)
                for item in targets
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_and_extract_single_page(
        self,
        client: httpx.AsyncClient,
        item: Dict[str, str]
    ) -> None:
        """Fetches a single URL and populates item['full_content'] with structured text & tables."""
        if item.get("full_content"):
            return

        url = item.get("url", "").strip()
        if not url or not url.startswith(("http://", "https://")):
            return

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return
            content_type = resp.headers.get("content-type", "").lower()
            if "html" not in content_type and "text" not in content_type:
                return

            html_text = resp.text
            if not html_text:
                return

            extracted = await asyncio.to_thread(
                self.extract_structured_html_content,
                html_text,
                self.MAX_PAGE_CHARS
            )
            if extracted:
                item["full_content"] = extracted
                logger.info(
                    f"[Deep Scraping] Extracted {len(extracted)} chars (including tables) from {url}"
                )
        except Exception as e:
            logger.debug(f"[Deep Scraping] Skipped {url}: {e}")

    @staticmethod
    def extract_structured_html_content(html_str: str, max_chars: int = 4000) -> str:
        """
        Parses HTML using BeautifulSoup (lxml), removes boilerplate/scripts,
        converts HTML <table> elements into structured Markdown tables,
        and returns clean, dense textual content.
        """
        try:
            soup = BeautifulSoup(html_str, "lxml")
        except Exception:
            soup = BeautifulSoup(html_str, "html.parser")

        # 1. Remove noise tags
        for noisy_tag in soup([
            "script", "style", "noscript", "svg", "iframe",
            "nav", "footer", "header", "aside", "form", "button"
        ]):
            noisy_tag.decompose()

        # 2. Convert HTML tables into structured Markdown tables in-place
        for table in soup.find_all("table"):
            md_rows: List[str] = []
            rows = table.find_all("tr")
            for r_idx, tr in enumerate(rows[:35]):  # Cap at 35 rows per table
                cells = tr.find_all(["th", "td"])
                if not cells:
                    continue
                cleaned_cells = [
                    re.sub(r"\s+", " ", c.get_text(" ", strip=True)).replace("|", "/")
                    for c in cells
                ]
                if not any(cleaned_cells):
                    continue
                md_rows.append("| " + " | ".join(cleaned_cells) + " |")
                if r_idx == 0:
                    md_rows.append("| " + " | ".join(["---"] * len(cleaned_cells)) + " |")

            if md_rows:
                table_md = "\n[TABELA EXTRAÍDA]\n" + "\n".join(md_rows) + "\n[/TABELA EXTRAÍDA]\n"
                table.replace_with(table_md)

        # 3. Extract structured paragraphs, headings, lists, and converted tables
        root = soup.find("article") or soup.find("main") or soup.body or soup
        raw_text = root.get_text(separator="\n", strip=True)

        # 4. Compact redundant blank lines while preserving table rows
        lines = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Collapse multiple internal spaces (except in markdown table rows)
            if not stripped.startswith("|"):
                stripped = re.sub(r"[ \t]+", " ", stripped)
            lines.append(stripped)

        cleaned_text = "\n".join(lines)
        return cleaned_text[:max_chars]

    @staticmethod
    def format_search_context(results: List[Dict[str, str]]) -> str:
        """
        Formats search results (including Deep Scraped full page content & Markdown tables
        for the top results) into a structured tool_response for the LLM.
        """
        if not results:
            return ""

        formatted = "--- INÍCIO DOS RESULTADOS DA BUSCA NA WEB (COM SCRAPING PROFUNDO) ---\n\n"
        for idx, item in enumerate(results, start=1):
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            snippet = item.get("snippet", "").strip()
            full_content = item.get("full_content", "").strip()

            formatted += f"=== FONTE [{idx}] ===\n"
            formatted += f"Título: {title}\n"
            formatted += f"URL: {url}\n"
            formatted += f"Resumo Inicial: {snippet}\n"
            if full_content:
                formatted += (
                    f"Conteúdo Extraído da Página (Texto & Tabelas Estruturadas):\n"
                    f"{full_content}\n"
                )
            formatted += "\n"

        formatted += (
            "--- FIM DOS RESULTADOS DA BUSCA NA WEB ---\n"
            "Instrução Estrita: Analise com atenção as tabelas e datas extraídas acima. "
            "Garanta que os dados citados (ex: pódio, vencedor, valores ou versões) pertençam "
            "exatamente ao evento específico perguntado, referenciando as fontes como [1], [2], etc."
        )
        return formatted

    @staticmethod
    def format_sources_metadata(results: List[Dict[str, str]], query: str = "") -> Dict[str, Any]:
        """Formats structured sources metadata for API / SSE events."""
        return {
            "query": query,
            "total_sources": len(results),
            "sources": [
                {
                    "index": idx,
                    "title": item.get("title", "Fonte"),
                    "url": item.get("url", "#"),
                    "snippet": item.get("snippet", ""),
                    "deep_scraped": bool(item.get("full_content"))
                }
                for idx, item in enumerate(results, start=1)
            ]
        }
