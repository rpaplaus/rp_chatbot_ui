# 📄 Relatório de Execução — Especialização de LLMs, Scraping Profundo e Poda de Contexto

**Projeto:** `RP_ChatBot`  
**Data:** 28 de Outubro de 2026  
**Status:** ✅ Concluído, Compilado no Docker e Validado com Testes Reais (Grok-4 & Qwen3-Coder)

---

## 1. Resumo Executivo

A orquestração do `RP_ChatBot` foi evoluída para um **Design Específico por Provedor**, solucionando três desafios críticos de produção:
1. **Roteamento Assimétrico de Ferramentas (Tool Disabling):** Os modelos generalistas (**GPT-5**, **Claude 4.6**, **Gemini-3** e **Grok-4**) mantêm o *Agentic Tool Calling* (`search_web`) ativo, enquanto o modelo especialista em engenharia de software (**Qwen3-Coder**) tem a injeção de ferramentas bloqueada programaticamente (`supports_web_search = False` -> `tools_mode = "disabled"`), economizando tokens de sistema e eliminando alucinações de chamadas externas.
2. **Scraping Profundo Assíncrono (Full Page & Table Extraction):** O [`WebSearchService`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/web_search.py) agora acessa concorrentemente (`httpx.AsyncClient` + `asyncio.gather`) o HTML real dos **2 principais resultados** da busca e converte elementos `<table>` diretamente em **tabelas Markdown estruturadas** (`[TABELA EXTRAÍDA] | Col 1 | Col 2 |`) via `BeautifulSoup` (`lxml`), eliminando a "fome de dados" causada por snippets truncados.
3. **Poda e Higienização de Contexto (`_prune_and_sanitize_messages`):** O [`ChatOrchestrator`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/chat_orchestrator.py) descarta automaticamente mensagens anteriores com marcadores de erro/interrupção e detecta mudanças abruptas de assunto (*Topic Shift Pruning* com interseção vocabular zero e ausência de conectivos de continuidade), isolando a nova pergunta para impedir o vazamento de contexto (*Context Leakage*).

---

## 2. Arquivos Atualizados e Criados

- [`backend/requirements.txt`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/requirements.txt): Adicionados `beautifulsoup4>=4.12.0` e `lxml>=5.0.0`.
- [`backend/app/services/llm/base.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/llm/base.py): Adicionadas as flags declarativas `supports_web_search: bool = True` e `specialization: str = "generalist"`.
- [`backend/app/services/llm/qwen_provider.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/llm/qwen_provider.py): Configurado com `supports_web_search = False`, `specialization = "code_specialist"` e bloqueio programático `tools_mode="disabled"`.
- [`backend/app/services/llm/tools.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/llm/tools.py): Refinado `parse_tool_query` com `json.JSONDecoder().raw_decode` para extrair limpidamente o primeiro objeto JSON mesmo quando a LLM emite múltiplas `tool_calls` paralelas.
- [`backend/app/services/web_search.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/web_search.py): Implementado o pipeline assíncrono `_enrich_top_results` (`TOP_SCRAPE_COUNT = 2`, `MAX_PAGE_CHARS = 4000`) e o conversor `extract_structured_html_content` (remoção de tags de ruído + conversão de `<table>` HTML para tabela Markdown).
- [`backend/app/services/chat_orchestrator.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/app/services/chat_orchestrator.py): Implementados `_prune_and_sanitize_messages`, `_extract_semantic_keywords`, `_has_continuity_intent` e a seleção automática entre `BASE_GENERALIST_PROFILE` e `BASE_CODE_SPECIALIST_PROFILE`.
- [`backend/test_specialization_and_pruning.py`](file:///c:/Users/rpapl/.gemini/antigravity-ide/scratch/rp_chatbot_ui/backend/test_specialization_and_pruning.py): Suíte automatizada de homologação dos 3 pilares.

---

## 3. Resultados dos Testes Executados (`test_specialization_and_pruning.py`)

Executado dentro do container `rp_backend` (`docker exec rp_backend python test_specialization_and_pruning.py`):

### 3.1. Verificação Estrutural (Unitária)
```text
[0] Verificando Matriz de Capacidades, Conversor HTML->Tabela Markdown e Context Pruning:
  ✓ Roteamento Assimétrico: Qwen3-Coder (supports_web_search=False) | Generalistas (True)
  ✓ Deep Scraping Parser: Tabela HTML convertida com precisão para Markdown
  ✓ Context Pruning: Histórico de 5 msgs podado para 1 msg após mudança abrupta de assunto!
```

### 3.2. Teste 1 — Grok-4 + Deep Scraping em Tabelas (Pódio de Corrida F1)
Graças ao **Deep Scraping** nas 2 principais URLs (`planetf1.com` e `pitdebrief.com` com `deep_scraped=True`), o `Grok-4` recebeu a tabela completa da corrida e extraiu a ordem exata do pódio sem confundir linhas adjacentes:
```text
🏎️ [TESTE 1] Grok-4 + Deep Scraping em Tabelas (Pódio de Corrida F1)
Prompt: "Consulte os resultados da temporada 2026 da Fórmula 1 e monte uma tabela Markdown com o pódio (1º, 2º e 3º colocados) do GP dos Estados Unidos (Austin) ou da corrida mais recente detalhada nas fontes."
  🌐 [Sources Returned]: 5 links (2 com Deep Scraping completo de página/tabelas)
     - [1] deep_scraped=True | United States Grand Prix 2026 – F1 race results (https://www.planetf1.com/news/f1-results-united-states-grand-prix-2026-race)
     - [2] deep_scraped=True | 2026 F1 United States GP | Race results - Pit Debrief (https://www.pitdebrief.com/post/2026-f1-united-states-gp-race-results/)

  💬 [Grok-4 Resposta]:
**Pódio do GP dos Estados Unidos 2026 (Austin – Circuit of the Americas)**

| Posição | Piloto              | Equipe     |
|---------|---------------------|------------|
| 1º      | Kimi Antonelli     | Mercedes   |
| 2º      | Charles Leclerc    | Ferrari    |
| 3º      | Max Verstappen     | Red Bull   |

**Fonte principal:** Resultados oficiais da corrida (PlanetF1 e Pit Debrief, 3 dias atrás).
Kimi Antonelli venceu a prova, com Leclerc em segundo e Verstappen completando o pódio.
```

### 3.3. Teste 2 — Mudança Abrupta de Assunto (Context Pruning) + Qwen3-Coder (Tool Disabling)
Na **mesma sessão** imediatamente após o diálogo sobre Fórmula 1, foi enviada uma solicitação de código Python/FastAPI para o `Qwen3-Coder` forçando `web_search_mode="always"` no payload:
```text
🔀 [TESTE 2] Mudança Abrupta de Assunto (Context Pruning) + Qwen3-Coder (Tool Disabling)
Prompt (na mesma sessão após F1, com web_search_mode='always' no Qwen3-Coder):
"Escreva uma função Python curta usando FastAPI e Pydantic que valide um payload de healthcheck. Responda apenas com o bloco de código e uma frase."

  💬 [Qwen3-Coder Resposta]:
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class HealthCheckPayload(BaseModel):
    service: str = Field(..., min_length=1)
    status: str = Field(..., pattern="^(healthy|unhealthy)$")

@app.post("/health")
async def healthcheck(payload: HealthCheckPayload) -> dict:
    return {"service": payload.service, "status": payload.status}

Esta implementação garante validação automática e tipagem segura do payload utilizando os recursos nativos do Pydantic v2.

  ✓ Qwen3-Coder bloqueou tool calling mesmo com web_search_mode='always'!
  ✓ Poda de Contexto impediu qualquer vazamento do assunto anterior (Fórmula 1)!
```

