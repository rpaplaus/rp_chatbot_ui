import asyncio
import os
import sys
import json
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.chat_orchestrator import ChatOrchestrator

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


async def run_context_amnesia_suite():
    print("=" * 76)
    print("🛡️ [SUITE] Validação da Correção de Amnésia de Contexto & Agente de Busca")
    print(f"Target API: {BASE_URL}")
    print("=" * 76)

    # -------------------------------------------------------------------------
    # TEST 1: Heurística do Agente de Pesquisa (Dev/Stack) - Leitura de Histórico
    # -------------------------------------------------------------------------
    print("\n[1] Verificando Heurística Contextual do Agente de Busca (Dev/Stack):")

    cyber_history = [
        {"role": "user", "content": "Explique o framework MITRE ATT&CK e como categorizar táticas adversárias."},
        {"role": "assistant", "content": "O MITRE ATT&CK organiza táticas e técnicas de ameaças cibernéticas em matrizes detalhadas."},
        {"role": "user", "content": "Quais são as principais técnicas de persistência mais utilizadas por invasores?"}
    ]

    # Caso 1.1: O LLM sob o perfil software_engineer alucina 'SQLAlchemy' na query de busca
    hallucinated_query = "SQLAlchemy 2.0 Async MITRE ATT&CK persistence techniques"
    refined_1 = ChatOrchestrator.contextualize_search_query(
        search_query=hallucinated_query,
        messages=cyber_history,
        profile_id="software_engineer",
        n_history=4
    )
    print(f"  Query Alucinada: '{hallucinated_query}'")
    print(f"  Query Refinada:  '{refined_1}'")
    assert "sqlalchemy" not in refined_1.lower(), "SQLAlchemy não deve constar na query refinada!"
    assert "mitre" in refined_1.lower() or "persistence" in refined_1.lower(), "Contexto de segurança deve ser mantido!"
    print("  ✓ Termos padrão alucinados (SQLAlchemy) foram expurgados com base no histórico de cibersegurança!")

    # Caso 1.2: Query puramente de SQLAlchemy emitida por alucinação completa do perfil Dev/Stack
    pure_hallucination = "SQLAlchemy 2.0 Async"
    refined_2 = ChatOrchestrator.contextualize_search_query(
        search_query=pure_hallucination,
        messages=cyber_history,
        profile_id="software_engineer",
        n_history=4
    )
    print(f"  Query Alucinação Pura: '{pure_hallucination}'")
    print(f"  Query Reancorada:       '{refined_2}'")
    assert "sqlalchemy" not in refined_2.lower()
    assert "mitre" in refined_2.lower()
    print("  ✓ Alucinação total reancorada para o tema real da conversa (MITRE ATT&CK)!")

    # Caso 1.3: Query curta e vaga que precisa ser ancorada ao tema da sessão
    vague_query = "técnicas de persistência"
    refined_3 = ChatOrchestrator.contextualize_search_query(
        search_query=vague_query,
        messages=cyber_history,
        profile_id="software_engineer",
        n_history=4
    )
    print(f"  Query Vaga:      '{vague_query}'")
    print(f"  Query Ancorada:  '{refined_3}'")
    assert "mitre att&ck" in refined_3.lower()
    print("  ✓ Query vaga ancorada ao contexto recente de cibersegurança!")

    # Caso 1.4: Usuário pede explicitamente SQLAlchemy na conversa -> Não deve ser removido
    dev_history = [
        {"role": "user", "content": "Como configuro o SQLAlchemy 2.0 com FastAPI?"},
        {"role": "assistant", "content": "Use AsyncSessionLocal e mapped_column."},
        {"role": "user", "content": "Pesquise documentação do SQLAlchemy"}
    ]
    legit_query = "SQLAlchemy async engine connection pool"
    legit_refined = ChatOrchestrator.contextualize_search_query(
        search_query=legit_query,
        messages=dev_history,
        profile_id="software_engineer",
        n_history=4
    )
    assert "sqlalchemy" in legit_refined.lower(), "Termo solicitado legitimamente deve ser preservado!"
    print("  ✓ Consultas legítimas de programação são integralmente preservadas quando solicitadas!")

    # -------------------------------------------------------------------------
    # TEST 2: Preservação de Histórico e Continuidade (Sem Amnésia de Contexto)
    # -------------------------------------------------------------------------
    print("\n[2] Verificando Preservação de Histórico e Continuidade contra Amnésia:")

    # Turnos de conversa sobre MITRE ATT&CK seguidos de pergunta de follow-up
    conv_history = [
        {"role": "user", "content": "Explique o framework MITRE ATT&CK em cibersegurança."},
        {"role": "assistant", "content": "O MITRE ATT&CK é uma base estruturada de táticas e técnicas de ameaças."},
        {"role": "user", "content": "Quais técnicas são mais perigosas?"}
    ]
    pruned_conv = ChatOrchestrator._prune_and_sanitize_messages(conv_history)
    assert len(pruned_conv) == 3, f"Histórico não deve ser podado para follow-up! Got len={len(pruned_conv)}"
    print(f"  ✓ Follow-up preservou todos os {len(pruned_conv)} turnos do diálogo!")

    # Pergunta sobre histórico anterior ("O que conversamos antes?" ou "Não encontrou nada no histórico?")
    meta_history = [
        {"role": "user", "content": "Quais vulnerabilidades CVE recentes afetam Linux?"},
        {"role": "assistant", "content": "Diversas vulnerabilidades no kernel Linux foram catalogadas recentemente."},
        {"role": "user", "content": "O que falamos na mensagem anterior?"}
    ]
    pruned_meta = ChatOrchestrator._prune_and_sanitize_messages(meta_history)
    assert len(pruned_meta) == 3, f"Pergunta sobre conversa anterior deve manter histórico! Got len={len(pruned_meta)}"
    print(f"  ✓ Pergunta autoreferencial preservou histórico completo ({len(pruned_meta)} turnos)!")

    # Regressão: Tarefa standalone explícita de código com assunto totalmente novo deve podar
    f1_to_code = [
        {"role": "user", "content": "Quem venceu a corrida de Fórmula 1?"},
        {"role": "assistant", "content": "Max Verstappen venceu o Grande Prêmio."},
        {"role": "user", "content": "Implemente um endpoint FastAPI assíncrono com SQLAlchemy para listar usuários."}
    ]
    pruned_standalone = ChatOrchestrator._prune_and_sanitize_messages(f1_to_code)
    assert len(pruned_standalone) == 1, f"Tarefa standalone nova deve ser podada! Got len={len(pruned_standalone)}"
    assert "FastAPI" in pruned_standalone[0]["content"]
    print("  ✓ Regressão OK: Tarefa imperativa de código nova é devidamente isolada!")

    # -------------------------------------------------------------------------
    # TEST 3: Teste End-to-End via API: Preservação de Sessão & Troca de Perfil
    # -------------------------------------------------------------------------
    print("\n[3] Teste End-to-End: Troca de Perfil (Geral -> Dev/Stack) na mesma Sessão:")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Autenticação
        r_auth = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": settings.APP_USER, "password": settings.APP_PASSWORD}
        )
        assert r_auth.status_code == 200, f"Falha no login: {r_auth.text}"
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Criação de Sessão
        r_sess = await client.post(
            f"{BASE_URL}/sessions",
            headers=headers,
            json={
                "title": "Sessão Teste MITRE & Perfil Switch",
                "model_name": "GPT-5 (OpenAI)",
                "web_search_mode": "auto"
            }
        )
        assert r_sess.status_code == 201
        session_id = r_sess.json()["id"]
        print(f"  ✓ Sessão criada: {session_id}")

        # Turno 1: Perfil general_assistant sobre MITRE ATT&CK
        t1_prompt = "Explique concisamente o framework MITRE ATT&CK para detecção de ameaças."
        print(f"\n  [Turno 1 - Perfil: general_assistant] Enviando: '{t1_prompt}'")

        t1_response_text = ""
        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "message": {"content": t1_prompt},
                "profile_id": "general_assistant",
                "model_name": "GPT-5 (OpenAI)",
                "web_search_mode": "disabled"
            }
        ) as stream1:
            assert stream1.status_code == 200
            async for line in stream1.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = json.loads(line.replace("data:", "").strip())
                    if "text" in payload:
                        t1_response_text += payload["text"]

        print(f"  Turno 1 concluído ({len(t1_response_text)} caracteres recebidos).")
        assert len(t1_response_text) > 20

        # Verifica histórico persistido no banco
        r_det = await client.get(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        assert r_det.status_code == 200
        msgs_db = r_det.json().get("messages", [])
        assert len(msgs_db) >= 2, f"Esperado pelo menos 2 msgs no DB, encontrou {len(msgs_db)}"
        print(f"  ✓ Banco de dados possui {len(msgs_db)} mensagens persistidas para a sessão.")

        # Turno 2: TROCA DE PERFIL para software_engineer (Dev/Stack) na MESMA sessão
        # Pergunta de follow-up contextual
        t2_prompt = "Com base no que conversamos sobre o MITRE ATT&CK, como posso estruturar a correlação desses eventos?"
        print(f"\n  [Turno 2 - Perfil: software_engineer (Dev/Stack)] Enviando follow-up na mesma sessão...")

        t2_response_text = ""
        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "message": {"content": t2_prompt},
                "profile_id": "software_engineer",  # TROCA DE PERFIL NO MEIO DA SESSÃO!
                "model_name": "GPT-5 (OpenAI)",
                "web_search_mode": "disabled"
            }
        ) as stream2:
            assert stream2.status_code == 200
            async for line in stream2.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = json.loads(line.replace("data:", "").strip())
                    if "text" in payload:
                        t2_response_text += payload["text"]

        print(f"\n  💬 [Resposta Turno 2 (Dev/Stack)]:\n{t2_response_text[:300]}...\n")

        # Validações cruciais contra a Amnésia de Contexto
        t2_lower = t2_response_text.lower()
        assert "não encontrei nenhuma conversa anterior" not in t2_lower, "LLM relatou amnésia de contexto!"
        assert "não encontrei histórico" not in t2_lower
        assert "mitre" in t2_lower or "att&ck" in t2_lower or "evento" in t2_lower or "tática" in t2_lower or "técnica" in t2_lower, "Contexto de MITRE ATT&CK foi perdido!"
        print("  ✓ LLM manteve memória perfeita do Turno 1 após a troca de perfil para Dev/Stack!")

        # Turno 3: Teste com payload contendo array 'messages' diretamente (suporte Headless / API)
        print("\n[4] Teste de Injeção de Histórico via array 'messages' no Payload:")
        t3_prompt = "Resuma em tópicos curtos o que foi discutido nesta sessão."
        payload_messages = [
            {"role": "user", "content": "Discussão inicial sobre CVE-2026-9999 e MITRE ATT&CK T1059."},
            {"role": "assistant", "content": "Detalhamos a técnica T1059 (Command and Scripting Interpreter)."},
            {"role": "user", "content": t3_prompt}
        ]

        t3_response_text = ""
        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions/stream",
            headers=headers,
            json={
                "session_id": session_id,
                "messages": payload_messages,
                "profile_id": "software_engineer",
                "model_name": "GPT-5 (OpenAI)",
                "web_search_mode": "disabled"
            }
        ) as stream3:
            assert stream3.status_code == 200
            async for line in stream3.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = json.loads(line.replace("data:", "").strip())
                    if "text" in payload:
                        t3_response_text += payload["text"]

        t3_lower = t3_response_text.lower()
        assert "t1059" in t3_lower or "cve-2026-9999" in t3_lower or "command" in t3_lower, "Histórico injetado via messages array deve ser lido pelo LLM!"
        print(f"  ✓ Payload 'messages' injetado com sucesso no contexto do LLM! ({len(t3_response_text)} chars)")

        # Limpeza da sessão
        await client.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        print("  ✓ Sessão de teste limpa.")

    print("\n" + "=" * 76)
    print("🎉 TODAS AS CORREÇÕES DE AMNÉSIA DE CONTEXTO E HEURÍSTICA DE BUSCA FORAM VALIDADAS COM SUCESSO!")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(run_context_amnesia_suite())

