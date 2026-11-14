import React, { useState, useRef, useEffect, useMemo } from 'react';
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
  Search,
  RefreshCw,
  Star,
  X
} from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { CHAT_PROFILES, ChatProfileId, ModelOption, SUPPORTED_MODELS, WebSearchMode } from '../../types/chat';

function formatPricePer1M(prompt?: number, completion?: number, isFree?: boolean): string {
  if (isFree || ((prompt === 0 || prompt === undefined) && (completion === 0 || completion === undefined))) {
    return 'FREE';
  }
  const p = prompt ?? 0;
  const c = completion ?? 0;
  const fmt = (v: number) => (v < 0.1 && v > 0 ? v.toFixed(3) : v.toFixed(2));
  return `$${fmt(p)} / $${fmt(c)} /1M`;
}

function formatContextLength(ctx?: number): string {
  if (!ctx || ctx <= 0) return '';
  if (ctx >= 1000000) return `${(ctx / 1000000).toFixed(1).replace('.0', '')}M ctx`;
  if (ctx >= 1000) return `${Math.round(ctx / 1000)}k ctx`;
  return `${ctx} ctx`;
}

export const Header: React.FC = () => {
  const {
    isSidebarOpen,
    availableModels,
    selectedModel,
    activeProfile,
    webSearchMode,
    systemPrompt,
    setSidebarOpen,
    setModel,
    setActiveProfile,
    setWebSearchMode,
    setSettingsOpen,
    refreshModels
  } = useChatStore();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [modelSearch, setModelSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [isRefreshingModels, setIsRefreshingModels] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const modelsCatalog = availableModels.length > 0 ? availableModels : SUPPORTED_MODELS;

  const currentModelObj: ModelOption = useMemo(() => {
    const found = modelsCatalog.find((m) => m.id === selectedModel);
    if (found) return found;
    const slug = selectedModel.includes('/') ? selectedModel.split('/')[0] : 'openrouter';
    return {
      id: selectedModel,
      name: selectedModel,
      provider: slug,
      badge: slug.toUpperCase(),
      description: 'Modelo OpenRouter'
    };
  }, [modelsCatalog, selectedModel]);

  const filteredModels = useMemo(() => {
    const q = modelSearch.trim().toLowerCase();
    return modelsCatalog.filter((m) => {
      if (providerFilter === 'featured' && !m.featured) return false;
      if (providerFilter === 'free' && !m.is_free) return false;
      if (
        providerFilter !== 'all' &&
        providerFilter !== 'featured' &&
        providerFilter !== 'free' &&
        m.provider.toLowerCase() !== providerFilter
      ) {
        return false;
      }

      if (!q) return true;
      return (
        m.name.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        m.badge.toLowerCase().includes(q) ||
        (m.description && m.description.toLowerCase().includes(q))
      );
    });
  }, [modelsCatalog, modelSearch, providerFilter]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (dropdownOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 40);
    }
  }, [dropdownOpen]);

  const handleRefreshCatalog = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsRefreshingModels(true);
    try {
      await refreshModels(true);
    } finally {
      setIsRefreshingModels(false);
    }
  };

  const quickFilters = [
    { id: 'all', label: `Todos (${modelsCatalog.length})` },
    { id: 'featured', label: '⭐ Destaques' },
    { id: 'free', label: 'Gratuitos' },
    { id: 'openai', label: 'OpenAI' },
    { id: 'anthropic', label: 'Anthropic' },
    { id: 'google', label: 'Google' },
    { id: 'x-ai', label: 'xAI' },
    { id: 'qwen', label: 'Qwen' },
    { id: 'deepseek', label: 'DeepSeek' },
    { id: 'meta-llama', label: 'Llama' },
    { id: 'mistralai', label: 'Mistral' }
  ];

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

        {/* OpenRouter Dynamic Model Selector Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-slate-800/90 hover:bg-slate-800 border border-slate-700/70 text-slate-100 text-sm font-medium transition-all shadow-sm"
          >
            <Sparkles className="w-4 h-4 text-indigo-400 shrink-0" />
            <span className="truncate max-w-[150px] sm:max-w-[240px]">{currentModelObj.name}</span>
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
            <div className="absolute left-0 mt-2 w-[340px] sm:w-[440px] rounded-2xl bg-slate-900 border border-slate-700/80 shadow-2xl shadow-black/70 z-50 overflow-hidden flex flex-col">
              {/* Top Bar + Refresh */}
              <div className="px-3.5 py-2.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-300">
                    Catálogo OpenRouter
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">
                    {filteredModels.length} modelos
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleRefreshCatalog}
                  disabled={isRefreshingModels}
                  title="Sincronizar modelos com o OpenRouter"
                  className="p-1 text-slate-400 hover:text-indigo-300 hover:bg-slate-800 rounded-lg transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isRefreshingModels ? 'animate-spin text-indigo-400' : ''}`} />
                </button>
              </div>

              {/* Search Input */}
              <div className="p-2.5 border-b border-slate-800/80 bg-slate-900">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={modelSearch}
                    onChange={(e) => setModelSearch(e.target.value)}
                    placeholder="Buscar modelo ou provedor (ex: gpt-5, claude, deepseek, free)..."
                    className="w-full bg-slate-950 text-slate-100 placeholder-slate-500 text-xs pl-8 pr-7 py-2 rounded-xl border border-slate-800 focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                  {modelSearch && (
                    <button
                      type="button"
                      onClick={() => setModelSearch('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Quick Filter Pills */}
                <div className="flex items-center gap-1.5 overflow-x-auto pt-2 pb-0.5 custom-scrollbar">
                  {quickFilters.map((f) => {
                    const active = providerFilter === f.id;
                    return (
                      <button
                        key={f.id}
                        type="button"
                        onClick={() => setProviderFilter(f.id)}
                        className={`px-2 py-1 rounded-lg text-[10px] font-medium whitespace-nowrap transition-colors ${
                          active
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-950/90 text-slate-400 hover:text-slate-200 border border-slate-800'
                        }`}
                      >
                        {f.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Scrollable Model List */}
              <div className="py-1 max-h-96 overflow-y-auto custom-scrollbar divide-y divide-slate-800/40">
                {filteredModels.length === 0 ? (
                  <div className="py-8 px-4 text-center text-xs text-slate-500">
                    Nenhum modelo encontrado para "{modelSearch}".
                  </div>
                ) : (
                  filteredModels.map((model) => {
                    const isSelected = model.id === selectedModel;
                    const ctxText = formatContextLength(model.context_length);
                    const priceText = formatPricePer1M(
                      model.prompt_price_per_1m,
                      model.completion_price_per_1m,
                      model.is_free
                    );

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
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center flex-wrap gap-1.5">
                            {model.featured && (
                              <Star className="w-3 h-3 text-amber-400 fill-amber-400 shrink-0" />
                            )}
                            <span className="text-xs sm:text-sm font-medium truncate max-w-[230px]">
                              {model.name}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
                              {model.badge}
                            </span>
                            {model.supports_tools === false && (
                              <span
                                className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20"
                                title="Sem suporte nativo a Function Calling"
                              >
                                Sem Tools
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400 font-mono">
                            <span className="truncate max-w-[190px] text-slate-500">{model.id}</span>
                            {ctxText && (
                              <span className="px-1.5 py-0.2 rounded bg-slate-950 border border-slate-800 text-slate-400">
                                {ctxText}
                              </span>
                            )}
                            <span
                              className={`px-1.5 py-0.2 rounded border ${
                                model.is_free
                                  ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 font-semibold'
                                  : 'bg-slate-950 border-slate-800 text-slate-400'
                              }`}
                            >
                              {priceText}
                            </span>
                          </div>
                        </div>
                        {isSelected && <Check className="w-4 h-4 text-indigo-400 shrink-0 mt-1" />}
                      </button>
                    );
                  })
                )}
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
            const isActive = activeProfile === prof.id;

            return (
              <button
                key={prof.id}
                type="button"
                onClick={() => setActiveProfile(prof.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? prof.id === 'software_engineer'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title={`${prof.label}: ${prof.description}`}
              >
                {prof.icon}
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

