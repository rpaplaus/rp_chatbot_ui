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
  context_length?: number;
  prompt_price_per_1m?: number;
  completion_price_per_1m?: number;
  supports_tools?: boolean;
  is_free?: boolean;
  featured?: boolean;
}

export const DEFAULT_OPENROUTER_MODEL = 'openai/gpt-5';

export const LEGACY_MODEL_ID_MAP: Record<string, string> = {
  'GPT-5 (OpenAI)': 'openai/gpt-5',
  'gpt-5-2025-08-07': 'openai/gpt-5',
  'Claude Sonnet 4.6': 'anthropic/claude-sonnet-4.6',
  'claude-sonnet-4-6': 'anthropic/claude-sonnet-4.6',
  'Gemini-3': 'google/gemini-3.1-pro-preview',
  'gemini-3.1-pro-preview': 'google/gemini-3.1-pro-preview',
  'grok-4-1-fast-reasoning': 'x-ai/grok-4.6',
  'Qwen3-Coder': 'qwen/qwen3-coder',
  'qwen3.5-plus': 'qwen/qwen3-coder'
};

export const SUPPORTED_MODELS: ModelOption[] = [
  {
    id: 'openai/gpt-5',
    name: 'OpenAI: GPT-5',
    provider: 'openai',
    badge: 'OpenAI',
    description: 'Raciocínio avançado e arquitetura de software via OpenRouter',
    context_length: 400000,
    prompt_price_per_1m: 1.25,
    completion_price_per_1m: 10.0,
    supports_tools: true,
    is_free: false,
    featured: true
  },
  {
    id: 'anthropic/claude-sonnet-4.6',
    name: 'Anthropic: Claude Sonnet 4.6',
    provider: 'anthropic',
    badge: 'Anthropic',
    description: 'Excelência em engenharia de código e análise longa via OpenRouter',
    context_length: 200000,
    prompt_price_per_1m: 3.0,
    completion_price_per_1m: 15.0,
    supports_tools: true,
    is_free: false,
    featured: true
  },
  {
    id: 'google/gemini-3.1-pro-preview',
    name: 'Google: Gemini 3.1 Pro Preview',
    provider: 'google',
    badge: 'Google',
    description: 'Multimodal de alta velocidade e janela de contexto ampla via OpenRouter',
    context_length: 1048576,
    prompt_price_per_1m: 1.25,
    completion_price_per_1m: 5.0,
    supports_tools: true,
    is_free: false,
    featured: true
  },
  {
    id: 'x-ai/grok-4.6',
    name: 'xAI: Grok 4.6',
    provider: 'x-ai',
    badge: 'xAI',
    description: 'Raciocínio rápido em tempo real via OpenRouter',
    context_length: 256000,
    prompt_price_per_1m: 2.0,
    completion_price_per_1m: 10.0,
    supports_tools: true,
    is_free: false,
    featured: true
  },
  {
    id: 'qwen/qwen3-coder',
    name: 'Qwen: Qwen3 Coder',
    provider: 'qwen',
    badge: 'Qwen',
    description: 'Especialista em geração e refatoração de código via OpenRouter',
    context_length: 262144,
    prompt_price_per_1m: 0.8,
    completion_price_per_1m: 2.4,
    supports_tools: true,
    is_free: false,
    featured: true
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
  available_models: ModelOption[];
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


