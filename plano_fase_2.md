# 📋 Plano de Ação - Fase 2: Fundação do Backend (FastAPI, Pydantic Settings, SQLAlchemy & Alembic)

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 2 - Fundação do Backend  
**Status:** ⏳ Aguardando Aprovação Formal  

---

## 1. Objetivo da Fase 2
Construir a base arquitetural do microsserviço de Backend utilizando **FastAPI** assíncrono (Python 3.11), estabelecendo:
1. Validação tipada de configurações e chaves de API com `pydantic-settings`.
2. Camada de persistência relacional assíncrona com **SQLAlchemy 2.0** (`asyncpg`) e **Alembic** para versionamento de schema.
3. Modelagem de dados para substituir a persistência legada em arquivos JSON locais (`memory/*.json`) pelas entidades de banco `ChatSession` e `ChatMessage`.
4. Conexão ao Redis para suporte a cache e controle de streaming.
5. Endpoint de verificação de integridade (`GET /api/v1/health`) validando status de DB, Redis e provedores ativos.

---

## 2. Estrutura de Diretórios Proposta (`backend/`)

A organização seguirá os princípios de Clean Architecture e separação de responsabilidades recomendados para FastAPI:

```
backend/
├── alembic/
│   ├── versions/
│   │   └── 001_initial_schema.py    # Migração inicial das tabelas
│   ├── env.py                       # Configuração assíncrona do Alembic
│   ├── script.py.mako               # Template de migrações
│   └── README
├── alembic.ini                      # Configuração do CLI de migrações
├── app/
│   ├── __init__.py
│   ├── main.py                      # Instância FastAPI, Lifespan e Middlewares
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings com validação de env vars
│   │   ├── database.py              # Async Engine, sessionmaker e get_db dependency
│   │   └── redis.py                 # Pool de conexão Redis e get_redis dependency
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                  # DeclarativeBase e Mixins comuns (UUID, timestamps)
│   │   ├── session.py               # Entidade ChatSession
│   │   └── message.py               # Entidade ChatMessage
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py                # DTOs de verificação de integridade
│   │   ├── session.py               # DTOs de Sessão (Request/Response)
│   │   └── message.py               # DTOs de Mensagem (Request/Response)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                  # Injeção de dependências (DB, Redis)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # Roteador central da v1
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── health.py        # Endpoint GET /api/v1/health
│   └── services/                    # Camada de serviços (preparada para Fases 3 e 4)
│       └── __init__.py
├── requirements.txt                 # Dependências exclusivas do backend
├── Dockerfile                       # Container do Backend otimizado
└── entrypoint.sh                    # Script de boot (Alembic migrate + Uvicorn)
```

---

## 3. Configuração do `pydantic-settings` e Validação de Chaves

O módulo `app/core/config.py` centralizará todas as configurações com validação estrita baseada em `pydantic-settings`:

### 3.1. Campos Mapeados e Regras de Validação
- **Ambiente & Aplicação:**
  - `PROJECT_NAME: str = "RP_ChatBot API"`
  - `ENVIRONMENT: str = "production"` (ou `development`)
  - `PORT: int = 8000`
  - `CORS_ORIGINS: list[str] = ["https://chat.rpaplaus.com", "http://localhost:5185", "http://localhost:8085"]`
- **Infraestrutura:**
  - `DATABASE_URL: str`: Validação de string de conexão assíncrona (`postgresql+asyncpg://...`).
  - `REDIS_URL: str`: Validação de URL de conexão Redis com autenticação.
  - `SECRET_KEY: str`: Chave para hashing e proteção de endpoints.
- **Provedores de LLM (Checagem em tempo de boot):**
  - `OPENAI_API_KEY: Optional[str] = None`
  - `ANTHROPIC_API_KEY: Optional[str] = None`
  - `GEMINI_API_KEY: Optional[str] = None`
  - `XAI_API_KEY: Optional[str] = None`
  - `QWEN_API_KEY: Optional[str] = None`
  - `QWEN_BASE_URL: str = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"`
  - `TAVILY_API_KEY: Optional[str] = None`
- **Métodos Auxiliares:**
  - `available_models`: Método que inspeciona dinamicamente quais chaves estão presentes e retorna a lista de provedores ativos e funcionais, emitindo logs de aviso para chaves ausentes.

---

## 4. Modelagem das Entidades no SQLAlchemy 2.0 (Assíncrono)

Substituiremos os arquivos `memory/*.json` por um modelo relacional normalizado no PostgreSQL:

### 4.1. Entidade `ChatSession` (Tabela `sessions`)
Representa uma conversa do usuário:
- `id`: `UUID` (Primary Key, padrão `uuid.uuid4`)
- `title`: `VARCHAR(255)` (Título da conversa, padrão "New Chat")
- `system_prompt`: `TEXT` (Opcional, instruções personalizadas do sistema)
- `model_name`: `VARCHAR(100)` (Modelo selecionado, ex: "GPT-5 (OpenAI)")
- `web_search_mode`: `VARCHAR(20)` (Modo de busca: "auto", "always", "disabled")
- `created_at`: `TIMESTAMPTZ` (Padrão `func.now()`)
- `updated_at`: `TIMESTAMPTZ` (Padrão `func.now()`, com trigger `onupdate=func.now()`)
- `messages`: Relacionamento 1:N com `ChatMessage` (com `cascade="all, delete-orphan"` para deleção em cascata)

### 4.2. Entidade `ChatMessage` (Tabela `messages`)
Representa cada mensagem individual enviada ou gerada:
- `id`: `UUID` (Primary Key, padrão `uuid.uuid4`)
- `session_id`: `UUID` (Foreign Key apontando para `sessions.id` com `ondelete="CASCADE"`, com índice B-tree)
- `role`: `VARCHAR(20)` ("user", "assistant", "system")
- `content`: `TEXT` (Conteúdo da mensagem)
- `metadata_json`: `JSONB` (Metadados estruturados: fontes de busca na web consultadas, dados de anexos processados, tempo de resposta, contagem de tokens)
- `created_at`: `TIMESTAMPTZ` (Padrão `func.now()`, indexado para ordenação cronológica rápida)

---

## 5. Gerenciamento de Migrações com Alembic

- O Alembic será inicializado com suporte nativo a código assíncrono (`asyncpg`).
- O arquivo `alembic/env.py` importará `Base.metadata` e executará as migrações online utilizando a conexão assíncrona do `app.core.database.async_engine`.
- A migração `001_initial_schema.py` será gerada para criar as tabelas `sessions` e `messages` com seus índices e constraints.
- Um script `entrypoint.sh` executará automaticamente `alembic upgrade head` antes de subir o Uvicorn, garantindo que o banco esteja sempre atualizado na subida do container.

---

## 6. Passo a Passo de Execução da Fase 2 (Após Aprovação)

1. **Definir Dependências do Backend (`backend/requirements.txt`):**
   - `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
   - `sqlalchemy>=2.0.0`, `asyncpg`, `alembic`, `greenlet`
   - `redis>=5.0.0`, `python-dotenv`, `python-multipart`
2. **Atualizar `backend/Dockerfile` e `backend/entrypoint.sh`:**
   - Instalação de dependências do Python.
   - Script de entrada executando migrações e iniciando Uvicorn na porta 8000.
3. **Implementar Camada Core:**
   - `app/core/config.py`: Definição de `Settings`.
   - `app/core/database.py`: Instanciação do `create_async_engine` e `async_sessionmaker`.
   - `app/core/redis.py`: Cliente assíncrono do Redis com pool de conexões.
4. **Implementar Modelos e Schemas:**
   - `app/models/base.py`, `app/models/session.py`, `app/models/message.py`.
   - `app/schemas/health.py`, `app/schemas/session.py`, `app/schemas/message.py`.
5. **Configurar e Gerar Migrações Alembic:**
   - Inicializar `alembic.ini` e `alembic/env.py`.
   - Criar arquivo de migração `001_initial_schema.py`.
6. **Implementar API e Endpoint de Healthcheck:**
   - `app/api/v1/endpoints/health.py`: Testa `SELECT 1` no Postgres, `PING` no Redis e inspeciona chaves de LLM configuradas.
   - `app/main.py`: Setup de middlewares, lifespan e inclusão de routers.

---

## 7. Critérios de Validação e Aceite da Fase 2

A Fase 2 será considerada aprovada e concluída quando:
- [ ] O backend compilar e subir no Docker conectado à rede `rp_network`.
- [ ] O Alembic aplicar com sucesso a migração inicial no PostgreSQL (`rp_postgres`).
- [ ] O endpoint `GET http://localhost:8085/api/v1/health` (via Caddy) e `GET http://localhost:8002/api/v1/health` (direto) responderem HTTP 200 com:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "active_providers": ["openai", "anthropic", "gemini", "xai", "qwen"]
  }
  ```
- [ ] O Swagger UI estiver navegável e funcional em `https://chat.rpaplaus.com/docs` ou `http://localhost:8085/docs`.
- [ ] O arquivo `relatorio_fase_2.md` for gerado, documentando tudo o que foi implementado e solicitando autorização para a Fase 3.

---

> ⚠️ **Aviso de Conformidade:** Seguindo rigorosamente a diretriz de execução, **nenhum arquivo de código foi alterado ou criado**. Aguardo sua aprovação formal deste plano para iniciar a execução da Fase 2.

