import React, { useState, useRef, useEffect } from 'react';
import {
  PanelLeftOpen,
  ChevronDown,
  Globe,
  Zap,
  ShieldOff,
  SlidersHorizontal,
  Sparkles,
  Check,
  Code2,
  Compass,
  Lock
} from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { CHAT_PROFILES, ChatProfileId, SUPPORTED_MODELS, WebSearchMode } from '../../types/chat';

export const Header: React.FC = () => {
  const {
    isSidebarOpen,
    selectedModel,
    activeProfile,
    webSearchMode,
    systemPrompt,
    setSidebarOpen,
    setModel,
    setActiveProfile,
    setWebSearchMode,
    setSettingsOpen
  } = useChatStore();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentModelObj =
    SUPPORTED_MODELS.find((m) => m.id === selectedModel) || SUPPORTED_MODELS[0];

  const isCodeSpecialistModel = selectedModel === 'Qwen3-Coder';

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const profileOptions: Array<{
    id: ChatProfileId;
    label: string;
    description: string;
    icon: React.ReactNode;
  }> = CHAT_PROFILES.map((p) => ({
    id: p.id,
    label: p.shortLabel,
    description: p.description,
    icon:
      p.id === 'software_engineer' ? (
        <Code2 className="w-3.5 h-3.5" />
      ) : (
        <Compass className="w-3.5 h-3.5" />
      )
  }));

  const searchModes: Array<{ value: WebSearchMode; label: string; icon: React.ReactNode }> = [
    { value: 'auto', label: 'Auto', icon: <Globe className="w-3.5 h-3.5" /> },
    { value: 'always', label: 'Sempre', icon: <Zap className="w-3.5 h-3.5" /> },
    { value: 'disabled', label: 'Off', icon: <ShieldOff className="w-3.5 h-3.5" /> }
  ];

  return (
    <header className="h-16 px-4 border-b border-slate-800/80 bg-slate-900/75 backdrop-blur-md flex items-center justify-between gap-2 z-20 shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        {!isSidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-xl transition-colors"
            title="Abrir barra lateral"
          >
            <PanelLeftOpen className="w-5 h-5" />
          </button>
        )}

        {/* Model Selector Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-slate-800/90 hover:bg-slate-800 border border-slate-700/70 text-slate-100 text-sm font-medium transition-all shadow-sm"
          >
            <Sparkles className="w-4 h-4 text-indigo-400 shrink-0" />
            <span className="truncate max-w-[150px] sm:max-w-[220px]">{currentModelObj.name}</span>
            <span className="hidden sm:inline-block text-[10px] px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {currentModelObj.badge}
            </span>
            <ChevronDown
              className={`w-4 h-4 text-slate-400 transition-transform duration-150 ${
                dropdownOpen ? 'rotate-180' : ''
              }`}
            />
          </button>

          {dropdownOpen && (
            <div className="absolute left-0 mt-2 w-72 sm:w-80 rounded-2xl bg-slate-900 border border-slate-700/80 shadow-2xl shadow-black/60 py-2 z-50">
              <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                Selecione o Modelo LLM
              </div>
              <div className="py-1 max-h-80 overflow-y-auto">
                {SUPPORTED_MODELS.map((model) => {
                  const isSelected = model.id === selectedModel;
                  return (
                    <button
                      key={model.id}
                      onClick={() => {
                        setModel(model.id);
                        setDropdownOpen(false);
                      }}
                      className={`w-full text-left px-3.5 py-2.5 flex items-start justify-between gap-2 transition-colors ${
                        isSelected ? 'bg-indigo-600/15 text-indigo-200' : 'hover:bg-slate-800/70 text-slate-300'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">{model.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {model.badge}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                          {model.description}
                        </p>
                      </div>
                      {isSelected && <Check className="w-4 h-4 text-indigo-400 shrink-0 mt-1" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Profile / Persona Selector (Next to Model Selector) */}
        <div
          className="hidden sm:flex items-center bg-slate-950/80 p-1 rounded-xl border border-slate-800"
          role="group"
          aria-label="Seletor de Perfil de Chat"
        >
          {profileOptions.map((prof) => {
            const isLocked = isCodeSpecialistModel && prof.id === 'general_assistant';
            const effectiveActiveProfile: ChatProfileId = isCodeSpecialistModel
              ? 'software_engineer'
              : activeProfile;
            const isActive = effectiveActiveProfile === prof.id;

            return (
              <button
                key={prof.id}
                type="button"
                disabled={isLocked}
                onClick={() => setActiveProfile(prof.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  isLocked
                    ? 'text-slate-600 cursor-not-allowed opacity-50'
                    : isActive
                    ? prof.id === 'software_engineer'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title={
                  isLocked
                    ? 'Qwen3-Coder é dedicado exclusivamente à Engenharia de Software (Tool Disabling ativo)'
                    : `${prof.label}: ${prof.description}`
                }
              >
                {isLocked ? <Lock className="w-3 h-3 text-amber-400/80" /> : prof.icon}
                <span>{prof.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right Controls: Web Search Mode & Settings */}
      <div className="flex items-center gap-2">
        {/* Web Search Mode Segmented Pill */}
        <div className="hidden sm:flex items-center bg-slate-950/80 p-1 rounded-xl border border-slate-800">
          {searchModes.map((m) => {
            const active = webSearchMode === m.value;
            return (
              <button
                key={m.value}
                onClick={() => setWebSearchMode(m.value)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  active
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title={`Busca Web: ${m.label}`}
              >
                {m.icon}
                <span>{m.label}</span>
              </button>
            );
          })}
        </div>

        {/* Settings / System Prompt Button */}
        <button
          onClick={() => setSettingsOpen(true)}
          className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-all ${
            systemPrompt.trim()
              ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-200'
              : 'bg-slate-800/80 hover:bg-slate-800 border-slate-700/70 text-slate-300'
          }`}
          title="Configurações da Sessão e System Prompt"
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span className="hidden md:inline">Configurações</span>
          {systemPrompt.trim() && (
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
          )}
        </button>
      </div>
    </header>
  );
};

