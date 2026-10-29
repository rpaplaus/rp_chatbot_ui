import asyncio
import os
import sys
import json
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.chat_orchestrator import ChatOrchestrator

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

async def run_end_to_end_test():
    print("=" * 65)
    print("🧪 [TEST SUITE] Phase 4, 4.5 & Context Injection v2 Flow")
    print(f"Target API: {BASE_URL}")
    print("=" * 65)

    # 0a. Unit check for ChatOrchestrator._build_effective_system_prompt
    print("\n0a. Testing ChatOrchestrator._build_effective_system_prompt (v2):")
    orch = ChatOrchestrator()
    prompt_with_client = orch._build_effective_system_prompt(
        user_system_prompt="Responda sempre em formato executivo.",
        client_timezone="America/Sao_Paulo",
        client_local_time="2026-10-28 15:49"
    )
    assert "2026-10-28 15:49" in prompt_with_client
    assert "America/Sao_Paulo" in prompt_with_client
    assert "Python, FastAPI, React, Docker e PostgreSQL" in prompt_with_client
    assert "Responda sempre em formato executivo." in prompt_with_client
    assert "Portugal" not in prompt_with_client
    print("  ✓ Dynamic client time, timezone, base tech stack and custom user prompt verified.")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 0b. Authenticate to obtain JWT Access Token
        print("\n0b. Authenticating via POST /auth/login:")
        r_auth = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": settings.APP_PASSWORD}
        )
        assert r_auth.status_code == 200, f"Login failed: {r_auth.text}"
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  ✓ Authenticated as '{settings.APP_USER}'")

        # 1. Health check
        print("\n1. Testing GET /health:")
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200, f"Healthcheck failed: {r.text}"
        data = r.json()
        print(f"  ✓ Status: {data['status']}, Database: {data['database']}, Redis: {data['redis']}")

        # 2. Create Session
        print("\n2. Testing POST /sessions:")
        create_payload = {
            "title": "New Chat",
            "model_name": "grok-4-1-fast-reasoning",
            "system_prompt": "Você é um assistente conciso.",
            "web_search_mode": "disabled"
        }
        r = await client.post(f"{BASE_URL}/sessions", headers=headers, json=create_payload)
        assert r.status_code == 201, f"Create session failed: {r.text}"
        session_data = r.json()
        session_id = session_data["id"]
        print(f"  ✓ Session created: ID={session_id}, UserID={session_data['user_id']}")

        # 3. List Sessions
        print("\n3. Testing GET /sessions:")
        r = await client.get(f"{BASE_URL}/sessions", headers=headers)
        assert r.status_code == 200
        sessions_list = r.json()
        assert any(s["id"] == session_id for s in sessions_list)
        print(f"  ✓ Session list returned {len(sessions_list)} sessions (found created session).")

        # 4. Upload File
        print("\n4. Testing POST /files/upload:")
        test_filename = "docker_test_doc.txt"
        test_content = b"Arquitetura de Microsservicos: Caddy + FastAPI + PostgreSQL + Redis"
        files = {"file": (test_filename, test_content, "text/plain")}
        r = await client.post(f"{BASE_URL}/files/upload", headers=headers, files=files)
        assert r.status_code == 200, f"Upload failed: {r.text}"
        upload_data = r.json()
        print(f"  ✓ Uploaded: {upload_data['filename']} (ID: {upload_data['file_id']})")

        # 5. Stream Chat Completion with SSE + Client Timezone & Local Time
        print("\n5. Testing POST /chat/completions/stream (SSE + Client Time Context):")
        chat_payload = {
            "session_id": session_id,
            "message": {
                "content": "Qual é a data e hora locais exatas da minha máquina neste momento e qual o banco mencionado no anexo? Seja breve.",
                "attachments": [
                    {
                        "file_id": upload_data["file_id"],
                        "filename": upload_data["filename"],
                        "type": upload_data["file_type"],
                        "content": upload_data["parsed_content"]
                    }
                ]
            },
            "model_name": "grok-4-1-fast-reasoning",
            "web_search_mode": "disabled",
            "client_timezone": "America/Sao_Paulo",
            "client_local_time": "2026-10-28 15:49"
        }

        received_events = []
        assistant_chunks = []

        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json=chat_payload
        ) as stream_resp:
            assert stream_resp.status_code == 200, f"SSE failed: {stream_resp.status_code}"
            assert "text/event-stream" in stream_resp.headers.get("content-type", "")

            current_event = None
            async for line in stream_resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                    received_events.append(current_event)
                elif line.startswith("data:"):
                    raw_data = line.replace("data:", "").strip()
                    try:
                        parsed_event_data = json.loads(raw_data)
                        if current_event == "chunk":
                            chunk_text = parsed_event_data.get("text", "")
                            assistant_chunks.append(chunk_text)
                            print(chunk_text, end="", flush=True)
                        elif current_event == "persisted":
                            print(f"\n  ✓ Event 'persisted' received: message_id={parsed_event_data.get('message_id')}")
                    except Exception:
                        pass

        print(f"\n  ✓ Stream completed. Full text: '{''.join(assistant_chunks).strip()}'")
        assert "chunk" in received_events
        assert "done" in received_events
        assert "persisted" in received_events

        # 6. Verify PostgreSQL History Persistence
        print("\n6. Testing GET /sessions/{session_id}:")
        r = await client.get(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        assert r.status_code == 200
        full_session = r.json()
        messages = full_session.get("messages", [])
        assert len(messages) >= 2
        print(f"  ✓ Verified {len(messages)} messages persisted in PostgreSQL.")

        # 6b. Test Server-Side PDF Generation (POST /tools/pdf)
        print("\n6b. Testing POST /tools/pdf (WeasyPrint SSR):")
        sample_markdown = (
            "# Arquitetura de Microsserviços\n\n"
            "Exemplo de código em **Python 3.11 + FastAPI**:\n\n"
            "```python\n"
            "from fastapi import FastAPI\n\n"
            "app = FastAPI(title='RP_ChatBot')\n\n"
            "@app.get('/health')\n"
            "async def health():\n"
            "    return {'status': 'healthy', 'stack': ['FastAPI', 'React', 'PostgreSQL', 'Docker']}\n"
            "```\n\n"
            "| Serviço | Porta |\n"
            "| :--- | :--- |\n"
            "| Caddy | 8085 |\n"
            "| Backend | 8002 |\n"
        )
        r_pdf = await client.post(
            f"{BASE_URL}/tools/pdf",
            headers=headers,
            json={
                "content": sample_markdown,
                "title": "Arquitetura RP_ChatBot",
                "model_name": "GPT-5 (OpenAI)"
            }
        )
        assert r_pdf.status_code == 200, f"PDF generation failed: {r_pdf.text}"
        assert r_pdf.headers.get("content-type") == "application/pdf"
        assert r_pdf.content.startswith(b"%PDF-"), "Response is not a valid PDF binary"
        print(f"  ✓ PDF generated successfully! Size: {len(r_pdf.content)} bytes, Header: {r_pdf.content[:8]!r}")

        # 7. Delete Session
        print("\n7. Testing DELETE /sessions/{session_id}:")
        r = await client.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        assert r.status_code == 204
        print("  ✓ Session deleted.")

    print("\n" + "=" * 65)
    print("🎉 ALL AUTHENTICATED & CONTEXT INJECTION V2 TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())
