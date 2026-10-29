import React, { useState, useEffect } from 'react';
import { X, Terminal, Globe, Trash2, Save, Code2, Compass, Lock } from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { CHAT_PROFILES, ChatProfileId, WebSearchMode } from '../../types/chat';

export const SettingsModal: React.FC = () => {
  const {
    isSettingsOpen,
    selectedModel,
    activeProfile,
    systemPrompt,
    webSearchMode,
    setSettingsOpen,
    setActiveProfile,
    setSystemPrompt,
    setWebSearchMode,
    clearCurrentChat
  } = useChatStore();

  const [promptValue, setPromptValue] = useState(systemPrompt);
  const isCodeSpecialistModel = selectedModel === 'Qwen3-Coder';

  useEffect(() => {
    setPromptValue(systemPrompt);
  }, [systemPrompt, isSettingsOpen]);

  if (!isSettingsOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    await setSystemPrompt(promptValue);
    setSettingsOpen(false);
  };

  const handleClear = async () => {
    if (window.confirm('Tem certeza que deseja apagar todas as mensagens desta conversa?')) {
      await clearCurrentChat();
      setSettingsOpen(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-700/80 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <Terminal className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-slate-100">
              Configurações da Conversa
            </h2>
          </div>
          <button
            onClick={() => setSettingsOpen(false)}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-5 space-y-5">
          {/* Chat Profile / Persona Selector */}
          <div>
            <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              <Code2 className="w-3.5 h-3.5 text-indigo-400" />
              <span>Perfil de Comportamento (Persona / Workspace)</span>
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              {CHAT_PROFILES.map((profile) => {
                const isLocked = isCodeSpecialistModel && profile.id === 'general_assistant';
                const effectiveProfile: ChatProfileId = isCodeSpecialistModel
                  ? 'software_engineer'
                  : activeProfile;
                const isSelected = effectiveProfile === profile.id;

                return (
                  <button
                    key={profile.id}
                    type="button"
                    disabled={isLocked}
                    onClick={() => setActiveProfile(profile.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      isLocked
                        ? 'bg-slate-950/30 border-slate-800/60 text-slate-600 cursor-not-allowed opacity-60'
                        : isSelected
                        ? profile.id === 'software_engineer'
                          ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                          : 'bg-emerald-600/20 border-emerald-500 text-emerald-200'
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1.5 text-xs font-semibold">
                      <span className="flex items-center gap-1.5">
                        {profile.id === 'software_engineer' ? (
                          <Code2 className="w-3.5 h-3.5 shrink-0" />
                        ) : (
                          <Compass className="w-3.5 h-3.5 shrink-0" />
                        )}
                        {profile.name}
                      </span>
                      {isLocked && <Lock className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                    </div>
                    <div className="text-[10px] opacity-80 mt-1 leading-relaxed">
                      {isLocked
                        ? 'Indisponível para Qwen3-Coder (Especialista exclusivo em Código)'
                        : profile.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              System Prompt (Instruções do Sistema)
            </label>
            <textarea
              rows={5}
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Ex: Você é um Arquiteto de Software Sênior especialista em Python, FastAPI, Docker e React. Responda sempre com exemplos práticos e código limpo..."
              className="w-full rounded-xl bg-slate-950 border border-slate-800 p-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
            />
            <p className="text-[11px] text-slate-400 mt-1.5">
              Define o comportamento, tom e regras globais que o LLM seguirá nesta sessão.
            </p>
          </div>

          {/* Web Search Mode (Essential for Mobile view) */}
          <div>
            <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              <Globe className="w-3.5 h-3.5 text-indigo-400" />
              <span>Busca na Web em Tempo Real</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  { id: 'auto', title: '🔍 Automático', desc: 'Detecta quando buscar' },
                  { id: 'always', title: '⚡ Sempre', desc: 'Pesquisa toda pergunta' },
                  { id: 'disabled', title: '🚫 Desativado', desc: 'Apenas base offline' }
                ] as Array<{ id: WebSearchMode; title: string; desc: string }>
              ).map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setWebSearchMode(option.id)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    webSearchMode === option.id
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="text-xs font-semibold">{option.title}</div>
                  <div className="text-[10px] opacity-80 mt-0.5">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Danger Zone: Clear Messages */}
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
            <button
              type="button"
              onClick={handleClear}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-medium transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Limpar Mensagens</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium shadow-lg shadow-indigo-600/25 transition-all"
              >
                <Save className="w-4 h-4" />
                <span>Salvar Configurações</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

