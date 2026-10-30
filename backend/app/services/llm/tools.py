import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from google.genai import types as genai_types

SEARCH_WEB_TOOL_NAME = "search_web"

SEARCH_WEB_DESCRIPTION = (
    "Pesquisa informações em tempo real na internet para obter dados atualizados, "
    "notícias recentes, eventos esportivos (como Fórmula 1, futebol, etc.), cotações, "
    "documentações técnicas recentes, lançamentos de software ou fatos posteriores ao "
    "corte de treinamento. Gere uma query de busca concisa, precisa e otimizada para "
    "motores de busca, levando em conta o histórico recente da conversa e a data atual informada no System Info. "
    "DIRETRIZES DE CONTEXTO E FORMULAÇÃO DA QUERY: "
    "(1) Analise obrigatoriamente as últimas mensagens do histórico da conversa para contextualizar a pesquisa. "
    "Se o assunto em discussão for cibersegurança (ex: MITRE ATT&CK, CVEs, ameaças cibernéticas, TTPs), a query "
    "deve focar estritamente nesse tema e NUNCA incluir termos de bibliotecas de programação (como SQLAlchemy, FastAPI) "
    "a menos que o usuário tenha pedido código explicitamente. "
    "(2) Verifique minuciosamente a data de publicação, a cronologia e o contexto completo do snippet "
    "retornado antes de assumir qualquer dado como válido ou como o evento mais recente. "
    "(3) Tenha extrema cautela ao ler listas, calendários ou tabelas agregadoras (ex: páginas com "
    "resultados de todas as corridas ou rodadas do ano), garantindo que o dado extraído (como vencedor, "
    "pódio ou placar) pertença estritamente ao evento específico pesquisado, sem misturar ou atribuir "
    "dados de eventos adjacentes na mesma página."
)

SEARCH_WEB_PARAMETERS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "A consulta de pesquisa otimizada para buscar na internet "
                "(ex: 'último GP Fórmula 1 2026 resultados vencedor')."
            )
        }
    },
    "required": ["query"]
}


@dataclass
class ToolCallRequest:
    """
    Represents an autonomous tool execution request emitted by an LLM during Turn 1 streaming.
    """
    id: str
    name: str
    query: str
    raw_assistant_data: Any = None


def parse_tool_query(raw_arguments: Any, fallback_query: str = "") -> str:
    """
    Safely parses the 'query' argument from a streamed JSON string or dict emitted by an LLM,
    including cases where parallel tool_calls concatenate multiple JSON objects.
    """
    if isinstance(raw_arguments, dict):
        q = str(raw_arguments.get("query", "")).strip()
        return q or fallback_query

    if isinstance(raw_arguments, str):
        cleaned = raw_arguments.strip()
        if not cleaned:
            return fallback_query
        try:
            parsed, _ = json.JSONDecoder().raw_decode(cleaned)
            if isinstance(parsed, dict):
                q = str(parsed.get("query", "")).strip()
                if q:
                    return q
        except Exception:
            pass

    return fallback_query


def get_openai_tools_and_choice(tools_mode: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Any]]:
    """
    Returns (tools, tool_choice) formatted for OpenAI / xAI / Qwen Chat Completions API.
    """
    if tools_mode not in ("auto", "always"):
        return None, None

    tools = [
        {
            "type": "function",
            "function": {
                "name": SEARCH_WEB_TOOL_NAME,
                "description": SEARCH_WEB_DESCRIPTION,
                "parameters": SEARCH_WEB_PARAMETERS_SCHEMA
            }
        }
    ]

    if tools_mode == "always":
        tool_choice: Any = {
            "type": "function",
            "function": {"name": SEARCH_WEB_TOOL_NAME}
        }
    else:
        tool_choice = "auto"

    return tools, tool_choice


def get_anthropic_tools_and_choice(tools_mode: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
    """
    Returns (tools, tool_choice) formatted for Anthropic Messages API.
    """
    if tools_mode not in ("auto", "always"):
        return None, None

    tools = [
        {
            "name": SEARCH_WEB_TOOL_NAME,
            "description": SEARCH_WEB_DESCRIPTION,
            "input_schema": SEARCH_WEB_PARAMETERS_SCHEMA
        }
    ]

    if tools_mode == "always":
        tool_choice = {"type": "tool", "name": SEARCH_WEB_TOOL_NAME}
    else:
        tool_choice = {"type": "auto"}

    return tools, tool_choice


def get_gemini_tools_and_config(
    tools_mode: str
) -> Tuple[Optional[List[genai_types.Tool]], Optional[genai_types.ToolConfig]]:
    """
    Returns (tools, tool_config) formatted for Google GenAI SDK (google-genai).
    """
    if tools_mode not in ("auto", "always"):
        return None, None

    func_decl = genai_types.FunctionDeclaration(
        name=SEARCH_WEB_TOOL_NAME,
        description=SEARCH_WEB_DESCRIPTION,
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "query": genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description="Consulta otimizada para busca na internet."
                )
            },
            required=["query"]
        )
    )

    tools = [genai_types.Tool(function_declarations=[func_decl])]
    mode_str = "ANY" if tools_mode == "always" else "AUTO"
    tool_config = genai_types.ToolConfig(
        function_calling_config=genai_types.FunctionCallingConfig(mode=mode_str)
    )

    return tools, tool_config


def ensure_tool_call_id(raw_id: Optional[str]) -> str:
    """Ensures every tool call has a valid non-empty identifier."""
    if raw_id and raw_id.strip():
        return raw_id.strip()
    return f"call_{uuid.uuid4().hex[:12]}"

