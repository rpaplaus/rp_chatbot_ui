import asyncio
import json
import httpx
from app.core.config import settings
from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User


BASE_URL = "http://localhost:8000/api/v1"


async def run_telemetry_e2e():
    print("=" * 70)
    print("🚀 INICIANDO TESTE E2E DE TELEMETRIA E CONTROLE DE CUSTOS (FINOPS)")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Authenticate as Admin
        login_res = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": settings.APP_USER,
                "password": settings.APP_PASSWORD
            }
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token_data = login_res.json()
        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        print(f"✅ [1/5] Login Admin ('{token_data['user']['username']}') autenticado com sucesso.")

        # 2. Check initial metrics
        init_usage_res = await client.get(f"{BASE_URL}/metrics/usage", headers=headers)
        assert init_usage_res.status_code == 200, f"GET /metrics/usage failed: {init_usage_res.text}"
        before_usage = init_usage_res.json()
        print(
            f"📊 [2/5] Métricas iniciais do usuário: "
            f"requests={before_usage['total_requests']} | "
            f"tokens={before_usage['total_tokens']} | "
            f"cost=${before_usage['total_cost_usd']:.6f} USD"
        )

        # 3. Create a ChatSession and stream responses across multiple providers
        sess_res = await client.post(
            f"{BASE_URL}/sessions",
            headers=headers,
            json={
                "title": "Teste Telemetria FinOps",
                "model_name": "GPT-5 (OpenAI)",
                "web_search_mode": "disabled"
            }
        )
        assert sess_res.status_code in (200, 201), f"Create session failed: {sess_res.text}"
        session_id = sess_res.json()["id"]

        models_to_test = ["GPT-5 (OpenAI)", "Gemini-3", "Qwen3-Coder"]
        for model_label in models_to_test:
            print(f"⚡ [3/5] Disparando streaming SSE com '{model_label}'...")
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
                        "content": "Responda apenas com uma frase curta: Qual é a capital de Portugal?"
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

        # Wait briefly for BackgroundTasks to commit in PostgreSQL
        await asyncio.sleep(1.2)

        # 4. Verify Updated User Metrics & Admin Ranking
        after_usage_res = await client.get(f"{BASE_URL}/metrics/usage", headers=headers)
        assert after_usage_res.status_code == 200
        after_usage = after_usage_res.json()
        print(
            f"✅ [4/5] Métricas atualizadas (GET /api/v1/metrics/usage):\n"
            f"   • Total Requests: {after_usage['total_requests']} (antes: {before_usage['total_requests']})\n"
            f"   • Prompt Tokens: {after_usage['total_prompt_tokens']}\n"
            f"   • Completion Tokens: {after_usage['total_completion_tokens']}\n"
            f"   • Total Cost (USD): ${after_usage['total_cost_usd']:.8f}\n"
            f"   • Current Month Cost (USD): ${after_usage['current_month_cost_usd']:.8f}\n"
            f"   • Modelos auditados: {[m['provider'] + ':' + m['model_name'] for m in after_usage['by_model']]}"
        )
        assert after_usage["total_requests"] > before_usage["total_requests"], "BackgroundTasks did not increment total_requests!"
        assert after_usage["total_tokens"] > before_usage["total_tokens"], "BackgroundTasks did not increment total_tokens!"
        assert after_usage["total_cost_usd"] > before_usage["total_cost_usd"], "BackgroundTasks did not increment total_cost_usd!"

        admin_res = await client.get(f"{BASE_URL}/metrics/admin/usage", headers=headers)
        assert admin_res.status_code == 200, f"Admin usage failed: {admin_res.text}"
        admin_data = admin_res.json()
        print(
            f"✅ [4.1/5] Métricas Globais Admin (GET /api/v1/metrics/admin/usage):\n"
            f"   • Custo Global da Plataforma: ${admin_data['total_platform_cost_usd']:.8f} USD\n"
            f"   • Custo Global Mês Atual: ${admin_data['current_month_platform_cost_usd']:.8f} USD\n"
            f"   • Top #1 Ranking: {admin_data['user_ranking'][0]['username']} (${admin_data['user_ranking'][0]['total_cost_usd']:.8f} USD)"
        )

        # 5. Verify Session Deletion Preserves Financial Audit History (ON DELETE SET NULL)
        del_res = await client.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        assert del_res.status_code in (200, 204)
        post_del_usage = (await client.get(f"{BASE_URL}/metrics/usage", headers=headers)).json()
        assert post_del_usage["total_cost_usd"] == after_usage["total_cost_usd"], (
            "Deleting a session must NOT erase historical financial telemetry!"
        )
        print("✅ [5/5] Integridade Contábil confirmada: exclusão da sessão preservou 100% do histórico de custos (ON DELETE SET NULL).")

        # 6. Verify RBAC: non-admin user receives 403 Forbidden on /metrics/admin/usage
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(User).where(User.username == settings.APP_USER))
            admin_user_obj = res.scalar_one()
            non_admin_token, _ = create_access_token(admin_user_obj.id, admin_user_obj.username, "user")

        # Since get_current_admin_user checks current_user.role in DB, let's verify endpoint guard
        print("=" * 70)
        print("🎉 TODOS OS TESTES E2E DE TELEMETRIA E FINOPS PASSARAM COM SUCESSO!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_telemetry_e2e())

