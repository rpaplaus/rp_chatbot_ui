import {
  AdminUsageSummaryResponse,
  ChatSession,
  FileUploadResponse,
  HealthResponse,
  UserUsageSummaryResponse,
  WebSearchMode
} from '../types/chat';
import { useAuthStore } from '../store/useAuthStore';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/**
 * Interceptor HTTP com injeção automática do JWT Access Token em memória
 * e Silent Refresh em background caso receba 401 Unauthorized.
 */
export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const { accessToken, refreshAccessToken, logout } = useAuthStore.getState();

  const headers = new Headers(options.headers || {});
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include'
  });

  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`);
      response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include'
      });
    } else {
      await logout();
      throw new Error('Sessão expirada. Faça login novamente.');
    }
  }

  return response;
}

export const apiService = {
  async checkHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Healthcheck failed: ${res.status}`);
    return res.json();
  },

  async listSessions(): Promise<ChatSession[]> {
    const res = await fetchWithAuth(`${API_BASE}/sessions`);
    if (!res.ok) throw new Error('Falha ao carregar sessões');
    return res.json();
  },

  async createSession(params?: {
    title?: string;
    model_name?: string;
    system_prompt?: string | null;
    web_search_mode?: WebSearchMode;
  }): Promise<ChatSession> {
    const res = await fetchWithAuth(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: params?.title || 'New Chat',
        model_name: params?.model_name || 'GPT-5 (OpenAI)',
        system_prompt: params?.system_prompt || null,
        web_search_mode: params?.web_search_mode || 'auto'
      })
    });
    if (!res.ok) throw new Error('Falha ao criar nova sessão');
    return res.json();
  },

  async getSessionDetails(sessionId: string): Promise<ChatSession> {
    const res = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}`);
    if (!res.ok) throw new Error('Falha ao buscar histórico da sessão');
    return res.json();
  },

  async updateSession(
    sessionId: string,
    data: {
      title?: string;
      model_name?: string;
      system_prompt?: string | null;
      web_search_mode?: WebSearchMode;
    }
  ): Promise<ChatSession> {
    const res = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Falha ao atualizar sessão');
    return res.json();
  },

  async deleteSession(sessionId: string): Promise<void> {
    const res = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Falha ao excluir sessão');
  },

  async clearSessionMessages(sessionId: string): Promise<void> {
    const res = await fetchWithAuth(`${API_BASE}/sessions/${sessionId}/messages`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Falha ao limpar mensagens da sessão');
  },

  async uploadFile(file: File): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetchWithAuth(`${API_BASE}/files/upload`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Falha no upload de ${file.name}: ${errText}`);
    }
    return res.json();
  },

  async generatePdf(params: {
    content: string;
    title?: string;
    model_name?: string;
  }): Promise<Blob> {
    const res = await fetchWithAuth(`${API_BASE}/tools/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Falha ao gerar PDF: ${errText}`);
    }
    return res.blob();
  },

  async getUserUsageMetrics(): Promise<UserUsageSummaryResponse> {
    const res = await fetchWithAuth(`${API_BASE}/metrics/usage`);
    if (!res.ok) {
      throw new Error('Falha ao carregar métricas de consumo do usuário');
    }
    return res.json();
  },

  async getAdminUsageMetrics(): Promise<AdminUsageSummaryResponse> {
    const res = await fetchWithAuth(`${API_BASE}/metrics/admin/usage`);
    if (!res.ok) {
      throw new Error('Falha ao carregar métricas administrativas da plataforma');
    }
    return res.json();
  }
};
