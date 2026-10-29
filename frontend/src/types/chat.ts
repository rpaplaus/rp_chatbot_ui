export type WebSearchMode = 'auto' | 'always' | 'disabled';

export type ChatProfileId = 'software_engineer' | 'general_assistant';

export interface ChatProfileOption {
  id: ChatProfileId;
  name: string;
  shortLabel: string;
  description: string;
}

export const CHAT_PROFILES: ChatProfileOption[] = [
  {
    id: 'software_engineer',
    name: 'Engenheiro de Software',
    shortLabel: 'Dev / Stack',
    description: 'Foco em código, arquitetura e stack Python, FastAPI, React, Docker e PostgreSQL'
  },
  {
    id: 'general_assistant',
    name: 'Assistente Geral',
    shortLabel: 'Geral',
    description: 'Respostas diretas, concisas, utilidade geral e atualidades sem viés de código'
  }
];

export interface ModelOption {
  id: string;
  name: string;
  provider: string;
  badge: string;
  description: string;
}

export const SUPPORTED_MODELS: ModelOption[] = [
  {
    id: 'GPT-5 (OpenAI)',
    name: 'GPT-5 (OpenAI)',
    provider: 'openai',
    badge: 'OpenAI',
    description: 'Raciocínio avançado e arquitetura de software'
  },
  {
    id: 'Claude Sonnet 4.6',
    name: 'Claude Sonnet 4.6',
    provider: 'anthropic',
    badge: 'Anthropic',
    description: 'Excelência em engenharia de código e análise longa'
  },
  {
    id: 'Gemini-3',
    name: 'Gemini-3',
    provider: 'gemini',
    badge: 'Google',
    description: 'Multimodal de alta velocidade e janela de contexto ampla'
  },
  {
    id: 'grok-4-1-fast-reasoning',
    name: 'grok-4-1-fast-reasoning',
    provider: 'xai',
    badge: 'xAI',
    description: 'Raciocínio rápido em tempo real'
  },
  {
    id: 'Qwen3-Coder',
    name: 'Qwen3-Coder',
    provider: 'qwen',
    badge: 'Alibaba Qwen',
    description: 'Especialista em geração e refatoração de código'
  }
];

export interface SearchSource {
  index: number;
  title: string;
  url: string;
  snippet?: string;
}

export interface Attachment {
  file_id?: string;
  filename: string;
  type: string;
  content: string;
  size_bytes?: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata_json?: {
    model?: string;
    sources?: SearchSource[];
    attachments?: Attachment[];
  };
  created_at: string;
  isStreaming?: boolean;
  searchStatus?: {
    isSearching: boolean;
    query?: string;
  };
}

export interface ChatSession {
  id: string;
  title: string;
  system_prompt?: string | null;
  model_name: string;
  web_search_mode: WebSearchMode;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export interface FileUploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  parsed_content: string;
  saved_path: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  database: string;
  redis: string;
  active_providers: string[];
  available_models: Array<{ id: string; name: string; provider: string }>;
}

export interface ModelUsageBreakdown {
  provider: string;
  model_name: string;
  request_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  percentage_of_cost: number;
}

export interface UserUsageSummaryResponse {
  user_id: string;
  username: string;
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  current_month_cost_usd: number;
  current_month_tokens: number;
  by_model: ModelUsageBreakdown[];
}

export interface AdminUserRankingItem {
  user_id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  request_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  current_month_cost_usd: number;
}

export interface AdminUsageSummaryResponse {
  total_platform_cost_usd: number;
  current_month_platform_cost_usd: number;
  total_platform_tokens: number;
  total_platform_requests: number;
  active_users_count: number;
  by_model: ModelUsageBreakdown[];
  user_ranking: AdminUserRankingItem[];
}


