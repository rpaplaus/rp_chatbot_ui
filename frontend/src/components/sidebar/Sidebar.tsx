import React, { useState } from 'react';
import { Plus, Search, Bot, PanelLeftClose, Activity, Sparkles, LogOut, Shield, BarChart3 } from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { useAuthStore } from '../../store/useAuthStore';
import { SessionItem } from './SessionItem';

export const Sidebar: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    isSidebarOpen,
    health,
    selectSession,
    createNewSession,
    renameSession,
    deleteSession,
    setSidebarOpen,
    setTelemetryOpen
  } = useChatStore();

  const { user, logout } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelectSession = async (id: string) => {
    await selectSession(id);
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const handleNewChat = async () => {
    await createNewSession();
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isSidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-30 md:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 flex flex-col bg-slate-900/95 border-r border-slate-800/80 transition-all duration-300 ease-in-out ${
          isSidebarOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full md:w-0 overflow-hidden border-r-0'
        }`}
      >
        <div className="flex flex-col h-full w-72">
          {/* Brand Header */}
          <div className="flex items-center justify-between px-4 h-16 border-b border-slate-800/80">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-1.5">
                  RP_ChatBot
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold">
                    PRO
                  </span>
                </h1>
                <p className="text-[11px] text-slate-400">Multi-LLM Workspace</p>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
              title="Recolher barra lateral"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-3">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium text-sm shadow-lg shadow-indigo-600/20 transition-all duration-150"
            >
              <Plus className="w-4 h-4" />
              <span>Nova Conversa</span>
            </button>
          </div>

          {/* Search Filter */}
          <div className="px-3 pb-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filtrar conversas..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950/70 text-slate-200 placeholder-slate-500 text-xs pl-8 pr-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-indigo-500/60 transition-colors"
              />
            </div>
          </div>

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 px-2 pb-1.5">
              Histórico ({filteredSessions.length})
            </div>

            {filteredSessions.length === 0 ? (
              <div className="text-center py-8 px-4">
                <Sparkles className="w-6 h-6 text-slate-600 mx-auto mb-2" />
                <p className="text-xs text-slate-500">Nenhuma conversa encontrada.</p>
              </div>
            ) : (
              filteredSessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  onSelect={handleSelectSession}
                  onRename={renameSession}
                  onDelete={deleteSession}
                />
              ))
            )}
          </div>

          {/* User Profile & System Health Footer */}
          <div className="p-3 border-t border-slate-800/80 bg-slate-950/50 space-y-2.5">
            {/* Telemetry & Cost Dashboard Trigger Button */}
            <button
              type="button"
              onClick={() => setTelemetryOpen(true)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800/90 border border-slate-800 hover:border-indigo-500/40 text-slate-200 text-xs font-medium transition-all group"
            >
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
                <span>Telemetria & Custos</span>
              </div>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-semibold">
                USD
              </span>
            </button>

            {user && (
              <div className="flex items-center justify-between px-2 py-1.5 rounded-xl bg-slate-900/90 border border-slate-800/80">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 font-bold text-xs uppercase shrink-0">
                    {user.username.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold text-slate-200 truncate">
                        {user.username}
                      </span>
                      <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-medium uppercase">
                        <Shield className="w-2.5 h-2.5" />
                        {user.role}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 truncate">{user.email}</p>
                  </div>
                </div>
                <button
                  onClick={logout}
                  title="Encerrar sessão (Logout)"
                  className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors shrink-0"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between text-xs text-slate-400 px-1">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    health?.status === 'healthy'
                      ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
                      : 'bg-amber-400'
                  }`}
                />
                <span className="truncate font-medium text-slate-300">
                  {health?.status === 'healthy' ? 'Clusters Online' : 'Conectando...'}
                </span>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-slate-500">
                <Activity className="w-3.5 h-3.5 text-indigo-400" />
                <span>{health?.active_providers?.length || 5} LLMs</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
