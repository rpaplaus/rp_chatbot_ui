import React, { useEffect, useState } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';
import { RefreshCw, WifiOff, X } from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';

const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000;

/**
 * Registers the service worker and shows:
 * - an "update available" prompt (applied only on user confirmation, never mid-stream);
 * - an offline banner, since chatting requires the backend.
 */
export const PWAStatus: React.FC = () => {
  const isStreaming = useChatStore((s) => s.isStreaming);
  const [isOffline, setIsOffline] = useState(() => typeof navigator !== 'undefined' && !navigator.onLine);

  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_swUrl, registration) {
      if (!registration) return;
      setInterval(() => {
        if (navigator.onLine) registration.update().catch(() => undefined);
      }, UPDATE_CHECK_INTERVAL_MS);
    },
    onRegisterError(error) {
      console.error('[PWA] Service worker registration failed:', error);
    },
  });

  useEffect(() => {
    const goOnline = () => setIsOffline(false);
    const goOffline = () => setIsOffline(true);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  if (!isOffline && !needRefresh) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]">
      {isOffline && (
        <div
          role="status"
          className="pointer-events-auto flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-950/90 px-3 py-2 text-xs text-amber-100 shadow-lg backdrop-blur"
        >
          <WifiOff className="h-4 w-4 shrink-0" />
          Você está offline. O chat ficará disponível quando a conexão voltar.
        </div>
      )}

      {needRefresh && (
        <div
          role="alert"
          className="pointer-events-auto flex items-center gap-3 rounded-lg border border-indigo-500/40 bg-slate-900/95 px-3 py-2 text-xs text-slate-100 shadow-lg backdrop-blur"
        >
          <span>Nova versão do RP_ChatBot disponível.</span>
          <button
            type="button"
            disabled={isStreaming}
            onClick={() => updateServiceWorker(true)}
            title={isStreaming ? 'Aguarde a resposta terminar' : undefined}
            className="flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 font-semibold text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Atualizar
          </button>
          <button
            type="button"
            aria-label="Dispensar"
            onClick={() => setNeedRefresh(false)}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
