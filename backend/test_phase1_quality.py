"""
Offline validation for Phase 1 answer-quality improvements:
multimodal content, generation params, relevant-passage scraping and tool-context persistence.

Run inside the backend container:  python test_phase1_quality.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.llm.base import message_text
from app.services.llm.multimodal import build_user_content, resolve_upload_path
from app.services.llm.openrouter_provider import OpenRouterCatalog, OpenRouterProvider
from app.services.passage_selector import select_relevant_passages
from app.services.web_search import WebSearchService

PNG_URI = "data:image/png;base64,iVBORw0KGgo="


def check(label: str, condition: bool) -> None:
    print(f"  {'✓' if condition else '✗'} {label}")
    assert condition, label


async def test_multimodal() -> None:
    print("\n[1] Multimodal content")
    image = [{"filename": "a.png", "type": "image", "content": PNG_URI}]

    content = await build_user_content("Descreva", image, supports_modality=lambda m: m == "image")
    check("image becomes image_url part for vision models",
          isinstance(content, list) and content[1] == {"type": "image_url", "image_url": {"url": PNG_URI}})
    check("text part keeps the prompt", message_text({"content": content}).startswith("Descreva"))

    content = await build_user_content("Descreva", image, supports_modality=lambda m: False)
    check("text-only models get a plain string with a notice",
          isinstance(content, str) and "não aceita imagens" in content)

    with tempfile.TemporaryDirectory() as upload_dir:
        settings.UPLOAD_DIR = upload_dir
        audio_path = os.path.join(upload_dir, "x_note.mp3")
        with open(audio_path, "wb") as f:
            f.write(b"ID3fake-audio")
        audio = [{"filename": "note.mp3", "type": "audio", "content": audio_path}]

        content = await build_user_content("Resuma", audio, supports_modality=lambda m: m == "audio")
        check("audio becomes input_audio part for audio models",
              isinstance(content, list) and content[1]["type"] == "input_audio"
              and content[1]["input_audio"]["format"] == "mp3")

        async def fake_transcribe(b64: str, fmt: str) -> str:
            return "olá mundo"

        content = await build_user_content("Resuma", audio, supports_modality=lambda m: False,
                                           transcribe=fake_transcribe)
        check("audio is transcribed for non-audio models",
              isinstance(content, str) and "olá mundo" in content)

        check("path traversal outside UPLOAD_DIR is rejected", resolve_upload_path("/etc/passwd") is None)
        check("relative escape is rejected", resolve_upload_path(os.path.join(upload_dir, "../../etc/hosts")) is None)
        leak = [{"filename": "secret.mp3", "type": "audio", "content": "/etc/passwd"}]
        content = await build_user_content("x", leak, supports_modality=lambda m: True)
        check("forged audio path never reaches the model", isinstance(content, str) and "indisponível" in content)

    text = [{"filename": "a.py", "type": "text", "content": "print(1)"}]
    content = await build_user_content("Revise", text, supports_modality=lambda m: True)
    check("text attachments stay inline", isinstance(content, str) and "print(1)" in content)


def test_generation_params() -> None:
    print("\n[2] Generation parameters")
    soc = ChatOrchestrator.resolve_generation_params("cybernexus_soc")
    check("SOC profile: low temperature + high reasoning",
          soc["temperature"] == 0.2 and soc["reasoning_effort"] == "high")
    general = ChatOrchestrator.resolve_generation_params("general_assistant", temperature=1.1, reasoning_effort="none")
    check("request overrides win", general["temperature"] == 1.1 and general["reasoning_effort"] == "none")

    OpenRouterCatalog._models_by_id.update({
        "test/no-temp": {"supported_parameters": ["max_tokens", "reasoning"], "max_completion_tokens": 4000},
        "test/plain": {"supported_parameters": ["temperature"], "max_completion_tokens": None},
    })
    resolved = OpenRouterProvider.resolve_generation_params("test/no-temp", soc)
    check("unsupported temperature is dropped", "temperature" not in resolved)
    check("max_tokens is capped by the model limit", resolved["max_tokens"] == 4000)
    check("reasoning sent via extra_body", resolved["extra_body"]["reasoning"]["effort"] == "high")
    resolved = OpenRouterProvider.resolve_generation_params("test/plain", soc)
    check("models without reasoning get only supported params", resolved == {"temperature": 0.2})
    check("unknown models receive no optional params",
          OpenRouterProvider.resolve_generation_params("unknown/model", soc) == {})


def test_passage_selection() -> None:
    print("\n[3] Relevant-passage scraping")
    filler = "\n".join(f"Menu item {i} navegação institucional cookies login" for i in range(300))
    target = "O vencedor do Grande Prêmio de Interlagos 2026 foi Fulano, seguido por Beltrano."
    page = f"Título da Página\n{filler}\n{target}\n{filler}"
    selected = select_relevant_passages(page, "vencedor Grande Prêmio Interlagos 2026", max_chars=2000)
    check("relevant passage deep in the page is kept", target in selected)
    check("page title/lead is kept", selected.startswith("Título da Página"))
    check("budget is respected", len(selected) <= 2000)
    check("head truncation was the old behaviour (target lost)", target not in page[:4000])

    table = "[TABELA EXTRAÍDA]\n| Pos | Piloto |\n| --- | --- |\n| 1 | Fulano |\n[/TABELA EXTRAÍDA]"
    selected = select_relevant_passages(f"Intro\n{filler}\n{table}\n{filler}", "piloto pos", max_chars=1500)
    check("extracted tables are kept intact", table in selected)


def test_tool_context_persistence() -> None:
    print("\n[4] Tool-context persistence")
    results = [{"title": "Fonte A", "url": "https://a.example", "snippet": "s", "full_content": "conteúdo " * 300}]
    compact = WebSearchService.format_compact_context(results)
    check("compact context is bounded", 0 < len(compact) <= 4000 and "[1] Fonte A" in compact)

    history = [
        {"role": "user", "content": "Quem venceu o GP de Interlagos?"},
        {"role": "assistant", "content": "Fulano venceu [1].", "tool_context": {"query": "GP Interlagos", "context": compact}},
        {"role": "user", "content": "E quem ficou em segundo segundo a fonte 1?"},
    ]
    pruned = ChatOrchestrator._prune_and_sanitize_messages(history)
    check("pruning preserves tool_context", pruned[1].get("tool_context", {}).get("query") == "GP Interlagos")
    block = ChatOrchestrator.build_prior_tool_context_block(pruned)
    check("prior search is re-injected into the system prompt", "GP Interlagos" in block and "[1] Fonte A" in block)


async def main() -> None:
    print("=" * 70)
    print("🧪 Phase 1 – Answer Quality Validation")
    print("=" * 70)
    await test_multimodal()
    test_generation_params()
    test_passage_selection()
    test_tool_context_persistence()
    print("\n✅ All Phase 1 checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
