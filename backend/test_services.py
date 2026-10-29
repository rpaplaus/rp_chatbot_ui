import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.llm.factory import LLMFactory
from app.services.file_parser import FileParserService
from app.services.web_search import WebSearchService
from app.services.chat_orchestrator import ChatOrchestrator

async def run_tests():
    print("=" * 60)
    print("🧪 [TEST SUITE] Phase 3 - LLM Strategy & Services Validation")
    print("=" * 60)

    # 1. Test Factory Resolution for all 5 providers
    print("\n1. Testing LLMFactory model resolution:")
    models_to_test = [
        "GPT-5 (OpenAI)",
        "Claude Sonnet 4.6",
        "Gemini-3",
        "grok-4-1-fast-reasoning",
        "Qwen3-Coder"
    ]
    for model_name in models_to_test:
        provider, target_id = LLMFactory.resolve(model_name)
        print(f"  ✓ Model '{model_name}' -> Provider: {provider.provider_name} (ID: {target_id})")

    # 2. Test File Parser
    print("\n2. Testing FileParserService:")
    test_file_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    parsed = await FileParserService.parse_file(test_file_path)
    print(f"  ✓ Parsed {parsed['filename']}: Type={parsed['type']}, Size={parsed['size_bytes']} bytes")
    assert parsed["type"] == "text"
    assert parsed["size_bytes"] > 0

    # 3. Test WebSearchService Heuristics
    print("\n3. Testing WebSearchService heuristics:")
    search_service = WebSearchService()
    assert search_service.should_search("Pesquise as últimas notícias de tecnologia hoje", "auto") is True
    assert search_service.should_search("Como escrever um loop for em Python?", "auto") is False
    assert search_service.should_search("Como escrever um loop for em Python?", "always") is True
    assert search_service.should_search("Pesquise as últimas notícias", "disabled") is False
    print("  ✓ Web search trigger heuristics passed.")

    # 4. Test Chat Orchestrator Event Emission with File Context
    print("\n4. Testing ChatOrchestrator streaming with OpenAI & File context:")
    orchestrator = ChatOrchestrator()
    file_context = [parsed]

    received_events = []
    chunk_buffer = []

    async for event in orchestrator.stream_chat(
        messages=[{"role": "user", "content": "Responda em uma palavra qual a biblioteca de ORM listada no arquivo"}],
        model_name="GPT-5 (OpenAI)",
        web_search_mode="disabled",
        file_contexts=file_context
    ):
        received_events.append(event["event"])
        if event["event"] == "chunk":
            chunk_buffer.append(event["data"]["text"])
        elif event["event"] == "done":
            print(f"  ✓ Response received: {''.join(chunk_buffer).strip()}")

    assert "chunk" in received_events
    assert "done" in received_events
    print(f"  ✓ Event cycle verified: {set(received_events)}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
