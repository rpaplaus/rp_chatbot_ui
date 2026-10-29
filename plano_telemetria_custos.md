# 📊 Plano de Arquitetura — Módulo de Telemetria e Controle de Custos por Usuário (FinOps Multi-LLM)

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 5 — Telemetria Financeira, Cost Engine Multi-Provedor e Painel de Monitoramento  
**Status:** ⏳ Aguardando Aprovação Técnica  

---

## 1. Objetivo Executivo
Implementar uma arquitetura de **Observabilidade e FinOps em Tempo Real** para rastrear, tarifar e auditar o consumo de tokens (*Input* e *Output*) e o custo financeiro em dólares (**USD**) gerado por cada usuário e sessão de chat através dos **5 provedores de IA** integrados (`OpenAI GPT-5`, `Anthropic Claude Sonnet 4.6`, `Google Gemini 3.1 Pro`, `xAI Grok-4` e `Alibaba Qwen3-Coder`), garantindo **impacto zero na latência do streaming SSE** por meio de processamento assíncrono em background (`BackgroundTasks`).

---

## 2. Pilar 1: Modelagem de Dados e Banco (SQLAlchemy 2.0 + Alembic)

### 2.1. Nova Entidade `TokenUsage` (`backend/app/models/token_usage.py`)
Criação da tabela `token_usage` no PostgreSQL utilizando SQLAlchemy 2.0 (`Mapped` / `mapped_column`), mantendo conformidade com `Base` e `UUIDMixin` de `backend/app/models/base.py`.

#### Decisão Arquitetural de Integridade Financeira (`ON DELETE SET NULL` para Sessões)
- O vínculo `user_id` possui `ForeignKey("users.id", ondelete="CASCADE")` (`nullable=False`), associando permanentemente o custo ao usuário responsável.
- O vínculo `session_id` utilizará `ForeignKey("sessions.id", ondelete="SET NULL")` (`nullable=True`). **Justificativa de Arquitetura:** Caso o usuário exclua uma conversa (`DELETE /api/v1/sessions/{id}`) ou limpe seu histórico, o registro contábil/financeiro do consumo já realizado na API das LLMs **não pode ser apagado**, preservando a auditoria de custos mensais e globais da plataforma.

#### Estrutura da Tabela `token_usage`
| Coluna | Tipo SQL / SQLAlchemy | Constraints / Índices | Descrição |
| :--- | :--- | :--- | :--- |
| `id` | `UUID(as_uuid=True)` | `PK`, `default=uuid.uuid4`, `index=True` | Identificador único do registro de telemetria (via `UUIDMixin`). |
| `user_id` | `UUID(as_uuid=True)` | `FK("users.id", ondelete="CASCADE")`, `NOT NULL`, `index=True` | Usuário proprietário da requisição. |
| `session_id` | `UUID(as_uuid=True)` | `FK("sessions.id", ondelete="SET NULL")`, `NULLABLE`, `index=True` | Sessão de chat onde o consumo ocorreu (preserva histórico mesmo se a sessão for deletada). |
| `provider` | `String(50)` | `NOT NULL`, `index=True` | Identificador do provedor (`openai`, `anthropic`, `gemini`, `xai`, `qwen`). |
| `model_name` | `String(100)` | `NOT NULL`, `index=True` | ID técnico do modelo executado (ex: `gpt-5-2025-08-07`, `claude-sonnet-4-6`). |
| `prompt_tokens` | `Integer` | `NOT NULL`, `default=0` | Total de tokens de entrada (*input/context*) consumidos na chamada. |
| `completion_tokens` | `Integer` | `NOT NULL`, `default=0` | Total de tokens de saída (*output/reasoning*) gerados pela LLM. |
| `total_tokens` | `Integer` | `NOT NULL`, `default=0` | Soma consolidada (`prompt_tokens + completion_tokens`). |
| `total_cost` | `Numeric(14, 8)` | `NOT NULL`, `default=0.0` | Custo exato calculado em **USD** com precisão de 8 casas decimais (evita erros de ponto flutuante IEEE 754 em microtransações). |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()`, `NOT NULL`, `index=True` | Timestamp exato da transação (indexado para agregações de mês vigente). |

#### Atualização de Relacionamentos ORM
- **`backend/app/models/user.py` (`User`):** Adição de `token_usages: Mapped[List["TokenUsage"]] = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")`.
- **`backend/app/models/session.py` (`ChatSession`):** Adição de `token_usages: Mapped[List["TokenUsage"]] = relationship("TokenUsage", back_populates="session")`.
- **`backend/app/models/__init__.py`:** Exportação de `TokenUsage` em `__all__` para registro automático no `Base.metadata` utilizado pelo Alembic.

### 2.2. Planejamento da Migração Alembic (`backend/alembic/versions/003_add_token_usage_telemetry.py`)
- **Identificadores de Revisão:**
  - `revision = "003_token_usage_telemetry"`
  - `down_revision = "002_users_tenant"`
- **Operações em `upgrade()`:**
  1. Criação da tabela `token_usage` com todas as colunas e chaves estrangeiras (`users.id` e `sessions.id`).
  2. Criação de índices simples (`ix_token_usage_user_id`, `ix_token_usage_session_id`, `ix_token_usage_model_name`, `ix_token_usage_created_at`) e um **índice composto** `ix_token_usage_user_created` em `(user_id, created_at)` para acelerar consultas de fechamento mensal por usuário.
- **Operações em `downgrade()`:**
  1. Remoção ordenada dos índices compostos e simples.
  2. `op.drop_table("token_usage")`.

---

## 3. Pilar 2: Cost Engine e Interceptação no Streaming (Backend)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    Fluxo de Telemetria Assíncrona Zero-Latency                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Provedor LLM (OpenAI / Anthropic / Gemini / xAI / Qwen)                             │
│    └─► Emite chunks de texto em tempo real + captura metadados nativos no último chunk │
│    └─► Ao encerrar o stream, emite objeto interno `UsageMetadata(prompt, completion)`  │
│                                                                                        │
│ 2. ChatOrchestrator (`stream_chat`)                                                    │
│    └─► Acumula `UsageMetadata` (suporta Turno Único ou Dual-Turn com Web Search)       │
│    └─► Emite evento SSE `done` ao cliente sem qualquer bloqueio de I/O contábil        │
│                                                                                        │
│ 3. Endpoint `/chat/completions/stream` + FastAPI `BackgroundTasks`                     │
│    └─► Despacha `record_token_usage_task(...)` em background após conclusão do stream  │
│    └─► CostEngine calcula USD (Numeric 14,8) e grava no PostgreSQL em sessão isolada   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1. Serviço Central de Precificação (`backend/app/services/cost_engine.py`)
Criação do módulo `CostEngine` contendo a tabela de tarifas por **1 Milhão de tokens (1M tokens)** de Entrada (*Input*) e Saída (*Output*) em USD, além de função de persistência assíncrona resiliente:

#### Tabela de Tarifação Oficial por 1M Tokens (USD)
| Provedor | ID Técnico / Alias | Custo Input / 1M (`USD`) | Custo Output / 1M (`USD`) |
| :--- | :--- | :---: | :---: |
| **OpenAI** | `gpt-5-2025-08-07` (`GPT-5 (OpenAI)`) | `$2.50` | `$10.00` |
| **Anthropic** | `claude-sonnet-4-6` (`Claude Sonnet 4.6`) | `$3.00` | `$15.00` |
| **Google Gemini** | `gemini-3.1-pro-preview` (`Gemini-3`) | `$1.25` | `$5.00` |
| **xAI** | `grok-4-1-fast-reasoning` (`grok-4`) | `$2.00` | `$10.00` |
| **Alibaba Qwen** | `qwen3.5-plus` (`Qwen3-Coder`) | `$0.80` | `$2.40` |

#### Fórmula de Cálculo (`Decimal` de Alta Precisão)
$$\text{total\_cost} = \left(\frac{\text{prompt\_tokens}}{1.000.000} \times \text{input\_price}\right) + \left(\frac{\text{completion\_tokens}}{1.000.000} \times \text{output\_price}\right)$$

- Utilização de `decimal.Decimal` com arredondamento `ROUND_HALF_UP` para `0.00000001` ($10^{-8}$ USD), garantindo precisão contábil absoluta.
- **Fallback de Estimativa de Tokens:** Caso algum provedor encerre a conexão abruptamente (ex: *AbortController* pelo usuário no meio da geração) antes de emitir o último chunk com o `usage` nativo, o `CostEngine` contará com um estimador determinístico de fallback ($\approx 4$ caracteres/token sobre o prompt efetivo + texto acumulado) para que até mesmo gerações interrompidas tenham seu consumo apropriado corretamente.

### 3.2. Interceptação Nativa nos Adaptadores (`backend/app/services/llm/`)
Definição de um dataclass tipado `UsageMetadata` em `backend/app/services/llm/base.py`:
```python
@dataclass
class UsageMetadata:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str
```
Atualização do tipo `StreamItem = Union[str, ToolCallRequest, UsageMetadata]` nos adaptadores:

1. **OpenAI (`openai_provider.py`), xAI (`xai_provider.py`) e Qwen (`qwen_provider.py`) via `_stream_openai_compatible` em `base.py`:**
   - Inclusão de `stream_options={"include_usage": True}` nos parâmetros de `client.chat.completions.create(...)`.
   - **Ajuste Crítico no Loop de Chunks (`base.py`):** No protocolo OpenAI-compatible, o último chunk contendo `chunk.usage` possui `chunk.choices = []`. O código atual faz `if not chunk.choices: continue` na linha 156, o que descartaria o chunk de telemetria. A inspeção será atualizada para interceptar `if getattr(chunk, "usage", None):` **antes** da verificação de `chunk.choices`, extraindo `chunk.usage.prompt_tokens` e `chunk.usage.completion_tokens`.
   - Ao final do generator `_stream_openai_compatible`, emite `yield UsageMetadata(...)`.

2. **Anthropic (`anthropic_provider.py`):**
   - No stream de eventos da `AsyncAnthropic`:
     - Intercepta o evento `chunk.type == "message_start"` para capturar `chunk.message.usage.input_tokens`.
     - Intercepta o evento final `chunk.type == "message_delta"` para capturar `chunk.usage.output_tokens`.
   - Ao encerrar o stream, emite `yield UsageMetadata(...)`.

3. **Google Gemini (`gemini_provider.py`):**
   - No `generate_content_stream` do SDK `google-genai`:
     - A cada chunk (consolidado no último chunk do stream), inspeciona `chunk.usage_metadata`, extraindo `prompt_token_count` e `candidates_token_count` (somando eventual `thoughts_token_count` caso aplicável).
   - Ao encerrar o stream, emite `yield UsageMetadata(...)`.

### 3.3. Consolidação Dual-Turn no `ChatOrchestrator` e Despacho via `BackgroundTasks`
1. **Acúmulo Multi-Turno (`backend/app/services/chat_orchestrator.py`):**
   - Quando uma pergunta aciona a ferramenta de busca na web (`search_web`), o `ChatOrchestrator` realiza **2 chamadas ao LLM** (Turno 1: decisão da tool call; Turno 2: síntese da resposta com o scraping da web).
   - O `stream_chat` interceptará os objetos `UsageMetadata` tanto do Turno 1 quanto do Turno 2, somando `total_prompt_tokens` e `total_completion_tokens`, e incluirá o objeto `usage` consolidado dentro do payload do evento final `done`.
2. **Despacho Assíncrono Não-Bloqueante (`backend/app/api/v1/endpoints/chat.py`):**
   - O endpoint `POST /api/v1/chat/completions/stream` receberá `background_tasks: BackgroundTasks` do FastAPI e o anexará ao `StreamingResponse(..., background=background_tasks)`.
   - Ao término do stream no `sse_event_generator`, o consumo capturado (ou estimado via fallback em caso de interrupção precoce) será agendado via:
     ```python
     background_tasks.add_task(
         record_token_usage_background,
         user_id=current_user.id,
         session_id=session_id,
         provider=resolved_provider,
         model_name=resolved_model_id,
         prompt_tokens=usage_data["prompt_tokens"],
         completion_tokens=usage_data["completion_tokens"]
     )
     ```
   - A task `record_token_usage_background` abrirá sua própria sessão `AsyncSessionLocal()` em background, calculará a tarifa via `CostEngine` e fará o `INSERT` na tabela `token_usage` **depois** que os chunks já foram entregues ao navegador.

---

## 4. Pilar 3: Endpoints de Monitoramento e Schemas (`metrics.py`)

### 4.1. Guard de Autorização Admin (`backend/app/api/deps.py`)
Criação da dependência de segurança `get_current_admin_user`:
- Recebe `current_user: User = Depends(get_current_active_user)`.
- Verifica se `current_user.role == "admin"`. Caso contrário, lança `HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores da plataforma.")`.

### 4.2. Schemas Pydantic (`backend/app/schemas/metrics.py`)
- `ModelUsageBreakdown`:
  - `provider: str`
  - `model_name: str`
  - `request_count: int`
  - `prompt_tokens: int`
  - `completion_tokens: int`
  - `total_tokens: int`
  - `total_cost_usd: float`
  - `percentage_of_cost: float`
- `UserUsageSummaryResponse` (retorno de `GET /api/v1/metrics/usage`):
  - `user_id: uuid.UUID`
  - `username: str`
  - `total_requests: int`
  - `total_prompt_tokens: int`
  - `total_completion_tokens: int`
  - `total_tokens: int`
  - `total_cost_usd: float`
  - `current_month_cost_usd: float`
  - `current_month_tokens: int`
  - `by_model: List[ModelUsageBreakdown]`
- `AdminUserRankingItem`:
  - `user_id: uuid.UUID`
  - `username: str`
  - `email: str`
  - `role: str`
  - `is_active: bool`
  - `request_count: int`
  - `total_tokens: int`
  - `total_cost_usd: float`
  - `current_month_cost_usd: float`
- `AdminUsageSummaryResponse` (retorno de `GET /api/v1/metrics/admin/usage`):
  - `total_platform_cost_usd: float`
  - `current_month_platform_cost_usd: float`
  - `total_platform_tokens: int`
  - `total_platform_requests: int`
  - `active_users_count: int`
  - `by_model: List[ModelUsageBreakdown]`
  - `user_ranking: List[AdminUserRankingItem]`

### 4.3. Rotas de Telemetria (`backend/app/api/v1/endpoints/metrics.py`)
Registradas em `backend/app/api/v1/router.py` sob o prefixo `/metrics` (`tags=["Metrics & Telemetry"]`):

| Método | Rota | Guard de Segurança | Comportamento e Queries SQL (SQLAlchemy Async) |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/metrics/usage` | `Depends(get_current_active_user)` | Executa agregação `SUM(prompt_tokens)`, `SUM(completion_tokens)`, `SUM(total_cost)` e `COUNT(id)` filtrando por `TokenUsage.user_id == current_user.id`. Calcula o recorte do mês atual (`created_at >= inicio_mes_utc`) e agrupa por `(provider, model_name)` ordenado por `total_cost DESC`. |
| `GET` | `/api/v1/metrics/admin/usage` | `Depends(get_current_admin_user)` | Executa agregação global da plataforma, agrupamento por modelo/provedor e `OUTER JOIN` entre `User` e `TokenUsage` agrupado por usuário e ordenado por `SUM(total_cost) DESC`, retornando o **Ranking de Consumo por Usuário**. |

---

## 5. Pilar 4: Painel Frontend (React + TypeScript + Zustand)

### 5.1. Tipagens e Cliente HTTP (`frontend/src/types/chat.ts` & `frontend/src/services/api.ts`)
- Adição das interfaces TypeScript `ModelUsageBreakdown`, `UserUsageSummaryResponse`, `AdminUserRankingItem` e `AdminUsageSummaryResponse` em `frontend/src/types/chat.ts`.
- Adição de dois métodos autenticados via `fetchWithAuth` no `apiService` (`frontend/src/services/api.ts`):
  - `getUserUsageMetrics(): Promise<UserUsageSummaryResponse>` (`GET /api/v1/metrics/usage`)
  - `getAdminUsageMetrics(): Promise<AdminUsageSummaryResponse>` (`GET /api/v1/metrics/admin/usage`)

### 5.2. Estado Global no Zustand (`frontend/src/store/useChatStore.ts`)
- Adição do controle de visibilidade do painel no `useChatStore`:
  - `isTelemetryOpen: boolean` (default `false`)
  - `setTelemetryOpen: (open: boolean) => void`

### 5.3. Componente Visual `TelemetryDashboard.tsx` (`frontend/src/components/telemetry/TelemetryDashboard.tsx`)
Modal/Dashboard amplo (`max-w-4xl`), responsivo e estilizado com o Design System Dark da aplicação (`bg-slate-900`, bordas `border-slate-800`, destaques em `indigo-500`, `emerald-400` e `amber-400`):

1. **Cabeçalho do Painel:**
   - Título **"Telemetria & Controle de Custos (FinOps)"**, botão de atualização manual (*Refresh*) com indicador de carregamento e seletor de abas:
     - **Aba "Meu Consumo"** (visível para todos os usuários).
     - **Aba "Visão Global & Ranking (Admin)"** (renderizada exclusivamente quando `user?.role === 'admin'`).
2. ** Linha de Cards de KPIs Financeiros (Topo):**
   - **Card 1 — Gasto no Mês Atual (USD):** Valor em destaque (ex: `$0.1482 USD`), badge indicando o mês/ano corrente e volume de tokens no mês.
   - **Card 2 — Custo Total Acumulado (USD):** Soma histórica da conta com precisão de até 4–6 casas decimais para fácil leitura de microcustos.
   - **Card 3 — Volume de Tokens Processados:** Total de tokens com divisão visual entre *Prompt Tokens (Input)* e *Completion Tokens (Output)* + total de requisições enviadas.
3. **Seção de Detalhamento por IA (5 Provedores):**
   - Lista interativa de cards/barras de proporção para cada modelo utilizado (`GPT-5`, `Claude Sonnet 4.6`, `Gemini-3`, `Grok-4`, `Qwen3-Coder`):
     - Badge colorido por provedor + número de chamadas.
     - Barra de progresso percentual indicando o peso daquele modelo no custo total do usuário.
     - Métricas detalhadas: `Input Tokens`, `Output Tokens` e `Custo ($ USD)`.
4. **Seção Exclusiva de Administração (`role === "admin"`):**
   - **KPIs Globais da Plataforma:** Custo Global Acumulado, Custo Global no Mês Atual, Total de Requisições e Usuários Ativos.
   - **Tabela de Ranking de Usuários:** Lista ordenada dos usuários que mais consomem na plataforma (Posição `#1, #2...`, Nome/E-mail, Role Badge, Requisições, Total de Tokens, Gasto no Mês e Custo Total em USD).

### 5.4. Acesso via `Sidebar.tsx` e Montagem em `App.tsx`
- Em `frontend/src/components/sidebar/Sidebar.tsx`: Adição do botão **"Telemetria & Custos"** (com ícone `BarChart3` / `DollarSign` do `lucide-react`) na seção inferior da barra lateral, logo acima do cartão de perfil do usuário.
- Em `frontend/src/App.tsx`: Inclusão do componente `<TelemetryDashboard />` ao lado do `<SettingsModal />`.

---

## 6. Matriz de Arquivos a Criar / Modificar (Após Aprovação)

| Camada | Arquivo | Ação | Responsabilidade |
| :--- | :--- | :---: | :--- |
| **Backend (Model)** | `backend/app/models/token_usage.py` | **Criar** | Entidade ORM `TokenUsage` (`user_id`, `session_id`, `provider`, `model_name`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `total_cost`, `created_at`). |
| **Backend (Models)** | `backend/app/models/user.py`, `session.py`, `__init__.py` | **Modificar** | Registro do relacionamento `token_usages` e exportação no `__all__`. |
| **Backend (Alembic)** | `backend/alembic/versions/003_add_token_usage_telemetry.py` | **Criar** | Migração criando a tabela `token_usage` e seus índices de performance. |
| **Backend (Service)** | `backend/app/services/cost_engine.py` | **Criar** | Dicionário de preços por 1M tokens dos 5 provedores, cálculo `Decimal` em USD e função assíncrona de persistência para `BackgroundTasks`. |
| **Backend (LLM)** | `backend/app/services/llm/base.py`, `anthropic_provider.py`, `gemini_provider.py` | **Modificar** | Interceptação das estatísticas nativas de uso no último chunk do stream e emissão de `UsageMetadata`. |
| **Backend (Orch.)** | `backend/app/services/chat_orchestrator.py` | **Modificar** | Acúmulo de tokens em chamadas simples e Dual-Turn (`search_web`) e repasse no evento `done`. |
| **Backend (API)** | `backend/app/api/v1/endpoints/chat.py` | **Modificar** | Despacho não-bloqueante da gravação de `TokenUsage` via FastAPI `BackgroundTasks`. |
| **Backend (Auth)** | `backend/app/api/deps.py` | **Modificar** | Adição da dependência `get_current_admin_user` (`role == "admin"`). |
| **Backend (Schemas)** | `backend/app/schemas/metrics.py` | **Criar** | Schemas Pydantic de resposta para métricas do usuário e ranking administrativo. |
| **Backend (API)** | `backend/app/api/v1/endpoints/metrics.py` e `router.py` | **Criar/Mod** | Endpoints `GET /api/v1/metrics/usage` e `GET /api/v1/metrics/admin/usage`. |
| **Frontend (Types/API)**| `frontend/src/types/chat.ts`, `frontend/src/services/api.ts` | **Modificar** | Tipagens de telemetria e métodos `getUserUsageMetrics` / `getAdminUsageMetrics`. |
| **Frontend (Store)** | `frontend/src/store/useChatStore.ts` | **Modificar** | Estado `isTelemetryOpen` e action `setTelemetryOpen`. |
| **Frontend (UI)** | `frontend/src/components/telemetry/TelemetryDashboard.tsx` | **Criar** | Painel visual com KPIs financeiros, detalhamento por IA, consumo mensal e aba Admin com ranking de usuários. |
| **Frontend (Layout)** | `frontend/src/components/sidebar/Sidebar.tsx`, `frontend/src/App.tsx` | **Modificar** | Botão de acesso na Sidebar e montagem global do modal `TelemetryDashboard`. |

---

## 7. Critérios de Validação e Aceite Técnico

- [ ] A migração `003_token_usage_telemetry` aplica-se sem erros via `alembic upgrade head` no container PostgreSQL.
- [ ] Chamadas de streaming para qualquer um dos 5 provedores (`GPT-5`, `Claude 4.6`, `Gemini 3.1`, `Grok-4`, `Qwen3`) persistem automaticamente um registro em `token_usage` via `BackgroundTasks` sem adicionar latência ao SSE.
- [ ] `GET /api/v1/metrics/usage` retorna exclusivamente os custos do usuário autenticado, detalhados por modelo e com recorte do mês atual.
- [ ] `GET /api/v1/metrics/admin/usage` bloqueia usuários comuns com `HTTP 403 Forbidden` e retorna o custo global + ranking de usuários para contas com `role="admin"`.
- [ ] O componente `TelemetryDashboard.tsx` abre a partir da `Sidebar`, exibindo os cards de custo total, consumo no mês atual, detalhamento por IA e visão administrativa.

---

> ⚠️ **Declaração de Conformidade Estrita:** Nenhum arquivo de código de produção foi alterado ou criado nesta etapa. O plano técnico acima aguarda sua revisão e aprovação para início da implementação.

