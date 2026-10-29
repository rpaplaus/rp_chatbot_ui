import os
import re
import logging
from typing import List, Dict, Any, Optional

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

logger = logging.getLogger(__name__)

class WebSearchManager:
    """Manages web searching across multiple search engines with fallback strategies."""
    
    def __init__(self):
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.tavily_client = TavilyClient(api_key=self.tavily_key) if self.tavily_key and TavilyClient else None

    def should_search(self, message: str, mode: str = "auto") -> bool:
        """
        Determines if a search should be executed based on the user's mode and query.
        Modes: 'always', 'auto', 'disabled'
        """
        if mode == "always":
            return True
        if mode == "disabled":
            return False
            
        # Automatic detection heuristic
        msg_lower = message.lower().strip()
        
        # Explicit search commands
        if any(msg_lower.startswith(prefix) for prefix in ["pesquise", "busque", "procure", "search", "google", "ache na web", "busca"]):
            return True
            
        # Time-sensitive keywords (Portuguese & English)
        time_keywords = [
            "hoje", "ontem", "agora", "atualmente", "últimas", "ultimas", "notícias", "noticias",
            "lançamento", "lancamento", "cotação", "cotacao", "preço", "preco", "previsão", "previsao",
            "resultado", "eleição", "eleicao", "novo", "nova", "recentemente", "atual", "versão atual",
            "today", "yesterday", "now", "current", "currently", "latest", "recent", "news",
            "release", "price", "stock", "weather", "score", "who is the current", "what is the current"
        ]
        if any(kw in msg_lower for kw in time_keywords):
            return True
            
        # Year references (e.g. 2024, 2025, 2026, 2027)
        if re.search(r'\b(202[4-9]|203[0-9])\b', msg_lower):
            return True
            
        # Question words asking for real-time state or factual events
        question_triggers = [
            "quem ganhou", "quem é o presidente", "quem e o presidente",
            "qual o valor", "qual a cotacao", "qual a cotação", "o que aconteceu"
        ]
        if any(qt in msg_lower for qt in question_triggers):
            return True

        return False

    def extract_search_query(self, message: str) -> str:
        """Cleans and extracts the core search query from a user message."""
        clean = message.strip()
        # Remove conversational prefixes if present
        prefixes = [
            r'^(por favor\s*,?\s*)?(pesquise|busque|procure|veja na internet|procure na web|pesquisa)\s+(sobre\s+)?',
            r'^(please\s+)?(search|look up|google|find)\s+(for\s+|about\s+)?',
            r'^(você pode pesquisar|voce pode pesquisar|poderia buscar)\s+(sobre\s+)?'
        ]
        for p in prefixes:
            clean = re.sub(p, '', clean, flags=re.IGNORECASE).strip()
            
        # Limit query length for search engine efficiency
        return clean[:200]

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Executes web search returning a list of dicts with keys: title, url, snippet.
        """
        results = []
        clean_query = self.extract_search_query(query)
        
        # 1. Try Tavily if configured
        if self.tavily_client:
            try:
                response = self.tavily_client.search(query=clean_query, max_results=max_results, search_depth="basic")
                for r in response.get("results", []):
                    results.append({
                        "title": r.get("title", "Sem título"),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", "")
                    })
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Tavily search error: {e}, falling back to DDGS.")

        # 2. Try DuckDuckGo Search (DDGS)
        if DDGS is not None:
            try:
                ddgs_instance = DDGS()
                raw_results = ddgs_instance.text(clean_query, max_results=max_results)
                if raw_results:
                    for r in raw_results:
                        url = r.get("href") or r.get("url") or ""
                        title = r.get("title") or "Página da Web"
                        body = r.get("body") or r.get("snippet") or ""
                        if url:
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": body
                            })
                    if results:
                        return results
            except Exception as e:
                logger.warning(f"DDGS text search error: {e}")

        # 3. Fallback: DDGS news search if text search returned nothing
        if DDGS is not None and not results:
            try:
                ddgs_instance = DDGS()
                raw_news = ddgs_instance.news(clean_query, max_results=max_results)
                if raw_news:
                    for r in raw_news:
                        results.append({
                            "title": r.get("title") or "Notícia",
                            "url": r.get("url") or "",
                            "snippet": r.get("body") or ""
                        })
            except Exception as e:
                logger.warning(f"DDGS news search error: {e}")

        return results

    @staticmethod
    def format_search_context(results: List[Dict[str, str]]) -> str:
        """Formats the search results into a clean string to be provided to the LLM."""
        if not results:
            return ""
            
        formatted = "--- INÍCIO DOS RESULTADOS DA BUSCA NA WEB (DADOS ATUALIZADOS) ---\n"
        for idx, item in enumerate(results, start=1):
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            snippet = item.get("snippet", "").strip()
            formatted += f"[{idx}] Título: {title}\nFonte/URL: {url}\nResumo: {snippet}\n\n"
        formatted += (
            "--- FIM DOS RESULTADOS DA BUSCA NA WEB ---\n"
            "Instrução: Utilize as informações acima para responder com dados precisos e atualizados. "
            "Sempre que citar uma informação, indique a fonte utilizando referências numéricas como [1], [2], etc."
        )
        return formatted

    @staticmethod
    def format_sources_markdown(results: List[Dict[str, str]], query: str = "") -> str:
        """Formats the consulted sources into a beautiful markdown section for the user UI."""
        if not results:
            return ""
            
        query_display = f' por *"{query}"*' if query else ""
        header = f"🌐 **Busca na Web realizada{query_display}** ({len(results)} fontes consultadas):\n\n"
        sources_list = []
        for idx, item in enumerate(results, start=1):
            title = item.get("title", "Fonte").replace("[", "(").replace("]", ")")
            url = item.get("url", "#")
            sources_list.append(f"- **[{idx}]** [{title}]({url})")
            
        return f"{header}" + "\n".join(sources_list) + "\n\n---\n\n"
