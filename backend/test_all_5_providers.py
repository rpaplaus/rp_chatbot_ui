import asyncio
import json
import httpx
from app.core.config import settings


BASE_URL = "http://localhost:8000/api/v1"


async def run_remaining_providers():
    async with httpx.AsyncClient(timeout=60.0) as client:
        login_res = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": settings.APP_USER,
                "password": settings.APP_PASSWORD
            }
        )
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        sess_res = await client.post(
            f"{BASE_URL}/sessions",
            headers=headers,
            json={
                "title": "Auditoria FinOps 5 LLMs",
                "model_name": "Claude Sonnet 4.6",
                "web_search_mode": "disabled"
            }
        )
        session_id = sess_res.json()["id"]

        for model_label in ["Claude Sonnet 4.6", "grok-4-1-fast-reasoning"]:
            print(f"⚡ Disparando streaming SSE com '{model_label}'...")
            done_usage = None
            chunks_received = 0
            async with client.stream(
                "POST",
                f"{BASE_URL}/chat/completions/stream",
                headers=headers,
                json={
                    "session_id": session_id,
                    "message": {
                        "role": "user",
                        "content": f"Responda em 1 linha: Confirme que a telemetria FinOps do modelo {model_label} está ativa."
                    },
                    "model_name": model_label,
                    "web_search_mode": "disabled"
                }
            ) as stream_res:
                assert stream_res.status_code == 200
                current_event = ""
                async for line in stream_res.aiter_lines():
                    if line.startswith("event:"):
                        current_event = line.replace("event:", "").strip()
                    elif line.startswith("data:"):
                        raw_data = line.replace("data:", "").strip()
                        try:
                            parsed = json.loads(raw_data)
                        except Exception:
                            parsed = {}
                        if current_event == "chunk":
                            chunks_received += 1
                        elif current_event == "done":
                            done_usage = parsed.get("usage")
            print(f"   └─► Stream concluído ({chunks_received} chunks) | Usage capturado: {done_usage}")

        await asyncio.sleep(1.2)
        usage = (await client.get(f"{BASE_URL}/metrics/usage", headers=headers)).json()
        print("\n📊 RESUMO CONSOLIDADO DOS 5 PROVEDORES (/api/v1/metrics/usage):")
        print(json.dumps(usage, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(run_remaining_providers())

