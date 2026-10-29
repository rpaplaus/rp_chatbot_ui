import { Attachment, ChatProfileId, SearchSource, WebSearchMode } from '../types/chat';
import { fetchWithAuth } from './api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface SSECallbacks {
  onSearchStart?: (query: string) => void;
  onSources?: (sources: SearchSource[], query: string) => void;
  onChunk?: (text: string) => void;
  onDone?: (data: { model: string; provider: string; full_response: string }) => void;
  onPersisted?: (data: { message_id: string; session_id: string; created_at: string }) => void;
  onError?: (errorMessage: string) => void;
}

/**
 * Captura dinamicamente o fuso horário IANA e a data/hora local da máquina do cliente.
 */
function getClientTimeContext(): { client_timezone: string; client_local_time: string } {
  const now = new Date();
  let client_timezone = 'UTC';
  try {
    client_timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    client_timezone = 'UTC';
  }

  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const client_local_time = `${year}-${month}-${day} ${hours}:${minutes}`;

  return { client_timezone, client_local_time };
}

export async function streamChatCompletion(
  params: {
    sessionId: string;
    content: string;
    attachments?: Attachment[];
    modelName?: string;
    profileId?: ChatProfileId;
    systemPrompt?: string | null;
    webSearchMode?: WebSearchMode;
    signal?: AbortSignal;
  },
  callbacks: SSECallbacks
): Promise<void> {
  const { client_timezone, client_local_time } = getClientTimeContext();

  const response = await fetchWithAuth(`${API_BASE}/chat/completions/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    body: JSON.stringify({
      session_id: params.sessionId,
      message: {
        content: params.content,
        attachments: params.attachments && params.attachments.length > 0 ? params.attachments : undefined
      },
      model_name: params.modelName,
      profile_id: params.profileId || 'software_engineer',
      system_prompt: params.systemPrompt,
      web_search_mode: params.webSearchMode || 'auto',
      client_timezone,
      client_local_time
    }),
    signal: params.signal
  });

  if (!response.ok) {
    const errBody = await response.text();
    throw new Error(`Erro HTTP ${response.status}: ${errBody}`);
  }

  if (!response.body) {
    throw new Error('ReadableStream não suportado pelo navegador.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let currentEvent = 'message';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // Keep the last potentially incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) {
          continue;
        }

        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          const jsonStr = line.slice(5).trim();
          try {
            const payload = JSON.parse(jsonStr);

            switch (currentEvent) {
              case 'search_start':
                callbacks.onSearchStart?.(payload.query || '');
                break;
              case 'sources':
                callbacks.onSources?.(payload.sources || [], payload.query || '');
                break;
              case 'chunk':
                callbacks.onChunk?.(payload.text || '');
                break;
              case 'done':
                callbacks.onDone?.(payload);
                break;
              case 'persisted':
                callbacks.onPersisted?.(payload);
                break;
              case 'error':
                callbacks.onError?.(payload.message || 'Erro desconhecido no streaming.');
                break;
            }
          } catch (parseErr) {
            console.warn('Falha ao parsear evento SSE JSON:', jsonStr, parseErr);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
