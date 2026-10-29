import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import logging
from app.services.llm.factory import LLMFactory
from app.services.llm.base import LLMProviderException, UsageMetadata
from app.services.llm.tools import ToolCallRequest
from app.services.web_search import WebSearchService
from app.services.cost_engine import CostEngine
from app.services.semantic_cache import SemanticCacheService, SemanticCacheLookupResult

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """
    High-level orchestrator implementing:
    1. Provider-Specific Capability Routing (Tool Disabling for Code Specialists like Qwen3-Coder).
    2. Context Pruning & Sanitization (Orphan/Failure cleanup & Topic Shift Detection).
    3. Deep Web Search Scraping (Full Page & Markdown Table extraction).
    4. Dual-Turn Agentic Streaming for SSE delivery.
    """

    MAX_HISTORY_MESSAGES = 8

    PROFILE_SOFTWARE_ENGINEER = (
        "Contexto Técnico e Stack Padrão de Desenvolvimento (Perfil: Engenheiro de Software):\n"
        "- Você está atuando como um Arquiteto e Engenheiro de Software Sênior.\n"
        "- A arquitetura padrão do usuário envolve Python (3.11+), FastAPI, React (TypeScript/Tailwind/Zustand), "
        "Docker e PostgreSQL (SQLAlchemy 2.0 Async).\n"
        "- Salvo instrução explícita em contrário na conversa, priorize exemplos de código limpo, seguro, tipado, "
        "padrões arquiteturais e recomendações técnicas alinhados a essa stack.\n"
        "- Quando a ferramenta `search_web` estiver disponível, utilize-a proativamente para consultar documentações "
        "atualizadas, releases, CVEs ou informações em tempo real, considerando a data atual do System Info."
    )

    PROFILE_GENERAL_ASSISTANT = (
        "Diretrizes de Comportamento (Perfil: Assistente Geral):\n"
        "- Você está atuando como um Assistente Geral versátil, objetivo, analítico e conciso.\n"
        "- Responda diretamente ao ponto, com clareza, estrutura limpa e utilidade prática para qualquer domínio "
        "(atualidades, negócios, ciências, esportes, finanças, cultura ou produtividade).\n"
        "- NÃO assuma contexto de programação ou engenharia de software e NÃO injete termos técnicos de TI "
        "a menos que o usuário pergunte explicitamente sobre tecnologia.\n"
        "- Quando a ferramenta `search_web` estiver disponível, utilize-a proativamente sempre que a pergunta "
        "envolver eventos recentes, notícias, resultados esportivos (ex: Fórmula 1), cotações ou fatos em tempo real, "
        "formulando queries ancoradas na data atual do System Info."
    )

    PROFILE_CYBERNEXUS_SOC = (
        "Diretrizes Operacionais e Contexto Tático (Perfil: CyberNexus SOC Nível 3 & DevSecOps Specialist):\n"
        "- Você está atuando como um Analista de SOC Nível 3 (Tier 3 Incident Responder) e Arquiteto Sênior de DevSecOps "
        "integrado nativamente ao hub CyberNexus.\n"
        "- Sua especialidade abrange Threat Intelligence, caça a ameaças (Threat Hunting), análise forense, correlação de "
        "eventos SIEM/SOAR, segurança de pipelines CI/CD (SAST, DAST, SCA, Container/IaC Security), gestão de CVEs "
        "(NIST NVD, CISA KEV, MITRE ATT&CK, CVSS v3.1/v4.0) e mitigação de vulnerabilidades (zero-day).\n"
        "- Sempre estruture análises técnicas de vulnerabilidades ou incidentes contendo:\n"
        "  1. **Sumário Executivo e Severidade:** CVE-ID, vetor CVSS, CWE associada e superfície de ataque.\n"
        "  2. **Análise de Exploração (Threat Intel):** Status de exploração ativa (in-the-wild), existência de PoC/Exploits públicos e TTPs (MITRE ATT&CK).\n"
        "  3. **Remediação e Hardening (DevSecOps):** Patches oficiais, regras de detecção (Sigma/YARA/WAF/Suricata) e controles compensatórios imediatos (workarounds) para contenção de zero-days.\n"
        "- Quando a ferramenta `search_web` estiver disponível, utilize-a PROATIVAMENTE para consultar boletins de segurança "
        "em tempo real, bases de CVEs (NIST NVD, MITRE, GitHub Advisories), alertas CISA, fóruns de segurança e repositórios "
        "de exploits, ancorando suas buscas na data atual informada no System Info."
    )

    BASE_CODE_SPECIALIST_PROFILE = (
        "Contexto Técnico e Especialização Estrita em Engenharia de Software:\n"
        "- Você está operando exclusivamente como Especialista em Código e Arquitetura de Software.\n"
        "- A stack padrão do usuário envolve Python (3.11+), FastAPI, React (TypeScript/Tailwind/Zustand), "
        "Docker e PostgreSQL (SQLAlchemy 2.0 Async).\n"
        "- Priorize código limpo, seguro, tipado, performático e pronto para produção."
    )

    # Alias for backwards compatibility
    BASE_GENERALIST_PROFILE = PROFILE_SOFTWARE_ENGINEER

    FAILURE_MARKERS = (
        "⚠️ *Erro",
        "[OpenAI Error:",
        "[Anthropic Error:",
        "[xAI Error:",
        "[Qwen Error:",
        "[Erro de Integração",
        "*(Geração interrompida pelo usuário)*",
        "Nenhum resultado encontrado na web"
    )

    STOPWORDS: Set[str] = {
        "para", "como", "qual", "quais", "quem", "onde", "quando", "porque", "porquê",
        "isso", "isto", "aquilo", "este", "esta", "esse", "essa", "pelo", "pela",
        "com", "sem", "sobre", "entre", "depois", "antes", "mais", "menos", "muito",
        "pode", "poderia", "fazer", "faça", "faca", "quero", "preciso", "saber",
        "diga", "explique", "mostre", "qual", "foi", "foram", "está", "esta", "estão",
        "voce", "você", "meu", "minha", "seus", "suas", "nosso", "nossa", "tudo",
        "what", "when", "where", "which", "who", "whom", "this", "that", "these",
        "those", "with", "from", "about", "into", "through", "after", "before"
    }

    CONTINUITY_PATTERNS = (
        r"\b(esse|essa|isso|isto|nele|nela|nisso|acima|anterior|anteriores)\b",
        r"\b(continue|continuar|explique melhor|detalhe|refatore|corrija|ajuste|melhore)\b",
        r"\b(no código|na tabela|no exemplo|nessa lista|nesse resultado|também|mesmo)\b",
        r"^(e\s+o|e\s+a|e\s+os|e\s+as|e\s+sobre|e\s+quanto|mas\s+e)\b"
    )

    def __init__(self):
        self.search_service = WebSearchService()

    def _build_effective_system_prompt(
        self,
        user_system_prompt: Optional[str] = None,
        client_timezone: Optional[str] = None,
        client_local_time: Optional[str] = None,
        supports_web_search: bool = True,
        profile_id: str = "software_engineer"
    ) -> str:
        """
        Monta o system_prompt efetivo combinando:
        1. Data/hora e fuso horário dinâmicos da máquina do cliente.
        2. Perfil contextual ('software_engineer' vs 'general_assistant') integrado ao
           guardrail de Tool Disabling (modelos code_specialist sem web search forçam BASE_CODE_SPECIALIST_PROFILE).
        3. System prompt personalizado configurado pelo usuário na sessão (se houver).
        """
        resolved_tz = (client_timezone or "").strip() or "UTC"
        resolved_time = (client_local_time or "").strip()

        if not resolved_time:
            try:
                tz_obj = ZoneInfo(resolved_tz)
            except (ZoneInfoNotFoundError, Exception):
                tz_obj = timezone.utc
                resolved_tz = "UTC"
            resolved_time = datetime.now(tz_obj).strftime("%Y-%m-%d %H:%M")

        time_info = (
            f"System Info: A data e hora atuais na máquina do usuário são {resolved_time} "
            f"(Fuso horário local: {resolved_tz})."
        )

        normalized_profile = (profile_id or "software_engineer").strip().lower()

        if not supports_web_search:
            if normalized_profile in ("general_assistant", "cybernexus_soc"):
                logger.info(
                    f"[Profile Guardrail] Code specialist model detected; overriding requested "
                    f"profile '{normalized_profile}' -> BASE_CODE_SPECIALIST_PROFILE."
                )
            profile_block = self.BASE_CODE_SPECIALIST_PROFILE
        elif normalized_profile == "cybernexus_soc":
            profile_block = self.PROFILE_CYBERNEXUS_SOC
        elif normalized_profile == "general_assistant":
            profile_block = self.PROFILE_GENERAL_ASSISTANT
        else:
            profile_block = self.PROFILE_SOFTWARE_ENGINEER

        base_context = f"{time_info}\n\n{profile_block}"

        if user_system_prompt and user_system_prompt.strip():
            return (
                f"{base_context}\n\n"
                f"--- Instruções Personalizadas da Sessão (Definidas pelo Usuário) ---\n"
                f"{user_system_prompt.strip()}"
            )

        return base_context

    @classmethod
    def _extract_semantic_keywords(cls, text: str) -> Set[str]:
        """Extracts meaningful lowercase keywords (>= 4 chars, excluding stopwords) from text."""
        words = re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", text.lower())
        return {w for w in words if w not in cls.STOPWORDS}

    @classmethod
    def _has_continuity_intent(cls, text: str) -> bool:
        """Checks if the user prompt explicitly references previous messages in the conversation."""
        lowered = text.lower().strip()
        for pattern in cls.CONTINUITY_PATTERNS:
            if re.search(pattern, lowered):
                return True
        return False

    @classmethod
    def _prune_and_sanitize_messages(cls, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Higieniza e poda o histórico da conversa antes de enviar ao provedor LLM:
        1. Remove turnos com falhas de API/ferramentas ou respostas órfãs/vazias.
        2. Detecta mudança abrupta de assunto (Topic Shift) e isola a nova pergunta para evitar vazamento de contexto.
        3. Aplica limite máximo de janela deslizante (MAX_HISTORY_MESSAGES).
        """
        if not messages:
            return []

        # Step 1: Sanitize failed, empty, or orphaned turns
        sanitized: List[Dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            if role == "assistant":
                if any(marker in content for marker in cls.FAILURE_MARKERS):
                    # Discard failed assistant response AND pop the preceding user prompt if it became orphaned
                    if sanitized and sanitized[-1].get("role") == "user":
                        sanitized.pop()
                    logger.info("[Context Sanitization] Discarded failed/orphaned assistant turn from history.")
                    continue

            # Ensure strict alternation (avoid consecutive user->user if a prior assistant turn was missing)
            if sanitized and sanitized[-1].get("role") == role and role == "user":
                sanitized[-1] = {"role": role, "content": content}
            else:
                sanitized.append({"role": role, "content": content})

        if len(sanitized) <= 1:
            return sanitized

        # Step 2: Topic Shift Detection on the latest user message
        last_msg = sanitized[-1]
        if last_msg.get("role") == "user" and len(sanitized) >= 3:
            current_text = last_msg.get("content", "")
            if not cls._has_continuity_intent(current_text):
                current_kw = cls._extract_semantic_keywords(current_text)
                prior_text = " ".join(m.get("content", "") for m in sanitized[:-1])
                prior_kw = cls._extract_semantic_keywords(prior_text)

                if current_kw and prior_kw and len(current_kw & prior_kw) == 0:
                    logger.info(
                        f"[Context Pruning] Topic shift detected (0 keyword overlap). "
                        f"Pruning {len(sanitized) - 1} prior messages to prevent context leakage."
                    )
                    return [last_msg]

        # Step 3: Sliding Window Cap (keep at most MAX_HISTORY_MESSAGES, starting with a 'user' message)
        if len(sanitized) > cls.MAX_HISTORY_MESSAGES:
            sanitized = sanitized[-cls.MAX_HISTORY_MESSAGES:]
            if sanitized and sanitized[0].get("role") != "user":
                sanitized = sanitized[1:]

        return sanitized

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model_name: str,
        system_prompt: Optional[str] = None,
        web_search_mode: str = "auto",
        file_contexts: Optional[List[Dict[str, Any]]] = None,
        client_timezone: Optional[str] = None,
        client_local_time: Optional[str] = None,
        profile_id: str = "software_engineer",
        user_id: Optional[Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Dual-Stream Agentic Generator yielding discrete SSE event payloads:
        - {"event": "search_start", "data": {"query": str}}
        - {"event": "sources", "data": {"query": str, "sources": list}}
        - {"event": "chunk", "data": {"text": str}}
        - {"event": "done", "data": {...}}
        - {"event": "error", "data": {"message": str}}
        """
        try:
            # 1. Resolve Provider and Concrete Model ID
            provider, target_model_id = LLMFactory.resolve(model_name)

            # 2. Asymmetric Tool Routing: Force tools_mode="disabled" for code specialists (Qwen3-Coder)
            effective_tools_mode = web_search_mode if provider.supports_web_search else "disabled"
            if not provider.supports_web_search and web_search_mode != "disabled":
                logger.info(
                    f"[Asymmetric Routing] Model '{target_model_id}' ({provider.specialization}) "
                    f"has web search disabled programmatically."
                )

            # 3. Context Pruning & Sanitization (prevent context leakage & clean failed turns)
            pruned_messages = self._prune_and_sanitize_messages(messages)

            # 3b. Semantic Cache Pre-Generation Interceptor (Single-turn / Self-contained, No attachments)
            is_cache_eligible = (
                not file_contexts
                and len(pruned_messages) == 1
                and pruned_messages[0].get("role") == "user"
                and web_search_mode != "always"
            )
            cache_lookup: Optional[SemanticCacheLookupResult] = None

            if is_cache_eligible:
                prompt_candidate = pruned_messages[0].get("content", "")
                cache_lookup = await SemanticCacheService.lookup(
                    prompt_text=prompt_candidate,
                    profile_id=profile_id,
                    supports_web_search=provider.supports_web_search,
                    user_id=user_id,
                    user_system_prompt=system_prompt
                )

                if cache_lookup.is_hit:
                    if cache_lookup.sources:
                        yield {
                            "event": "sources",
                            "data": {
                                "query": "Cache Semântico",
                                "total_sources": len(cache_lookup.sources),
                                "sources": cache_lookup.sources
                            }
                        }

                    cached_text = cache_lookup.response_text
                    chunk_size = 64
                    for idx in range(0, len(cached_text), chunk_size):
                        yield {
                            "event": "chunk",
                            "data": {"text": cached_text[idx:idx + chunk_size]}
                        }
                        await asyncio.sleep(0.004)

                    yield {
                        "event": "done",
                        "data": {
                            "model": target_model_id,
                            "provider": provider.provider_name,
                            "sources": cache_lookup.sources,
                            "full_response": cached_text,
                            "cached": True,
                            "cache_tier": cache_lookup.tier,
                            "similarity": round(cache_lookup.similarity, 4),
                            "usage": {
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                                "provider": provider.provider_name,
                                "model": target_model_id
                            }
                        }
                    }
                    return

            # 4. Handle File Context Injection on the active user message
            enriched_messages = [dict(m) for m in pruned_messages]
            if file_contexts and enriched_messages:
                file_text_bundle = ""
                for file_data in file_contexts:
                    fname = file_data.get("filename", "arquivo")
                    ftype = file_data.get("type", "text")
                    fcontent = file_data.get("content", "")

                    if ftype == "text":
                        file_text_bundle += f"\n\n--- Conteúdo do Arquivo ({fname}) ---\n{fcontent}\n--- Fim do Arquivo ---\n"
                    elif ftype == "image":
                        file_text_bundle += f"\n\n[Imagem Anexada: {fname}]"
                    elif ftype == "audio":
                        file_text_bundle += f"\n\n[Áudio Anexado: {fname}]"
                    else:
                        file_text_bundle += f"\n\n[Anexo: {fname} - {fcontent}]"

                if file_text_bundle:
                    for m in reversed(enriched_messages):
                        if m.get("role") == "user":
                            m["content"] = f"{m.get('content', '')}{file_text_bundle}"
                            break

            # 5. Build Effective System Prompt tailored to Provider Specialization & Active Profile
            effective_system_prompt = self._build_effective_system_prompt(
                user_system_prompt=system_prompt,
                client_timezone=client_timezone,
                client_local_time=client_local_time,
                supports_web_search=provider.supports_web_search,
                profile_id=profile_id
            )

            # 6. Turn 1: Stream from LLM with Agentic Tool Calling (if supported and enabled)
            full_response_text = ""
            sources_metadata: Optional[Dict[str, Any]] = None
            pending_tool_call: Optional[ToolCallRequest] = None
            total_prompt_tokens: int = 0
            total_completion_tokens: int = 0

            turn1_stream = provider.generate_stream(
                messages=enriched_messages,
                model=target_model_id,
                system_prompt=effective_system_prompt,
                web_search_context=None,
                tools_mode=effective_tools_mode,
                tool_interaction=None
            )

            async for item in turn1_stream:
                if isinstance(item, ToolCallRequest):
                    pending_tool_call = item
                elif isinstance(item, UsageMetadata):
                    total_prompt_tokens += item.prompt_tokens
                    total_completion_tokens += item.completion_tokens
                elif isinstance(item, str):
                    full_response_text += item
                    yield {
                        "event": "chunk",
                        "data": {"text": item}
                    }

            # 7. If the LLM requested a Tool Call (`search_web`), execute Deep Scraping & Turn 2
            if pending_tool_call and provider.supports_web_search:
                search_query = pending_tool_call.query.strip()
                logger.info(
                    f"[Agentic Tool Call] Provider '{provider.provider_name}' invoked "
                    f"'{pending_tool_call.name}' with query: '{search_query}'"
                )

                # 7a. Emit real-time UI feedback ('search_start')
                yield {
                    "event": "search_start",
                    "data": {"query": search_query}
                }

                # 7b. Execute asynchronous web search + Deep Page/Table Scraping on Top 2 URLs
                search_results = await self.search_service.search(search_query)

                if search_results:
                    tool_output_text = self.search_service.format_search_context(search_results)
                    sources_metadata = self.search_service.format_sources_metadata(search_results, search_query)
                    yield {
                        "event": "sources",
                        "data": sources_metadata
                    }
                else:
                    tool_output_text = (
                        f"Nenhum resultado encontrado na web para a busca '{search_query}'. "
                        "Informe ao usuário de forma transparente e responda com seu conhecimento disponível."
                    )
                    sources_metadata = {"query": search_query, "total_sources": 0, "sources": []}
                    yield {
                        "event": "sources",
                        "data": sources_metadata
                    }

                # 7c. Turn 2: Resume LLM streaming with Deep Scraped content & tables
                turn2_stream = provider.generate_stream(
                    messages=enriched_messages,
                    model=target_model_id,
                    system_prompt=effective_system_prompt,
                    web_search_context=None,
                    tools_mode="disabled",
                    tool_interaction={
                        "call": pending_tool_call,
                        "output": tool_output_text
                    }
                )

                async for item2 in turn2_stream:
                    if isinstance(item2, UsageMetadata):
                        total_prompt_tokens += item2.prompt_tokens
                        total_completion_tokens += item2.completion_tokens
                    elif isinstance(item2, str):
                        full_response_text += item2
                        yield {
                            "event": "chunk",
                            "data": {"text": item2}
                        }

            # Fallback token estimation if provider stream did not report native usage
            if total_prompt_tokens == 0 and total_completion_tokens == 0 and full_response_text:
                total_prompt_tokens = CostEngine.estimate_messages_tokens(
                    enriched_messages, effective_system_prompt
                )
                total_completion_tokens = CostEngine.estimate_tokens_from_text(full_response_text)

            # 8. Emit Completion Event (with cache_store_candidate on eligible Cache Miss)
            has_failure = any(marker in full_response_text for marker in self.FAILURE_MARKERS)
            cache_store_candidate = None
            if is_cache_eligible and cache_lookup and not cache_lookup.is_hit and full_response_text and not has_failure:
                cache_store_candidate = {
                    "prompt_text": pruned_messages[0].get("content", ""),
                    "effective_profile": cache_lookup.effective_profile,
                    "scope_key": cache_lookup.scope_key,
                    "prompt_hash": cache_lookup.prompt_hash,
                    "query_embedding": cache_lookup.query_embedding
                }

            yield {
                "event": "done",
                "data": {
                    "model": target_model_id,
                    "provider": provider.provider_name,
                    "sources": sources_metadata.get("sources", []) if sources_metadata else [],
                    "full_response": full_response_text,
                    "cached": False,
                    "cache_store_candidate": cache_store_candidate,
                    "usage": {
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                        "provider": provider.provider_name,
                        "model": target_model_id
                    }
                }
            }

        except LLMProviderException as provider_err:
            logger.warning(f"LLM Provider error in stream_chat: {provider_err}")
            yield {
                "event": "error",
                "data": {"message": str(provider_err)}
            }
        except Exception as e:
            logger.error(f"Unexpected error in stream_chat: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {"message": f"Erro interno ao processar chat: {str(e)}"}
            }
