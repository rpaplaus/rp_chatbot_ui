import { create } from 'zustand';
import { TokenResponse, UserProfile } from '../types/auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface AuthState {
  accessToken: string | null; // Armazenado exclusivamente em RAM (mitigação XSS)
  user: UserProfile | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  error: string | null;

  initializeAuth: () => Promise<void>;
  login: (username: string, password: string) => Promise<boolean>;
  refreshAccessToken: () => Promise<string | null>;
  logout: () => Promise<void>;
  clearError: () => void;
}

// Single-flight promise para evitar race conditions na rotação estrita do Refresh Token no Redis
let refreshPromise: Promise<string | null> | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,
  isInitializing: true,
  error: null,

  initializeAuth: async () => {
    set({ isInitializing: true, error: null });
    try {
      const token = await get().refreshAccessToken();
      if (token) {
        set({ isAuthenticated: true, isInitializing: false });
      } else {
        set({
          accessToken: null,
          user: null,
          isAuthenticated: false,
          isInitializing: false
        });
      }
    } catch {
      set({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        isInitializing: false
      });
    }
  },

  login: async (username: string, password: string): Promise<boolean> => {
    set({ error: null });
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Recebe e armazena o cookie HttpOnly rp_refresh_token
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        let detail = 'Credenciais inválidas ou acesso não autorizado.';
        try {
          const errJson = await res.json();
          if (errJson.detail) detail = errJson.detail;
        } catch {
          // ignore parse error
        }
        set({ error: detail, isAuthenticated: false, accessToken: null, user: null });
        return false;
      }

      const data: TokenResponse = await res.json();
      set({
        accessToken: data.access_token,
        user: data.user,
        isAuthenticated: true,
        error: null
      });
      return true;
    } catch (err: any) {
      set({
        error: err?.message || 'Erro de conexão com o servidor de autenticação.',
        isAuthenticated: false,
        accessToken: null,
        user: null
      });
      return false;
    }
  },

  refreshAccessToken: async (): Promise<string | null> => {
    if (refreshPromise) {
      return refreshPromise;
    }

    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          credentials: 'include' // Envia automaticamente o cookie HttpOnly rp_refresh_token
        });

        if (!res.ok) {
          set({
            accessToken: null,
            user: null,
            isAuthenticated: false
          });
          return null;
        }

        const data: TokenResponse = await res.json();
        set({
          accessToken: data.access_token,
          user: data.user,
          isAuthenticated: true,
          error: null
        });
        return data.access_token;
      } catch {
        set({
          accessToken: null,
          user: null,
          isAuthenticated: false
        });
        return null;
      } finally {
        refreshPromise = null;
      }
    })();

    return refreshPromise;
  },

  logout: async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch {
      // ignore network error on logout
    } finally {
      set({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        error: null
      });
    }
  },

  clearError: () => set({ error: null })
}));

