# 📋 Plano de Ação - Fase 4: Endpoints REST e Server-Sent Events (SSE)

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 4 - Endpoints REST e Streaming SSE  
**Status:** ⏳ Aguardando Aprovação Formal  

---

## 1. Objetivo da Fase 4
Construir a camada de API pública do backend FastAPI, expondo os contratos REST e de streaming necessários para alimentar a interface do usuário:
1. **CRUD Completo de Sessões e Histórico:** Gerenciamento relacional de conversas no PostgreSQL via SQLAlchemy assíncrono.
2. **Endpoint Seguro de Upload de Arquivos:** Recepção de arquivos multipart, salvamento no volume `/app/uploads` e pré-parsing automático com `FileParserService`.
3. **Endpoint de Streaming Server-Sent Events (`POST /api/v1/chat/completions/stream`):** Consumo assíncrono do `ChatOrchestrator` emitindo eventos em tempo real (`search_start`, `sources`, `chunk`, `done`, `error`) com headers de desativação de buffering.
4. **Persistência Transacional:** Gravação automática imediata da mensagem do usuário e persistência da resposta final do assistente (incluindo metadados de fontes) no banco de dados ao término do stream.

---

## 2. Estrutura de Rotas e Endpoints da Fase 4

```
backend/app/
├── api/
│   └── v1/
│       ├── router.py                        # Registro de todos os routers da v1
│       └── endpoints/
│           ├── health.py                    # GET /api/v1/health (implementado na Fase 2)
│           ├── sessions.py                  # CRUD de conversas e mensagens
│           ├── files.py                     # Upload e extração de arquivos
│           └── chat.py                      # Streaming SSE via ChatOrchestrator
└── schemas/
    ├── chat.py                              # DTOs de requisição e eventos do Chat
    └── upload.py                            # DTOs de upload e dados extraídos
```

---

## 3. Especificação Detalhada dos Endpoints

### 3.1. CRUD de Sessões e Histórico (`backend/app/api/v1/endpoints/sessions.py`)

| Método | Rota | Descrição | Status HTTP |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/sessions` | Lista todas as sessões salvas, ordenadas por `updated_at DESC`. | `200 OK` |
| `POST` | `/api/v1/sessions` | Cria uma nova sessão (com `title`, `model_name`, `system_prompt`, `web_search_mode`). | `201 Created` |
| `GET` | `/api/v1/sessions/{session_id}` | Retorna os detalhes da sessão incluindo todas as mensagens ordenadas cronologicamente (`created_at ASC`). | `200 OK` / `404` |
| `PATCH` | `/api/v1/sessions/{session_id}` | Atualiza título, modelo, prompt de sistema ou modo de busca da sessão. | `200 OK` / `404` |
| `DELETE` | `/api/v1/sessions/{session_id}` | Exclui a sessão e todas as mensagens associadas (via cascade do PostgreSQL). | `204 No Content` |
| `DELETE` | `/api/v1/sessions/{session_id}/messages` | Limpa o histórico de mensagens da sessão mantendo as configurações da conversa. | `200 OK` |

### 3.2. Endpoint de Upload de Arquivos (`backend/app/api/v1/endpoints/files.py`)
- **Rota:** `POST /api/v1/files/upload`
- **Payload:** `multipart/form-data` contendo `file: UploadFile`.
- **Procedimento Seguro de Armazenamento:**
  1. Sanitização do nome original do arquivo para prevenir ataques de *path traversal*.
  2. Geração de prefixo UUID único: `/app/uploads/{uuid}_{sanitized_filename}`.
  3. Gravação assíncrona em blocos no volume montado `./data/uploads`.
  4. Execução imediata do `FileParserService.parse_file(file_path)` para extrair texto/conteúdo em segundo plano.
- **Resposta (`200 OK`):**
  ```json
  {
    "file_id": "c85d8cf4-2c26-444a-a621-e8d1a1b8cf44",
    "filename": "relatorio.pdf",
    "file_type": "text",
    "size_bytes": 45820,
    "parsed_content": "--- Página 1 ---\nConteúdo extraído..."
  }
  ```

---

## 4. Endpoint de Streaming SSE e Ciclo de Vida da Mensagem

### 4.1. Contrato da Requisição (`POST /api/v1/chat/completions/stream`)
```json
{
  "session_id": "8e3be249-e76c-49cc-8e65-ba5a029f3437",
  "message": {
    "content": "Explique a arquitetura orientada a eventos e cite fontes recentes",
    "attachments": [
      {
        "filename": "relatorio.pdf",
        "type": "text",
        "content": "Conteúdo pré-parseado..."
      }
    ]
  },
  "model_name": "GPT-5 (OpenAI)",
  "system_prompt": "Você é um arquiteto especialista...",
  "web_search_mode": "auto"
}
```

### 4.2. Formato do Streaming Server-Sent Events (SSE)
O endpoint responderá com `Content-Type: text/event-stream` e cabeçalhos `Cache-Control: no-cache`, `X-Accel-Buffering: no` e `Connection: keep-alive`:

```http
event: search_start
data: {"query": "arquitetura orientada a eventos 2026"}

event: sources
data: {"query": "...", "total_sources": 3, "sources": [{"index": 1, "title": "...", "url": "..."}]}

event: chunk
data: {"text": "A arquitetura "}

event: chunk
data: {"text": "orientada a eventos..."}

event: done
data: {"message_id": "d982e6c5-...", "model": "gpt-5-2025-08-07", "full_response": "..."}
```

---

## 5. Lógica de Persistência e Transação no Banco de Dados

Para garantir integridade transacional sem atrasar a emissão do primeiro token para o usuário:

```
[Início da Requisição SSE]
   │
   ├── 1. Validação: Localiza a sessão no PostgreSQL. Se não existir, retorna 404.
   │
   ├── 2. Persistência do Usuário: Insere ChatMessage(role='user', content=...) e executa session.commit().
   │      (A mensagem do usuário já fica salva mesmo se o streaming cair depois).
   │
   ├── 3. Carregamento do Histórico: Carrega todas as mensagens anteriores da sessão do banco para montar a memória conversacional.
   │
   ├── 4. Streaming Ativo: Invoca ChatOrchestrator.stream_chat(...) e despacha eventos SSE (search, sources, chunks).
   │      (Acumula o texto completo da resposta na memória da requisição).
   │
   ├── 5. Persistência do Assistente (Ao finalizar o stream):
   │      - Insere ChatMessage(role='assistant', content=accumulated_text, metadata_json={"sources": [...]}).
   │      - Atualiza session.updated_at = func.now().
   │      - Se for a primeira mensagem e o título for "New Chat", atualiza o título automaticamente para os primeiros 40 caracteres da pergunta.
   │      - Executa session.commit().
   │
   └── 6. Emissão do Evento Final: Envia event: done contendo o ID da mensagem gerada no banco.
```

---

## 6. Passo a Passo de Implementação da Fase 4

1. **Definição de Novos Schemas Pydantic:**
   - Criar `backend/app/schemas/chat.py` (modelos de request para completions e eventos de retorno).
   - Criar `backend/app/schemas/upload.py` (modelos para upload de arquivos).
2. **Implementação do Router de Sessões (`sessions.py`):**
   - Implementar endpoints de listagem, criação, detalhe com mensagens, edição e exclusão de sessões.
3. **Implementação do Router de Upload (`files.py`):**
   - Implementar upload multipart assíncrono com validação e parsing automático.
4. **Implementação do Router de Streaming SSE (`chat.py`):**
   - Implementar `POST /chat/completions/stream` utilizando `StreamingResponse` do Starlette/FastAPI com formatador SSE (`data: ...\n\n`).
   - Integrar a persistência do usuário pré-stream e do assistente pós-stream.
5. **Registro das Rotas:**
   - Atualizar `backend/app/api/v1/router.py` incluindo `sessions.router`, `files.router` e `chat.router`.
6. **Testes de Integração Automatizados:**
   - Script de teste para simular o fluxo completo:
     1. Criar sessão -> `POST /api/v1/sessions`
     2. Fazer upload de arquivo -> `POST /api/v1/files/upload`
     3. Consumir SSE stream -> `POST /api/v1/chat/completions/stream`
     4. Consultar histórico -> `GET /api/v1/sessions/{id}` e validar se mensagens foram persistidas no PostgreSQL.

---

## 7. Critérios de Validação e Aceite da Fase 4

A fase será considerada concluída com sucesso quando:
- [ ] O Swagger UI (`http://localhost:8085/docs`) exibir os novos grupos de endpoints (`Sessions`, `Files`, `Chat`).
- [ ] O fluxo CRUD de sessões for testado e retornar códigos HTTP semânticos (200, 201, 204, 404).
- [ ] O upload de arquivo salvar no volume `/app/uploads` e retornar o conteúdo extraído.
- [ ] O endpoint de streaming responder com `text/event-stream` e entregar os tokens em tempo real.
- [ ] O histórico do chat for consultado no banco PostgreSQL e comprovar que as mensagens (usuário e assistente) foram gravadas com sucesso.
- [ ] O arquivo `relatorio_fase_4.md` for gerado, documentando toda a implementação.

---

> ⚠️ **Aviso de Conformidade:** Seguindo estritamente a regra de ouro, **nenhum arquivo de código foi alterado ou criado**. Aguardo sua liberação técnica para iniciar a execução da Fase 4.

