import asyncio
import os
import sys
import json
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


async def run_agentic_tool_calling_test():
    print("=" * 72)
    print("🤖 [AGENTIC TOOL CALLING TEST] Native Function Calling & Dual-Stream SSE")
    print(f"Target API: {BASE_URL}")
    print("=" * 72)

    async with httpx.AsyncClient(timeout=90.0) as client:
        # 1. Authenticate
        r_auth = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": settings.APP_PASSWORD}
        )
        assert r_auth.status_code == 200, f"Login failed: {r_auth.text}"
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"\n1. Authenticated as '{settings.APP_USER}'")

        # 2. Create test session with web_search_mode = 'auto'
        r_sess = await client.post(
            f"{BASE_URL}/sessions",
            headers=headers,
            json={
                "title": "Teste Agentic F1",
                "model_name": "grok-4-1-fast-reasoning",
                "system_prompt": "Seja objetivo e cite as fontes encontradas.",
                "web_search_mode": "auto"
            }
        )
        assert r_sess.status_code == 201
        session_id = r_sess.json()["id"]
        print(f"2. Created session: {session_id} (web_search_mode='auto')")

        # 3. Ask about the latest Formula 1 GP (without explicit search trigger word like 'pesquise')
        prompt = "Quem venceu o último Grande Prêmio de Fórmula 1 e qual foi o pódio?"
        print(f"\n3. Sending prompt (mode='auto'): \"{prompt}\"")

        chat_payload = {
            "session_id": session_id,
            "message": {"content": prompt},
            "model_name": "grok-4-1-fast-reasoning",
            "web_search_mode": "auto",
            "client_timezone": "Europe/Lisbon",
            "client_local_time": "2026-10-28 19:55"
        }

        events_seen = []
        ai_formulated_query = None
        sources_count = 0
        response_chunks = []

        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json=chat_payload
        ) as stream_resp:
            assert stream_resp.status_code == 200, f"SSE failed: {stream_resp.status_code}"
            current_event = None
            async for line in stream_resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                    events_seen.append(current_event)
                elif line.startswith("data:"):
                    raw_data = line.replace("data:", "").strip()
                    try:
                        payload = json.loads(raw_data)
                        if current_event == "search_start":
                            ai_formulated_query = payload.get("query")
                            print(f"\n  🔍 [SSE event: search_start] AI Autonomous Query: '{ai_formulated_query}'")
                        elif current_event == "sources":
                            sources_count = len(payload.get("sources", []))
                            print(f"  🌐 [SSE event: sources] Found {sources_count} web sources:")
                            for s in payload.get("sources", [])[:3]:
                                print(f"     - [{s.get('index')}] {s.get('title')} ({s.get('url')})")
                            print("\n  💬 [SSE Turn 2 Stream]: ", end="", flush=True)
                        elif current_event == "chunk":
                            txt = payload.get("text", "")
                            response_chunks.append(txt)
                            print(txt, end="", flush=True)
                        elif current_event == "persisted":
                            print(f"\n\n  💾 [SSE event: persisted] Message ID: {payload.get('message_id')}")
                    except Exception:
                        pass

        assert "search_start" in events_seen, "Expected LLM to trigger 'search_start' via native Tool Calling!"
        assert "sources" in events_seen, "Expected 'sources' event after tool execution!"
        assert "chunk" in events_seen, "Expected 'chunk' events in Turn 2!"
        assert ai_formulated_query, "Expected non-empty search query formulated by the LLM!"

        # 4. Cleanup test session
        await client.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        print("4. Test session cleaned up.")

    print("\n" + "=" * 72)
    print("🎉 AGENTIC TOOL CALLING & DUAL-STREAM SSE VERIFIED SUCCESSFULLY!")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(run_agentic_tool_calling_test())

