# 🔐 Plano de Ação - Fase 4.5 (Fase de Segurança): Autenticação Next-Gen & Isolamento Multi-Tenant

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 4.5 - Segurança, Autenticação JWT + HttpOnly Refresh Rotation & Multi-Tenancy  
**Status:** ⏳ Aguardando Aprovação Formal  

---

## 1. Objetivo da Fase de Segurança
Blindar todos os endpoints de consumo de LLMs, upload de arquivos e histórico de conversas contra acessos não autorizados, implementando uma arquitetura de autenticação **Zero-Trust / Whitelist-Only** com isolamento de dados por usuário (*Multi-Tenant*), tokens JWT de curta duração em memória e *Refresh Tokens* rotacionados em cookies `HttpOnly` + `Secure` gerenciados no Redis.

---

## 2. Pilar 1: Modelagem de Dados e Isolamento Multi-Tenant (PostgreSQL & SQLAlchemy)

### 2.1. Nova Entidade `User` (`backend/app/models/user.py`)
Tabela `users` no PostgreSQL:
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`, indexado)
- `email`: `VARCHAR(255)` (`unique=True`, `index=True`, `nullable=False`)
- `username`: `VARCHAR(100)` (`unique=True`, `index=True`, `nullable=False` — permite login por e-mail ou username)
- `hashed_password`: `VARCHAR(255)` (`nullable=False` — hash criptográfico via `pwdlib` / `bcrypt`)
- `is_active`: `BOOLEAN` (`default=True`, `nullable=False`)
- `role`: `VARCHAR(30)` (`default="user"`, valores: `"admin"` | `"user"`)
- `created_at` / `updated_at`: `TIMESTAMPTZ` (Auditoria automática via `TimestampMixin`)
- `sessions`: Relacionamento `1:N` com `ChatSession` (`cascade="all, delete-orphan"`)

### 2.2. Vínculo Obrigatório em `ChatSession` (`backend/app/models/session.py`)
Atualização da tabela `sessions` para garantir isolamento estrito entre usuários:
- `user_id`: `UUID` (`ForeignKey("users.id", ondelete="CASCADE")`, `nullable=False`, `index=True`)
- `user`: Relacionamento reverso `Mapped["User"]`

### 2.3. Migração Alembic (`002_add_users_and_tenant_isolation.py`)
1. Criação da tabela `users` com índices únicos para `email` e `username`.
2. Criação automática do usuário administrador inicial (a partir de `APP_USER` e `APP_PASSWORD` do `.env`) caso ainda não exista.
3. Adição da coluna `user_id` na tabela `sessions`, associando eventuais sessões legadas existentes ao administrador inicial antes de aplicar a constraint `NOT NULL` e a chave estrangeira `ON DELETE CASCADE`.

---

## 3. Pilar 2: Arquitetura de Autenticação Backend (JWT + HttpOnly Refresh Rotation)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                   Fluxo Dual-Token (XSS & CSRF Resilient)                  │
├──────────────────────────────────────┬─────────────────────────────────────┤
│ Access Token (JWT - 15 min)          │ Refresh Token (JWT - 7 dias)        │
├──────────────────────────────────────┼─────────────────────────────────────┤
│ • Armazenado APENAS em RAM (Zustand) │ • Armazenado em Cookie HttpOnly     │
│ • Enviado via Header Authorization   │ • Flags: HttpOnly, Secure, SameSite │
│ • Imune a CSRF                       │ • Path restrito: /api/v1/auth       │
│ • Se a aba fechar, renova via Cookie │ • JTI rastreado e rotacionado Redis │
└──────────────────────────────────────┴─────────────────────────────────────┘
```

### 3.1. Especificação Criptográfica (`backend/app/core/security.py`)
- **Hashing de Senhas:** Algoritmo **Bcrypt** com salt aleatório por senha.
- **Access Token (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`):**
  - Payload: `{"sub": str(user.id), "username": user.username, "role": user.role, "type": "access", "exp": ...}`
- **Refresh Token (`REFRESH_TOKEN_EXPIRE_DAYS = 7`):**
  - Payload: `{"sub": str(user.id), "jti": str(uuid4()), "type": "refresh", "exp": ...}`
  - **Controle de Estado no Redis:** A cada emissão de `refresh_token`, a chave `auth:refresh:{user_id}:{jti}` é gravada no Redis com TTL de 7 dias.
  - **Rotação Estrita:** Quando `/api/v1/auth/refresh` é chamado, o `jti` utilizado é imediatamente invalidado/deletado do Redis e um novo par (`access_token` + `refresh_token` com novo `jti`) é emitido.

### 3.2. Endpoints de Autenticação (`backend/app/api/v1/endpoints/auth.py`)
| Método | Rota | Descrição Técnica |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Valida credenciais (`username`/`email` + `password`). Retorna `access_token` + `user` no body e define o cookie `rp_refresh_token` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/api/v1/auth`). |
| `POST` | `/api/v1/auth/refresh` | Lê o cookie `rp_refresh_token`, verifica o `jti` no Redis, rotaciona o cookie com novo `jti` e devolve um novo `access_token`. |
| `POST` | `/api/v1/auth/logout` | Remove o `jti` do Redis e limpa o cookie `rp_refresh_token` no navegador. |
| `GET` | `/api/v1/auth/me` | Retorna os dados cadastrais do usuário autenticado via `Depends(get_current_active_user)`. |

---

## 4. Pilar 3: Controle de Acesso Fechado (Whitelist & CLI Administrativo)

1. **Ausência Total de Registro Público:** Não existirá rota pública de criação de conta (`signup`).
2. **Seed Automático de Admin no Boot:** No startup da aplicação (`lifespan` / migração), o usuário definido em `APP_USER` (ex: `rpaplaus`) e `APP_PASSWORD` no `.env` é provisionado automaticamente como `role="admin"`.
3. **Utilitário CLI Administrativo (`backend/manage_users.py`):**
   Ferramenta de linha de comando para gestão da Whitelist diretamente via terminal do host/Docker:
   - Criar usuário: `docker exec rp_backend python manage_users.py create --username nome --email user@dominio.com --password SenhaForte --role user`
   - Listar usuários: `docker exec rp_backend python manage_users.py list`
   - Desativar/Ativar acesso: `docker exec rp_backend python manage_users.py toggle-status --username nome`
   - Alterar senha: `docker exec rp_backend python manage_users.py reset-password --username nome --password NovaSenha`

---

## 5. Pilar 4: Proteção de Rotas e Escopo Multi-Tenant (`deps.py`)

Todas as rotas de negócio receberão a dependência `current_user: User = Depends(get_current_active_user)`:

1. **Proteção de `/api/v1/sessions` (`sessions.py`):**
   - `GET /sessions`: Filtra `WHERE sessions.user_id == current_user.id`.
   - `POST /sessions`: Grava `user_id = current_user.id`.
   - `GET / PATCH / DELETE /sessions/{session_id}`: Filtra `WHERE sessions.id == session_id AND sessions.user_id == current_user.id` (retorna `404 Not Found` caso pertença a outro tenant).
2. **Proteção de `/api/v1/chat/completions/stream` (`chat.py`):**
   - Exige token JWT válido no header `Authorization: Bearer <token>`.
   - Verifica se a `session_id` pertence ao `current_user.id` antes de abrir conexão com qualquer provedor de LLM (OpenAI, Anthropic, Gemini, xAI, Qwen).
3. **Proteção de `/api/v1/files/upload` (`files.py`):**
   - Exige `Depends(get_current_active_user)` para permitir upload e parsing de documentos.

---

## 6. Pilar 5: Integração Frontend (React + TypeScript + Zustand)

### 6.1. Gestão de Estado de Autenticação (`frontend/src/store/useAuthStore.ts`)
- Armazena `accessToken: string | null` **exclusivamente em memória RAM** (não utiliza `localStorage` nem `sessionStorage`, neutralizando exfiltração de tokens por scripts terceiros).
- Armazena `user: UserProfile | null`, `isAuthenticated: boolean`, `isInitializing: boolean`.
- **Hidratação Silenciosa no Boot (`initializeAuth`):** Ao abrir ou recarregar a página (F5), chama `POST /api/v1/auth/refresh` enviando o cookie `HttpOnly` automaticamente (`credentials: 'include'`). Se válido, restaura o `accessToken` em memória e libera o acesso à SPA sem pedir login novamente.

### 6.2. Interceptor HTTP e SSE com Silent Refresh (`api.ts` & `sse.ts`)
- Wrapper centralizado `fetchWithAuth(url, options)`:
  1. Anexa automaticamente `Authorization: Bearer ${accessToken}` e `credentials: 'include'`.
  2. Se a resposta for `401 Unauthorized`, pausa a requisição, invoca `refreshAccessToken()` uma única vez (com *mutex/lock* para evitar múltiplas chamadas simultâneas de refresh) e, obtendo o novo token, **repete a requisição original de forma transparente** (inclusive no streaming SSE).
  3. Se a renovação falhar (sessão expirada ou revogada), limpa o estado e exibe a tela de Login.

### 6.3. Componentes Visuais de Autenticação
- **`frontend/src/components/auth/LoginPage.tsx`:**
  - Tela de login elegante seguindo o Design System Dark (`slate-950`, detalhes em `indigo-500/600`), com campos de Usuário/E-mail e Senha, botão de visualizar senha, feedback de erro claro e aviso de **"Ambiente Privado — Acesso Restrito a Usuários Autorizados"**.
- **`frontend/src/components/auth/AuthGuard.tsx`:**
  - Protege a árvore principal (`App.tsx`). Enquanto `isInitializing` for `true`, exibe tela de carregamento; se `!isAuthenticated`, renderiza `LoginPage`; se autenticado, renderiza o workspace do chatbot.
- **Rodapé de Perfil na `Sidebar.tsx`:**
  - Exibe avatar, nome/e-mail do usuário autenticado, badge de role (`ADMIN` / `USER`) e botão de **Logout** seguro.

---

## 7. Passo a Passo de Execução da Fase 4.5 (Após Aprovação)

1. **Dependências e Segurança Backend:**
   - Adicionar `bcrypt` e `PyJWT` (já instalado no ambiente) em `backend/requirements.txt`.
   - Criar `backend/app/core/security.py` (hash de senha, geração/validação de JWT e gestão de `jti` no Redis).
2. **Modelagem e Migração Alembic:**
   - Criar `backend/app/models/user.py` e atualizar `backend/app/models/session.py` + `backend/app/models/__init__.py`.
   - Criar `backend/app/schemas/auth.py` (`LoginRequest`, `TokenResponse`, `UserResponse`).
   - Criar migração `backend/alembic/versions/002_add_users_and_tenant_isolation.py`.
3. **Endpoints de Auth, Guards e CLI:**
   - Criar `backend/app/api/v1/endpoints/auth.py` (`/login`, `/refresh`, `/logout`, `/me`).
   - Atualizar `backend/app/api/deps.py` com `get_current_active_user`.
   - Proteger `sessions.py`, `chat.py` e `files.py` com `Depends(get_current_active_user)` e filtro `user_id`.
   - Criar `backend/manage_users.py` (CLI administrativo para gerir a whitelist).
4. **Implementação no Frontend:**
   - Criar `frontend/src/store/useAuthStore.ts`.
   - Atualizar `frontend/src/services/api.ts` e `frontend/src/services/sse.ts` com `fetchWithAuth` e *Silent Refresh*.
   - Criar `frontend/src/components/auth/LoginPage.tsx` e `AuthGuard.tsx`.
   - Atualizar `Sidebar.tsx` e `App.tsx` com informações do usuário e botão de Logout.
5. **Testes Automatizados e Rebuild Docker:**
   - Criar e rodar `backend/test_auth_flow.py` validando: bloqueio `401` sem token, login com sucesso, cookie `HttpOnly`, rotação de refresh token, isolamento multi-tenant entre usuários e logout.
   - Fazer rebuild de `rp_backend` e `rp_frontend` e gerar `relatorio_autenticacao.md`.

---

## 8. Critérios de Validação e Aceite

- [ ] Requisições para `/api/v1/sessions`, `/api/v1/files/upload` e `/api/v1/chat/completions/stream` sem token válido são imediatamente rejeitadas com `HTTP 401 Unauthorized`.
- [ ] Login via `/api/v1/auth/login` retorna `access_token` e configura o cookie `rp_refresh_token` com as flags `HttpOnly` e `SameSite=Lax`.
- [ ] O endpoint `/api/v1/auth/refresh` rotaciona o token no Redis e invalida o token anterior.
- [ ] Usuários distintos possuem isolamento total de suas conversas no PostgreSQL.
- [ ] O CLI `manage_users.py` permite criar, listar e desativar usuários da whitelist.
- [ ] A SPA exibe a tela de Login quando não autenticada e renova a sessão silenciosamente ao recarregar a página.

---

> ⚠️ **Aviso de Conformidade:** Seguindo rigorosamente a diretriz de execução, **nenhum arquivo de código foi modificado ou criado**. Aguardo sua aprovação formal deste plano para iniciar a implementação técnica da Fase de Segurança (Fase 4.5).

