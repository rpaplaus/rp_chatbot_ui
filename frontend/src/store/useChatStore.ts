import { create } from 'zustand';
import {
  Attachment,
  ChatMessage,
  ChatProfileId,
  ChatSession,
  DEFAULT_OPENROUTER_MODEL,
  HealthResponse,
  LEGACY_MODEL_ID_MAP,
  ModelOption,
  SUPPORTED_MODELS,
  WebSearchMode
} from '../types/chat';
import { apiService } from '../services/api';
import { streamChatCompletion } from '../services/sse';

function normalizeModelId(modelName?: string | null): string {
  if (!modelName) return DEFAULT_OPENROUTER_MODEL;
  const trimmed = modelName.trim();
  return LEGACY_MODEL_ID_MAP[trimmed] || trimmed;
}

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  availableModels: ModelOption[];
  selectedModel: string;
  activeProfile: ChatProfileId;
  systemPrompt: string;
  webSearchMode: WebSearchMode;
  pendingAttachments: Attachment[];
  isUploading: boolean;
  isStreaming: boolean;
  isLoadingSessions: boolean;
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  isTelemetryOpen: boolean;
  health: HealthResponse | null;
  error: string | null;
  abortController: AbortController | null;

  // Actions
  initApp: () => Promise<void>;
  refreshHealth: () => Promise<void>;
  refreshModels: (force?: boolean) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  createNewSession: () => Promise<void>;
  renameSession: (sessionId: string, newTitle: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  clearCurrentChat: () => Promise<void>;
  setModel: (modelName: string) => Promise<void>;
  setActiveProfile: (profile: ChatProfileId) => void;
  setWebSearchMode: (mode: WebSearchMode) => Promise<void>;
  setSystemPrompt: (prompt: string) => Promise<void>;
  uploadFiles: (files: FileList | File[]) => Promise<void>;
  removeAttachment: (index: number) => void;
  sendMessage: (content: string) => Promise<void>;
  stopStreaming: () => void;
  setSidebarOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setTelemetryOpen: (open: boolean) => void;
  clearError: () => void;
  resetChatState: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  availableModels: SUPPORTED_MODELS,
  selectedModel: DEFAULT_OPENROUTER_MODEL,
  activeProfile: 'software_engineer',
  systemPrompt: '',
  webSearchMode: 'auto',
  pendingAttachments: [],
  isUploading: false,
  isStreaming: false,
  isLoadingSessions: false,
  isSidebarOpen: typeof window !== 'undefined' ? window.innerWidth >= 768 : true,
  isSettingsOpen: false,
  isTelemetryOpen: false,
  health: null,
  error: null,
  abortController: null,

  initApp: async () => {
    set({ isLoadingSessions: true, error: null });
    try {
      const [healthData, sessionsList] = await Promise.all([
        apiService.checkHealth().catch(() => null),
        apiService.listSessions()
      ]);

      const catalogModels =
        healthData?.available_models && healthData.available_models.length > 0
          ? healthData.available_models
          : SUPPORTED_MODELS;

      set({
        health: healthData,
        availableModels: catalogModels,
        sessions: sessionsList
      });

      if (sessionsList.length > 0) {
        await get().selectSession(sessionsList[0].id);
      } else {
        await get().createNewSession();
      }
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao inicializar aplicação' });
    } finally {
      set({ isLoadingSessions: false });
    }
  },

  refreshHealth: async () => {
    try {
      const healthData = await apiService.checkHealth();
      set((state) => ({
        health: healthData,
        availableModels:
          healthData.available_models && healthData.available_models.length > 0
            ? healthData.available_models
            : state.availableModels
      }));
    } catch {
      set({ health: null });
    }
  },

  refreshModels: async (force = false) => {
    try {
      const res = await apiService.listModels(force);
      if (res.models && res.models.length > 0) {
        set({ availableModels: res.models });
      }
    } catch {
      // Keep existing availableModels on error
    }
  },

  selectSession: async (sessionId: string) => {
    try {
      const detailed = await apiService.getSessionDetails(sessionId);
      const resolvedModel = normalizeModelId(detailed.model_name);
      set((state) => ({
        activeSessionId: detailed.id,
        messages: detailed.messages || [],
        selectedModel: resolvedModel,
        activeProfile: state.activeProfile,
        systemPrompt: detailed.system_prompt || '',
        webSearchMode: (detailed.web_search_mode as WebSearchMode) || 'auto',
        error: null
      }));
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao carregar conversa' });
    }
  },

  createNewSession: async () => {
    try {
      const { selectedModel, webSearchMode } = get();
      const created = await apiService.createSession({
        title: 'New Chat',
        model_name: selectedModel,
        web_search_mode: webSearchMode
      });
      set((state) => ({
        sessions: [created, ...state.sessions],
        activeSessionId: created.id,
        messages: [],
        systemPrompt: '',
        pendingAttachments: [],
        error: null
      }));
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao criar nova conversa' });
    }
  },

  renameSession: async (sessionId: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) return;
    try {
      const updated = await apiService.updateSession(sessionId, { title: trimmed });
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, title: updated.title } : s))
      }));
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao renomear sessão' });
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await apiService.deleteSession(sessionId);
      const remaining = get().sessions.filter((s) => s.id !== sessionId);
      set({ sessions: remaining });

      if (get().activeSessionId === sessionId) {
        if (remaining.length > 0) {
          await get().selectSession(remaining[0].id);
        } else {
          await get().createNewSession();
        }
      }
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao remover sessão' });
    }
  },

  clearCurrentChat: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;
    try {
      await apiService.clearSessionMessages(activeSessionId);
      set({ messages: [] });
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao limpar histórico' });
    }
  },

  setModel: async (modelName: string) => {
    const normalized = normalizeModelId(modelName);
    set({ selectedModel: normalized });
    const { activeSessionId } = get();
    if (activeSessionId) {
      await apiService.updateSession(activeSessionId, { model_name: normalized }).catch(() => {});
    }
  },

  setActiveProfile: (profile: ChatProfileId) => {
    set({ activeProfile: profile });
  },

  setWebSearchMode: async (mode: WebSearchMode) => {
    set({ webSearchMode: mode });
    const { activeSessionId } = get();
    if (activeSessionId) {
      await apiService.updateSession(activeSessionId, { web_search_mode: mode }).catch(() => {});
    }
  },

  setSystemPrompt: async (prompt: string) => {
    set({ systemPrompt: prompt });
    const { activeSessionId } = get();
    if (activeSessionId) {
      await apiService.updateSession(activeSessionId, { system_prompt: prompt }).catch(() => {});
    }
  },

  uploadFiles: async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    set({ isUploading: true, error: null });
    try {
      const uploadedList: Attachment[] = [];
      for (const file of fileArray) {
        const res = await apiService.uploadFile(file);
        uploadedList.push({
          file_id: res.file_id,
          filename: res.filename,
          type: res.file_type,
          content: res.parsed_content,
          size_bytes: res.size_bytes
        });
      }
      set((state) => ({
        pendingAttachments: [...state.pendingAttachments, ...uploadedList]
      }));
    } catch (err: any) {
      set({ error: err?.message || 'Erro ao enviar arquivo(s)' });
    } finally {
      set({ isUploading: false });
    }
  },

  removeAttachment: (index: number) => {
    set((state) => ({
      pendingAttachments: state.pendingAttachments.filter((_, idx) => idx !== index)
    }));
  },

  sendMessage: async (content: string) => {
    const {
      activeSessionId,
      selectedModel,
      activeProfile,
      systemPrompt,
      webSearchMode,
      pendingAttachments,
      isStreaming
    } = get();

    if (isStreaming) return;
    if (!content.trim() && pendingAttachments.length === 0) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      await get().createNewSession();
      targetSessionId = get().activeSessionId;
    }
    if (!targetSessionId) return;

    const effectiveProfile: ChatProfileId = activeProfile;
    const attachmentsToSend = [...pendingAttachments];
    const promptText = content.trim() || `Analise o(s) arquivo(s): ${attachmentsToSend.map((a) => a.filename).join(', ')}`;

    const tempUserMsgId = `user-${Date.now()}`;
    const tempAssistantMsgId = `assistant-${Date.now()}`;

    const userMessage: ChatMessage = {
      id: tempUserMsgId,
      session_id: targetSessionId,
      role: 'user',
      content: promptText,
      metadata_json: attachmentsToSend.length > 0 ? { attachments: attachmentsToSend } : undefined,
      created_at: new Date().toISOString()
    };

    const assistantMessage: ChatMessage = {
      id: tempAssistantMsgId,
      session_id: targetSessionId,
      role: 'assistant',
      content: '',
      metadata_json: {
        model: selectedModel,
        sources: []
      },
      created_at: new Date().toISOString(),
      isStreaming: true,
      searchStatus: { isSearching: false }
    };

    const controller = new AbortController();

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      pendingAttachments: [],
      isStreaming: true,
      abortController: controller,
      error: null
    }));

    try {
      await streamChatCompletion(
        {
          sessionId: targetSessionId,
          content: promptText,
          attachments: attachmentsToSend,
          modelName: selectedModel,
          profileId: effectiveProfile,
          systemPrompt: systemPrompt || null,
          webSearchMode,
          signal: controller.signal
        },
        {
          onSearchStart: (query) => {
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? { ...m, searchStatus: { isSearching: true, query } }
                  : m
              )
            }));
          },
          onSources: (sources, query) => {
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? {
                      ...m,
                      searchStatus: { isSearching: false, query },
                      metadata_json: { ...m.metadata_json, sources }
                    }
                  : m
              )
            }));
          },
          onChunk: (chunkText) => {
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? {
                      ...m,
                      content: m.content + chunkText,
                      searchStatus: { isSearching: false, query: m.searchStatus?.query }
                    }
                  : m
              )
            }));
          },
          onDone: (doneData) => {
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? {
                      ...m,
                      isStreaming: false,
                      metadata_json: {
                        ...m.metadata_json,
                        model: doneData.model || selectedModel
                      }
                    }
                  : m
              )
            }));
          },
          onPersisted: async (persistedData) => {
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? {
                      ...m,
                      id: persistedData.message_id || m.id,
                      isStreaming: false
                    }
                  : m
              )
            }));
            // Refresh session list so auto-updated titles reflect in sidebar
            const updatedSessions = await apiService.listSessions().catch(() => null);
            if (updatedSessions) {
              set({ sessions: updatedSessions });
            }
          },
          onError: (errMsg) => {
            set((state) => ({
              error: errMsg,
              messages: state.messages.map((m) =>
                m.id === tempAssistantMsgId
                  ? {
                      ...m,
                      isStreaming: false,
                      content: m.content
                        ? `${m.content}\n\n⚠️ *Erro: ${errMsg}*`
                        : `⚠️ *Erro ao gerar resposta: ${errMsg}*`
                    }
                  : m
              )
            }));
          }
        }
      );
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === tempAssistantMsgId
              ? { ...m, isStreaming: false, content: m.content + '\n\n*(Geração interrompida pelo usuário)*' }
              : m
          )
        }));
      } else {
        set({ error: err?.message || 'Falha na conexão de streaming SSE' });
      }
    } finally {
      set({ isStreaming: false, abortController: null });
    }
  },

  stopStreaming: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      set({ isStreaming: false, abortController: null });
    }
  },

  setSidebarOpen: (open: boolean) => set({ isSidebarOpen: open }),
  setSettingsOpen: (open: boolean) => set({ isSettingsOpen: open }),
  setTelemetryOpen: (open: boolean) => set({ isTelemetryOpen: open }),
  clearError: () => set({ error: null }),
  resetChatState: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
    }
    set({
      sessions: [],
      activeSessionId: null,
      messages: [],
      pendingAttachments: [],
      isUploading: false,
      isStreaming: false,
      isLoadingSessions: false,
      error: null,
      abortController: null
    });
  }
}));

