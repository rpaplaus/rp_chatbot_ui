# 📋 Plano de Ação - Fase 1: Infraestrutura Base

**Projeto:** RP_ChatBot (Migração de Gradio para Microsserviços)  
**Domínio de Produção:** `https://chat.rpaplaus.com` (Cloudflare Tunnels)  
**Fase Atual:** Fase 1 - Infraestrutura Base (PostgreSQL, Redis, Caddy e Networks)  
**Status:** ⏳ Aguardando Aprovação  

---

## 1. Objetivo da Fase 1
Estabelecer a fundação de infraestrutura conteinerizada para o ecossistema do RP_ChatBot através do `docker-compose.yml`, configurando serviços essenciais de persistência (PostgreSQL), cache/sessão em memória (Redis), gateway reverso de alta performance com suporte nativo a streaming SSE (Caddy) e topologia de redes Docker isoladas, garantindo conformidade com a rota do Cloudflare Tunnel e zero conflito de portas com os serviços já em execução no host.

---

## 2. Mapeamento de Portas e Prevenção de Conflitos

### 2.1. Portas Já em Uso no Host (Identificadas)
- **Projeto TVDE (app.tvdepilot.com):** `5173` (Frontend) e `8000` (Backend)
- **Projeto Latin Class (latin.dumai.com.br):** `3001` (Frontend) e `8001` (Backend)
- **Projeto CyberNexus (cybernexus.rpaplaus.com):** `5180` (Frontend) e `8090` (Backend)
- **Projeto Skysync (Host/Windows - skysync.dumai.com.br):** `3000` (Frontend/Swagger)

### 2.2. Portas Alocadas para o RP_ChatBot (Sem Conflitos)
| Serviço | Porta Interna (Container) | Porta Exposta no Host | Justificativa / Roteamento |
| :--- | :--- | :--- | :--- |
| **Caddy (Reverse Gateway)** | `80` | **`8085`** | Ponto de entrada local. O Cloudflare Tunnel (Tunnel 1 ou 2) apontará para `http://localhost:8085` para servir `chat.rpaplaus.com`. |
| **Backend (FastAPI)** | `8000` | **`8002`** | Porta dedicada. Acesso externo é roteado primariamente via Caddy (`/api/*`), mas a porta 8002 fica exposta para testes e inspeção OpenAPI. |
| **Frontend (React/Vite)** | `80` (Prod) / `5173` (Dev) | **`5185`** | Porta dedicada sem conflito com 5173, 5180, 3000 ou 3001. Acesso externo passa pelo Caddy. |
| **PostgreSQL 16** | `5432` | **`5435`** | Evita conflito com instâncias padrão do Postgres (5432/5433). Permite conexão direta via ferramentas locais (DBeaver, DataGrip). |
| **Redis 7** | `6379` | **`6382`** | Evita conflito com o Redis padrão (6379). Permite monitoramento via RedisInsight/CLI. |

---

## 3. Topologia de Redes e Integração com Cloudflare Tunnels

### 3.1. Rede Docker Dedicada
- Nome da rede: `rp_network` (driver `bridge`).
- Todos os containers do RP_ChatBot (`caddy`, `backend`, `frontend`, `postgres`, `redis`) comunicam-se através dos seus nomes de serviço via DNS interno do Docker.

### 3.2. Integração com Cloudflare Tunnels
- O ambiente possui dois túneis mapeados:
  - **Tunnel 1 (Windows Host):** ID `2214d956-3213-4e23-9875-ac997a3b24f0`
  - **Tunnel 2 (Docker):** ID `be96f739-328d-4072-a82d-c76d552498ca`
- **Estratégia de Ingress:**
  - Caso utilize o **Tunnel 1 (Host)**: O túnel direcionará o hostname `chat.rpaplaus.com` para `http://localhost:8085`.
  - Caso utilize o **Tunnel 2 (Docker)**: O container do Caddy poderá ingressar na rede externa do túnel Docker (`cloudflared`), ou o túnel acessará o Caddy via `http://rp_caddy:80`.
  - A porta `8085` no host garante funcionamento universal em ambas as abordagens.

---

## 4. Persistência de Dados e Volumes

Serão configurados volumes nomeados e bind mounts para garantir que nenhuma perda de estado ocorra na reinicialização dos containers:

1. **`rp_postgres_data`**: Volume gerenciado para os dados relacionais do PostgreSQL (tabelas de usuários, sessões, mensagens e metadados).
2. **`rp_redis_data`**: Volume gerenciado com persistência AOF/RDB habilitada para cache de streaming e estado efêmero.
3. **`rp_caddy_data` & `rp_caddy_config`**: Volumes para armazenar certificados e dados internos do Caddy.
4. **`./data/uploads`** (Bind mount): Diretório local no projeto para armazenamento temporário e persistente de anexos enviados para análise (PDFs, imagens, códigos).

---

## 5. Especificação do Caddy (`Caddyfile`)

O Caddy atuará como proxy reverso de alta performance. Como o chatbot depende de **Server-Sent Events (SSE)** para streaming de tokens dos 5 modelos de LLM, o Caddy será configurado explicitamente para desativar o buffering HTTP:

- **Roteamento de API e SSE:**
  - Requisições para `/api/*` serão encaminhadas para `backend:8000`.
  - Configuração de `flush_interval -1` para manter o fluxo de pacotes SSE em tempo real sem latência ou retenção em buffer.
- **Roteamento de Frontend:**
  - Requisições gerais (`/*`) serão encaminhadas para `frontend:80`.
- **Cabeçalhos de Segurança:**
  - Injeção de headers padrão (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).

---

## 6. Passo a Passo de Implementação da Fase 1

Após a aprovação deste plano, os seguintes passos técnicos serão executados:

1. **Criação da Estrutura de Diretórios de Infraestrutura:**
   - Criar diretório `infra/caddy/` para o `Caddyfile`.
   - Criar diretório `data/uploads/` para armazenamento de arquivos e adicionar ao `.gitignore`.
2. **Criação do `infra/caddy/Caddyfile`:**
   - Configuração de listeners para a porta interna 80 (mapeada em 8085).
   - Regras de proxy reverso separando tráfego de API (`backend:8000`) e SPA (`frontend:80`).
   - Diretiva de desativação de buffering para SSE.
3. **Criação do Novo `docker-compose.yml`:**
   - Definição dos serviços `caddy`, `postgres` e `redis`.
   - Inclusão dos placeholders com profiles para `backend` e `frontend` (para orquestração completa futura).
   - Configuração de healthchecks para o Postgres (`pg_isready -U postgres`) e Redis (`redis-cli ping`).
   - Mapeamento explícito de portas no host (`8085`, `5435`, `6382`).
4. **Atualização do `.env.example` e `.env`:**
   - Adição de variáveis de infraestrutura:
     - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT=5435`
     - `REDIS_PASSWORD`, `REDIS_PORT=6382`
     - `CADDY_PORT=8085`
     - `BACKEND_PORT=8002`
     - `FRONTEND_PORT=5185`
5. **Atualização do `.gitignore`:**
   - Garantir exclusão de diretórios de dados locais, logs e arquivos de ambiente sensíveis.

---

## 7. Critérios de Validação e Aceite da Fase 1

A fase será considerada concluída com sucesso quando:
- [ ] Arquivos `docker-compose.yml`, `infra/caddy/Caddyfile` e `.env` atualizados forem gerados com sucesso.
- [ ] O `docker-compose.yml` for validado sintaticamente sem conflitos de portas.
- [ ] O arquivo `relatorio_fase_1.md` for gerado, documentando toda a infraestrutura pronta para a Fase 2 (Fundação do Backend).

---

> ⚠️ **Aviso:** Conforme as diretrizes rígidas de execução, **nenhum código ou arquivo de serviço foi alterado ou criado**. Aguardo sua autorização formal para iniciar a execução da Fase 1.

