import asyncio
import os
import sys
import json
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.llm.factory import LLMFactory
from app.services.web_search import WebSearchService
from app.services.chat_orchestrator import ChatOrchestrator

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


async def run_validation_suite():
    print("=" * 76)
    print("🧪 [VALIDATION SUITE] Provider Specialization, Deep Scraping & Context Pruning")
    print(f"Target API: {BASE_URL}")
    print("=" * 76)

    # -------------------------------------------------------------------------
    # PART 0: Unit Verification of the 3 Architectural Pillars
    # -------------------------------------------------------------------------
    print("\n[0] Verificando Matriz de Capacidades, Conversor HTML->Tabela Markdown e Context Pruning:")

    # 0.1 Asymmetric Provider Routing
    qwen_prov, _ = LLMFactory.resolve("Qwen3-Coder")
    grok_prov, _ = LLMFactory.resolve("grok-4-1-fast-reasoning")
    gpt_prov, _ = LLMFactory.resolve("GPT-5 (OpenAI)")
    assert qwen_prov.supports_web_search is False and qwen_prov.specialization == "code_specialist"
    assert grok_prov.supports_web_search is True and grok_prov.specialization == "generalist"
    assert gpt_prov.supports_web_search is True
    print("  ✓ Roteamento Assimétrico: Qwen3-Coder (supports_web_search=False) | Generalistas (True)")

    # 0.2 HTML Table to Markdown Converter
    sample_html = """
    <html><body>
      <nav>Menu irrelevante</nav>
      <main>
        <h1>Resultado Oficial GP dos Estados Unidos 2026</h1>
        <table>
          <tr><th>Posição</th><th>Piloto</th><th>Equipe</th></tr>
          <tr><td>1º</td><td>Charles Leclerc</td><td>Ferrari</td></tr>
          <tr><td>2º</td><td>Kimi Antonelli</td><td>Mercedes</td></tr>
          <tr><td>3º</td><td>Max Verstappen</td><td>Red Bull</td></tr>
        </table>
      </main>
    </body></html>
    """
    extracted_md = WebSearchService.extract_structured_html_content(sample_html)
    assert "[TABELA EXTRAÍDA]" in extracted_md
    assert "| 1º | Charles Leclerc | Ferrari |" in extracted_md
    print("  ✓ Deep Scraping Parser: Tabela HTML convertida com precisão para Markdown")

    # 0.3 Context Pruning on Abrupt Topic Shift & Failed Turn Sanitization
    contaminated_history = [
        {"role": "user", "content": "Quem venceu o Grande Prêmio de Fórmula 1 em Austin e qual foi o pódio?"},
        {"role": "assistant", "content": "O vencedor em Austin foi Charles Leclerc, seguido por Antonelli e Verstappen."},
        {"role": "user", "content": "Tente buscar outra corrida"},
        {"role": "assistant", "content": "⚠️ *Erro ao gerar resposta: Timeout*"},
        {"role": "user", "content": "Implemente um endpoint FastAPI assíncrono com SQLAlchemy para listar usuários."}
    ]
    pruned = ChatOrchestrator._prune_and_sanitize_messages(contaminated_history)
    assert len(pruned) == 1, f"Expected 1 message after topic shift pruning, got {len(pruned)}"
    assert "FastAPI" in pruned[0]["content"]
    print(f"  ✓ Context Pruning: Histórico de {len(contaminated_history)} msgs podado para {len(pruned)} msg após mudança abrupta de assunto!")

    # -------------------------------------------------------------------------
    # PART 1 & 2: Live End-to-End Container Tests (Grok-4 Deep Scraping + Topic Shift)
    # -------------------------------------------------------------------------
    async with httpx.AsyncClient(timeout=120.0) as client:
        r_auth = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": settings.APP_PASSWORD}
        )
        assert r_auth.status_code == 200
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_sess = await client.post(
            f"{BASE_URL}/sessions",
            headers=headers,
            json={
                "title": "Teste Deep Scraping & Pruning",
                "model_name": "grok-4-1-fast-reasoning",
                "web_search_mode": "auto"
            }
        )
        assert r_sess.status_code == 201
        session_id = r_sess.json()["id"]

        # TESTE 1: Pergunta complexa sobre tabelas/pódio da corrida no Grok-4 com Deep Scraping
        print("\n" + "-" * 76)
        print("🏎️ [TESTE 1] Grok-4 + Deep Scraping em Tabelas (Pódio de Corrida F1)")
        print("-" * 76)
        prompt_t1 = (
            "Consulte os resultados da temporada 2026 da Fórmula 1 e monte uma tabela Markdown "
            "com o pódio (1º, 2º e 3º colocados) do GP dos Estados Unidos (Austin) ou da corrida mais recente detalhada nas fontes."
        )
        print(f"Prompt: \"{prompt_t1}\"")

        t1_events = []
        t1_sources = []
        t1_chunks = []

        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "message": {"content": prompt_t1},
                "model_name": "grok-4-1-fast-reasoning",
                "web_search_mode": "auto",
                "client_timezone": "Europe/Lisbon",
                "client_local_time": "2026-10-28 21:25"
            }
        ) as stream1:
            assert stream1.status_code == 200
            cur_ev = None
            async for line in stream1.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    cur_ev = line.replace("event:", "").strip()
                    t1_events.append(cur_ev)
                elif line.startswith("data:"):
                    payload = json.loads(line.replace("data:", "").strip())
                    if cur_ev == "search_start":
                        print(f"  🔍 [Tool Call Query]: '{payload.get('query')}'")
                    elif cur_ev == "sources":
                        t1_sources = payload.get("sources", [])
                        deep_count = sum(1 for s in t1_sources if s.get("deep_scraped"))
                        print(f"  🌐 [Sources Returned]: {len(t1_sources)} links ({deep_count} com Deep Scraping completo de página/tabelas)")
                        for s in t1_sources[:2]:
                            print(f"     - [{s.get('index')}] deep_scraped={s.get('deep_scraped')} | {s.get('title')} ({s.get('url')})")
                        print("\n  💬 [Grok-4 Resposta]:\n", end="", flush=True)
                    elif cur_ev == "chunk":
                        txt = payload.get("text", "")
                        t1_chunks.append(txt)
                        print(txt, end="", flush=True)

        print("\n")
        assert "search_start" in t1_events
        assert "sources" in t1_events
        assert any(s.get("deep_scraped") for s in t1_sources), "Expected at least 1 top result to be deep scraped!"

        # TESTE 2: Mudança abrupta de assunto na MESMA sessão + Qwen3-Coder (Tool Disabling)
        print("-" * 76)
        print("🔀 [TESTE 2] Mudança Abrupta de Assunto (Context Pruning) + Qwen3-Coder (Tool Disabling)")
        print("-" * 76)
        prompt_t2 = (
            "Escreva uma função Python curta usando FastAPI e Pydantic que valide um payload de healthcheck. "
            "Responda apenas com o bloco de código e uma frase."
        )
        print(f"Prompt (na mesma sessão após F1, com web_search_mode='always' no Qwen3-Coder):\n\"{prompt_t2}\"")

        t2_events = []
        t2_chunks = []

        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "message": {"content": prompt_t2},
                "model_name": "Qwen3-Coder",
                "web_search_mode": "always",  # Deve ser bloqueado programaticamente pelo Qwen3-Coder!
                "client_timezone": "Europe/Lisbon",
                "client_local_time": "2026-10-28 21:26"
            }
        ) as stream2:
            assert stream2.status_code == 200
            cur_ev = None
            print("\n  💬 [Qwen3-Coder Resposta]:\n", end="", flush=True)
            async for line in stream2.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    cur_ev = line.replace("event:", "").strip()
                    t2_events.append(cur_ev)
                elif line.startswith("data:"):
                    payload = json.loads(line.replace("data:", "").strip())
                    if cur_ev == "chunk":
                        txt = payload.get("text", "")
                        t2_chunks.append(txt)
                        print(txt, end="", flush=True)

        t2_full_text = "".join(t2_chunks)
        print("\n")
        assert "search_start" not in t2_events, "Qwen3-Coder must have web search programmatically disabled!"
        assert "FastAPI" in t2_full_text or "fastapi" in t2_full_text
        assert "Fórmula 1" not in t2_full_text and "Leclerc" not in t2_full_text, "Zero context leakage from prior F1 turn!"
        print("  ✓ Qwen3-Coder bloqueou tool calling mesmo com web_search_mode='always'!")
        print("  ✓ Poda de Contexto impediu qualquer vazamento do assunto anterior (Fórmula 1)!")

        # Cleanup session
        await client.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers)

    print("\n" + "=" * 76)
    print("🎉 TODOS OS TESTES DE ESPECIALIZAÇÃO, DEEP SCRAPING E PRUNING APROVADOS!")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(run_validation_suite())

