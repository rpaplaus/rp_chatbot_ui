# 📋 Plano de Ação - Fase 3: Padrão Strategy de LLMs e Serviços de Domínio

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 3 - Padrão Strategy de LLMs e Serviços de Domínio  
**Status:** ⏳ Aguardando Aprovação Formal  

---

## 1. Objetivo da Fase 3
Refatorar e isolar completamente a lógica de inteligência artificial e processamento de arquivos que antes se encontrava concentrada no monólito Gradio (`llm_manager.py`, `file_parser.py`, `web_search.py`), implementando:
1. **Padrão Strategy:** Interface abstrata `BaseLLMProvider` e 5 implementações concretas (`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`, `XAIProvider`, `QwenProvider`) com clientes nativos assíncronos.
2. **Padrão Factory:** Classe `LLMFactory` responsável por resolver e injetar o provedor adequado com base no modelo solicitado, aplicando validação prévia de credenciais.
3. **Serviços de Domínio Desacoplados:** Migração e otimização não bloqueante do parser de arquivos (`FileParserService`) e do motor de busca web (`WebSearchService`).
4. **Orquestrador de Chat Assíncrono (`ChatOrchestrator`):** Gerador assíncrono unificado (`AsyncGenerator`) que coordena a injeção de contexto de arquivos, busca online e streaming de chunks das LLMs em formato padronizado.

---

## 2. Nova Estrutura da Camada de Serviços (`backend/app/services/`)

A camada de serviços será organizada da seguinte forma:

```
backend/app/services/
├── __init__.py
├── file_parser.py                   # Extração de texto/dados de anexos (PDF, TXT, código, imagens)
├── web_search.py                    # Busca na internet (Tavily + fallback DDG) sem I/O bloqueante
├── chat_orchestrator.py             # Orquestrador central: Anexos + Web Search + LLM Streaming
└── llm/
    ├── __init__.py
    ├── base.py                      # Interface abstrata BaseLLMProvider e DTOs de streaming
    ├── openai_provider.py           # Provider OpenAI (gpt-5-2025-08-07 via AsyncOpenAI)
    ├── anthropic_provider.py        # Provider Anthropic (claude-sonnet-4-6 via AsyncAnthropic)
    ├── gemini_provider.py           # Provider Google (gemini-3.1-pro-preview via Google GenAI)
    ├── xai_provider.py              # Provider xAI (grok-4-1-fast-reasoning via AsyncOpenAI client)
    ├── qwen_provider.py             # Provider Qwen (qwen3.5-plus via AsyncOpenAI client)
    └── factory.py                   # LLMFactory com lazy-loading e cache de instâncias
```

---

## 3. Especificação da Interface `BaseLLMProvider` e Provedores

### 3.1. Contrato da Interface Abstrata (`backend/app/services/llm/base.py`)
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Optional, Any

class BaseLLMProvider(ABC):
    """Contrato abstrato que todos os conectores de LLM devem implementar."""
    
    provider_name: str
    default_model: str

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Emite os tokens da resposta de forma assíncrona chunk por chunk.
        """
        pass

    def _inject_web_context(
        self, 
        messages: List[Dict[str, str]], 
        web_search_context: Optional[str]
    ) -> List[Dict[str, str]]:
        """Injeta os resultados da pesquisa da web no prompt de sistema de forma limpa."""
        ...
```

### 3.2. Implementação das 5 Classes Concretas

| Provedor | Classe Concreta | SDK Assíncrono Utilizado | Particularidades Tratadas |
| :--- | :--- | :--- | :--- |
| **OpenAI** | `OpenAIProvider` | `openai.AsyncOpenAI` | Consumo assíncrono de chunks via `async for chunk in response: ...`. Modelo padrão: `gpt-5-2025-08-07`. |
| **Anthropic** | `AnthropicProvider` | `anthropic.AsyncAnthropic` | Separação obrigatória da mensagem com role `system` para o parâmetro nomeado `system=...`. Validação de alternância entre `user` e `assistant`. Modelo padrão: `claude-sonnet-4-6`. |
| **Google GenAI** | `GeminiProvider` | `google.genai` / SDK assíncrono | Conversão de roles para o formato `{"role": "user" \| "model", "parts": [...]}`. Execução em streaming sem bloqueio do event loop. Modelo padrão: `gemini-3.1-pro-preview`. |
| **xAI** | `XAIProvider` | `openai.AsyncOpenAI` | Reutilização do cliente assíncrono da OpenAI configurado com a `base_url="https://api.x.ai/v1"`. Modelo padrão: `grok-4-1-fast-reasoning`. |
| **Qwen** | `QwenProvider` | `openai.AsyncOpenAI` | Cliente assíncrono configurado com a `base_url=settings.QWEN_BASE_URL` (Alibaba Cloud DashScope ou DeepSeek compatible). Modelo padrão: `qwen3.5-plus`. |

---

## 4. Arquitetura do `LLMFactory` (`backend/app/services/llm/factory.py`)

A fábrica gerenciará o ciclo de vida dos provedores:
- **Resolução de Modelos:** Mapeia identificadores de modelos (ex.: `"GPT-5 (OpenAI)"`, `"gpt-5-2025-08-07"`, `"Claude Sonnet 4.6"`, `"Gemini-3"`, etc.) para a classe de provedor correspondente.
- **Cache de Conexões (Singleton per Provider):** Instancia os clientes HTTP assíncronos sob demanda (*lazy-loading*) e reutiliza o mesmo pool de conexões TCP, evitando *socket exhaustion* e overhead de recriação de sessões.
- **Tratamento de Exceções de Domínio:** Lança erros tipados e semânticos (`ProviderNotConfiguredException`, `ModelNotFoundException`) se uma chave estiver ausente no arquivo `.env`.

---

## 5. Migração e Otimização dos Serviços Auxiliares

### 5.1. Parser de Arquivos (`backend/app/services/file_parser.py`)
- Suporte a `.txt`, `.py`, `.md`, `.csv`, `.json`, `.pdf`, `.jpg`, `.png`, `.mp3`.
- **Prevenção de Bloqueio do Event Loop:** Como a biblioteca `pdfplumber` e a leitura de disco realizam I/O e processamento intensivo de CPU que bloqueariam o loop do FastAPI, todas as operações de parsing serão envelopadas via `asyncio.to_thread(self._sync_parse, file_path)`.

### 5.2. Motor de Busca Web (`backend/app/services/web_search.py`)
- Métodos de decisão (`should_search`) e extração de query (`extract_search_query`) preservados e tipados.
- Integração prioritária com **Tavily** quando configurado.
- Fallback automático para **DuckDuckGo** (`ddgs`) executado de forma não-bloqueante via `asyncio.to_thread`.
- Geração padronizada de metadados das fontes consultadas para retorno estruturado.

---

## 6. Orquestrador Unificado (`ChatOrchestrator`) e Eventos de Streaming

Para viabilizar a emissão de **Server-Sent Events (SSE)** na Fase 4 sem acoplamento à UI, o `ChatOrchestrator` emitirá dicionários tipados durante a geração:

```
[Fluxo de Eventos Emitidos pelo ChatOrchestrator]
   │
   ├── 1. Web Search Check: Se detectado -> Emite: {"event": "search_start", "query": "..."}
   │
   ├── 2. Web Search Results: Fontes encontradas -> Emite: {"event": "sources", "data": [...]}
   │
   ├── 3. LLM Tokens: A cada chunk gerado -> Emite: {"event": "chunk", "text": "..."}
   │
   └── 4. Finalização: Ao concluir -> Emite: {"event": "done", "metadata": {...}}
```

Essa padronização garante que:
- O backend não precise de nenhuma dependência de renderização visual (Gradio/HTML).
- O Frontend (Fase 5) receba eventos limpos via SSE e renderize os componentes visuais de carregamento, citação de fontes e digitação em tempo real.

---

## 7. Passo a Passo de Implementação da Fase 3

Após a aprovação deste plano, os seguintes passos técnicos serão executados:

1. **Atualização de Dependências no `requirements.txt`:**
   - Adicionar SDKs oficiais assíncronos: `openai`, `anthropic`, `google-genai`, `pdfplumber`, `ddgs`, `tavily-python`.
2. **Criação da Camada `llm/`:**
   - Implementar `BaseLLMProvider` em `backend/app/services/llm/base.py`.
   - Implementar `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`, `XAIProvider` e `QwenProvider`.
   - Implementar `LLMFactory` em `backend/app/services/llm/factory.py`.
3. **Criação dos Serviços de Domínio:**
   - Migrar e assincronizar `file_parser.py` em `backend/app/services/file_parser.py`.
   - Migrar e assincronizar `web_search.py` em `backend/app/services/web_search.py`.
4. **Criação do `ChatOrchestrator`:**
   - Implementar a coordenação assíncrona unificada em `backend/app/services/chat_orchestrator.py`.
5. **Criação de Teste de Integração Assíncrono:**
   - Script de teste para disparar requisições em streaming para os provedores configurados e validar os chunks assíncronos sem dependência do Gradio.
6. **Rebuild e Validação no Docker:**
   - Atualizar a imagem `rp_backend` no Docker e validar logs e funcionamento.

---

## 8. Critérios de Validação e Aceite da Fase 3

A fase será considerada concluída com sucesso quando:
- [ ] A interface `BaseLLMProvider` e as 5 implementações concretas estiverem criadas e tipadas.
- [ ] O `LLMFactory` instanciar e despachar corretamente para os 5 provedores.
- [ ] O `FileParserService` e o `WebSearchService` funcionarem de forma assíncrona sem bloquear o event loop.
- [ ] Um teste assíncrono validar que os tokens de resposta fluem via gerador assíncrono.
- [ ] O container `rp_backend` reiniciar com sucesso e manter status `healthy` no healthcheck.
- [ ] O arquivo `relatorio_fase_3.md` for gerado, documentando tudo o que foi implementado.

---

> ⚠️ **Aviso de Conformidade:** Seguindo estritamente a diretriz rígida de execução, **nenhum arquivo de código foi alterado ou criado**. Aguardo sua aprovação formal deste plano para iniciar a execução técnica da Fase 3.

