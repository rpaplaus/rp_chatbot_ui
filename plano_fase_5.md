# 📋 Plano de Ação - Fase 5: Frontend SPA (Next-Gen UI em React, TypeScript & Vite)

**Projeto:** RP_ChatBot  
**Domínio de Produção:** `https://chat.rpaplaus.com`  
**Fase Atual:** Fase 5 - Frontend SPA (Next-Gen UI)  
**Status:** ⏳ Aguardando Aprovação Formal  

---

## 1. Objetivo da Fase 5
Construir a interface web definitiva do **RP_ChatBot** como uma Single Page Application (SPA) moderna, responsiva (*mobile-first*), acessível e de alta performance em `frontend/`, substituindo integralmente a antiga interface Gradio e conectando-se aos endpoints REST e Server-Sent Events (SSE) construídos na Fase 4.

---

## 2. Stack Tecnológica e Bibliotecas

| Categoria | Tecnologia / Biblioteca | Justificativa Técnica |
| :--- | :--- | :--- |
| **Core & Build** | **React 18 + TypeScript + Vite** | Tipagem estrita ponta a ponta, HMR instantâneo e bundle de produção altamente otimizado com *tree-shaking*. |
| **Estilização & UI** | **Tailwind CSS + Lucide Icons + Radix UI / Shadcn Pattern** | Design system moderno (Dark Mode nativo voltado para programadores), componentes acessíveis (WAI-ARIA) e responsividade fluida. |
| **Gestão de Estado** | **Zustand** | Store global leve e performático para gerenciar sessões, mensagens em streaming, modelo ativo, configurações e fila de anexos sem re-renders desnecessários. |
| **Renderização Markdown & Código** | **`react-markdown` + `remark-gfm` + `rehype-highlight` (`highlight.js`)** | Suporte completo a GitHub Flavored Markdown (tabelas, listas de tarefas), sanitização nativa contra XSS (sem `dangerouslySetInnerHTML`) e syntax highlighting com botão de "Copiar Código". |
| **Streaming SSE** | **Fetch ReadableStream + `AbortController` (`@microsoft/fetch-event-source` pattern)** | Suporte a requisições `POST` com payload JSON para SSE, reconexão controlada, parsing linha a linha de eventos (`search_start`, `sources`, `chunk`, `done`, `persisted`, `error`) e botão de cancelamento de geração em tempo real. |

---

## 3. Estrutura de Diretórios do Frontend (`frontend/`)

```
frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                         # Entrypoint React 18
│   ├── App.tsx                          # Layout principal responsivo (Sidebar + Main Chat Area)
│   ├── index.css                        # Diretivas Tailwind CSS, variáveis de tema e estilos de scrollbar/código
│   ├── types/
│   │   └── chat.ts                      # Interfaces TypeScript espelhando os schemas Pydantic do Backend
│   ├── services/
│   │   ├── api.ts                       # Cliente REST (Sessões, Healthcheck, Upload Multipart)
│   │   └── sse.ts                       # Cliente de Streaming SSE com AbortController e parser de eventos
│   ├── store/
│   │   └── useChatStore.ts              # Store Zustand (estado de sessões, mensagens, streaming, configurações)
│   └── components/
│       ├── sidebar/
│       │   ├── Sidebar.tsx              # Sidebar retrátil (Drawer no mobile, painel fixo/colapsável no desktop)
│       │   └── SessionItem.tsx          # Item de sessão com ações de renomear inline e excluir
│       ├── header/
│       │   ├── Header.tsx               # Barra superior: Seletor de Modelos, Status da API, Web Search Mode
│       │   └── SettingsModal.tsx        # Modal/Drawer para edição do System Prompt e limpeza de conversa
│       └── chat/
│           ├── ChatArea.tsx             # Lista de mensagens com auto-scroll inteligente e tela de boas-vindas
│           ├── MessageBubble.tsx        # Renderização de mensagem (User/Assistant), avatar, timestamp e ações
│           ├── MarkdownRenderer.tsx     # Renderizador GFM com cabeçalho de linguagem e cópia de código
│           ├── SearchIndicator.tsx      # Estado animado "Pesquisando na web por..." e cards/chips de fontes
│           └── ChatInput.tsx            # Textarea auto-ajustável, upload de múltiplos arquivos, chips de preview
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── nginx.conf                           # Configuração Nginx de produção com SPA fallback e headers CSP
└── Dockerfile                           # Build Multi-Stage (Node 20 Alpine -> Nginx Stable Alpine)
```

---

## 4. Arquitetura Visual, UX e Responsividade (Mobile-First)

### 4.1. Sidebar Retrátil de Sessões (`Sidebar.tsx`)
- **Desktop (`md:` e superior):** Painel lateral esquerdo de `280px` com transição suave para colapsar/expandir.
- **Mobile (`< 768px`):** Menu gaveta (*Off-canvas Drawer*) com *backdrop blur* acionado pelo botão hambúrguer no topo.
- **Funcionalidades:**
  - Botão de destaque **"➕ Nova Conversa"**.
  - Filtro rápido de busca por título de conversa.
  - Edição rápida do título da conversa (*inline rename*) via `PATCH /api/v1/sessions/{id}`.
  - Exclusão de conversa com confirmação via `DELETE /api/v1/sessions/{id}`.

### 4.2. Header e Controle de Parâmetros (`Header.tsx` & `SettingsModal.tsx`)
- **Seletor Visual de Modelos:** Dropdown customizado exibindo os 5 modelos homologados com badges do provedor:
  - `GPT-5 (OpenAI)` — Badge OpenAI
  - `Claude Sonnet 4.6` — Badge Anthropic
  - `Gemini-3` — Badge Google
  - `grok-4-1-fast-reasoning` — Badge xAI
  - `Qwen3-Coder` — Badge Alibaba Qwen
- **Seletor de Busca Web (Internet):** Controle rápido segmentado entre:
  - `🔍 Ask` (Heurística inteligente)
  - `⚡ Auto` (Força busca em tempo real)
  - `🚫 Off` (Apenas conhecimento prévio do modelo)
- **System Prompt & Configurações:** Botão que abre painel de instruções de sistema personalizadas para a sessão atual e opção de limpar mensagens (`DELETE /api/v1/sessions/{id}/messages`).

### 4.3. Área de Conversação e Componentes Ricos (`ChatArea.tsx` & `MessageBubble.tsx`)
- **Empty State Interativo:** Quando uma sessão está vazia, exibe cartões de sugestão rápida para tarefas de programação, arquitetura, debugging e pesquisa em tempo real.
- **Indicador de Pesquisa em Tempo Real (`SearchIndicator.tsx`):**
  - Ao receber `event: search_start`, exibe um card pulsante: *"🔎 Pesquisando na web por: '{query}'..."*.
  - Ao receber `event: sources`, transforma o indicador em uma grade horizontal de **Source Chips/Cards clicáveis** com título numerado, domínio e link seguro (`target="_blank" rel="noopener noreferrer"`).
- **Renderização de Código Profissional (`MarkdownRenderer.tsx`):**
  - Blocos de código com barra superior indicando a linguagem (`python`, `typescript`, `sql`, `bash`, etc.) e botão **"Copiar"** com feedback visual de confirmação.
- **Barra de Entrada Multimodal (`ChatInput.tsx`):**
  - Suporte a envio com `Enter` (e quebra de linha com `Shift + Enter`).
  - Botão de anexo e *Drag & Drop* para `.pdf`, `.txt`, `.py`, `.js`, `.ts`, `.md`, `.csv`, `.json`, `.jpg`, `.png`, `.mp3`.
  - Upload imediato via `POST /api/v1/files/upload` com indicador de progresso individual por arquivo e exibição de *chips* com nome, tipo e tamanho antes do envio da mensagem.

---

## 5. Consumo do Streaming SSE e Gestão de Estado

O cliente SSE (`src/services/sse.ts`) operará integrado ao store Zustand (`useChatStore.ts`):

```
[Usuário envia mensagem]
   │
   ├── 1. UI Otimista: Adiciona imediatamente a mensagem do usuário e um placeholder do assistente na tela.
   │
   ├── 2. Conexão SSE: Dispara POST /api/v1/chat/completions/stream com ReadableStream reader.
   │
   ├── 3. Processamento de Eventos:
   │      • event: search_start -> Atualiza status da mensagem para "searching" com a query.
   │      • event: sources      -> Anexa o array de fontes consultadas ao objeto da mensagem.
   │      • event: chunk        -> Concatena o token recebido no conteúdo da mensagem em tempo real.
   │      • event: persisted    -> Sincroniza o UUID definitivo gerado pelo PostgreSQL e recarrega a lista de sessões (caso o título tenha sido auto-gerado).
   │      • event: error        -> Exibe alerta visual de erro sem perder o texto já recebido.
   │
   └── 4. Controle de Interrupção: Botão "Parar Geração" aciona AbortController.abort(), encerrando o stream limpidamente.
```

---

## 6. Segurança, Nginx e Multi-Stage Docker Build

### 6.1. `frontend/nginx.conf`
- Escuta na porta `80` interna do container.
- Fallback de roteamento SPA (`try_files $uri $uri/ /index.html;`).
- Compressão `gzip` ativada para `.js`, `.css`, `.json`, `.svg`.
- **Cabeçalhos de Segurança:**
  - `Content-Security-Policy`: Restringe origens de scripts e conexões (`default-src 'self'; connect-src 'self' https://chat.rpaplaus.com http://localhost:*; img-src 'self' data: https:; style-src 'self' 'unsafe-inline';`).
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`

### 6.2. `frontend/Dockerfile`
1. **Estágio 1 (`builder`):** Imagem `node:20-alpine`, instala pacotes via `npm install`, compila TypeScript e gera o bundle estático de produção com `npm run build`.
2. **Estágio 2 (`runner`):** Imagem `nginx:1.27-alpine`, copia apenas os artefatos compilados de `/app/dist` para `/usr/share/nginx/html` e aplica o `nginx.conf` customizado.

---

## 7. Passo a Passo de Execução da Fase 5 (Após Aprovação)

1. **Configuração do Projeto Vite + React + TypeScript + Tailwind:**
   - Criar `package.json`, `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`, `postcss.config.js` e `index.html`.
2. **Definição de Tipos e Camada de Serviços (`src/types/` e `src/services/`):**
   - Criar `chat.ts` com contratos tipados.
   - Criar `api.ts` (cliente REST para sessões, health e upload).
   - Criar `sse.ts` (cliente de streaming SSE com parser de eventos e `AbortController`).
3. **Implementação da Store Global (`src/store/useChatStore.ts`):**
   - Gerenciamento reativo de sessões, histórico, anexos, parâmetros e streaming.
4. **Construção dos Componentes Visuais (`src/components/`):**
   - `Sidebar.tsx`, `SessionItem.tsx`, `Header.tsx`, `SettingsModal.tsx`.
   - `ChatArea.tsx`, `MessageBubble.tsx`, `MarkdownRenderer.tsx`, `SearchIndicator.tsx`, `ChatInput.tsx`.
5. **Configuração de Produção e Containerização:**
   - Criar `frontend/nginx.conf`.
   - Atualizar `frontend/Dockerfile` com build multi-stage real.
6. **Build, Deploy e Validação Integrada:**
   - Executar `docker compose up -d --build frontend` para compilar e subir o container `rp_frontend`.
   - Validar o carregamento da SPA e a comunicação ponta a ponta através do gateway Caddy (`http://localhost:8085`).

---

## 8. Critérios de Validação e Aceite da Fase 5

A Fase 5 (e a migração completa do projeto) será considerada concluída quando:
- [ ] O build multi-stage do `rp_frontend` compilar sem erros de TypeScript ou bundle.
- [ ] O container `rp_frontend` subir saudável na rede `rp_network` e responder na porta `5185` (direta) e `8085` (via Caddy).
- [ ] A SPA carregar com todos os assets (JS/CSS) e headers de segurança configurados no Nginx.
- [ ] A integração completa (Frontend -> Caddy -> Backend FastAPI -> PostgreSQL/Redis/LLMs) estiver validada.
- [ ] O arquivo `relatorio_fase_5.md` for gerado documentando a entrega final da arquitetura de microsserviços.

---

> ⚠️ **Aviso de Conformidade:** Seguindo estritamente a diretriz rígida de execução, **nenhum arquivo de código foi alterado ou criado**. Aguardo sua aprovação formal deste plano para iniciar a implementação da Fase 5.

