import React, { useEffect, useState, useCallback } from 'react';
import {
  X,
  BarChart3,
  DollarSign,
  Cpu,
  RefreshCw,
  Shield,
  Trophy,
  Calendar,
  Users,
  Activity,
  TrendingUp,
  AlertCircle
} from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { useAuthStore } from '../../store/useAuthStore';
import { apiService } from '../../services/api';
import {
  AdminUsageSummaryResponse,
  ModelUsageBreakdown,
  UserUsageSummaryResponse
} from '../../types/chat';

interface ProviderMeta {
  label: string;
  modelDisplay: string;
  rateInfo: string;
  badgeClass: string;
  barClass: string;
}

const PROVIDER_CATALOG: Record<string, ProviderMeta> = {
  openai: {
    label: 'OpenAI',
    modelDisplay: 'GPT-5 (gpt-5-2025-08-07)',
    rateInfo: '$2.50 / $10.00 por 1M',
    badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    barClass: 'from-emerald-500 to-teal-400'
  },
  anthropic: {
    label: 'Anthropic',
    modelDisplay: 'Claude Sonnet 4.6',
    rateInfo: '$3.00 / $15.00 por 1M',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    barClass: 'from-amber-500 to-orange-400'
  },
  gemini: {
    label: 'Google Gemini',
    modelDisplay: 'Gemini 3.1 Pro Preview',
    rateInfo: '$1.25 / $5.00 por 1M',
    badgeClass: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    barClass: 'from-blue-500 to-cyan-400'
  },
  xai: {
    label: 'xAI Grok',
    modelDisplay: 'Grok-4 Fast Reasoning',
    rateInfo: '$2.00 / $10.00 por 1M',
    badgeClass: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    barClass: 'from-purple-500 to-fuchsia-400'
  },
  qwen: {
    label: 'Alibaba Qwen',
    modelDisplay: 'Qwen3-Coder (qwen3.5-plus)',
    rateInfo: '$0.80 / $2.40 por 1M',
    badgeClass: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    barClass: 'from-indigo-500 to-violet-400'
  }
};

function formatUsd(val: number): string {
  if (!val || val === 0) return '$0.0000';
  if (val < 0.01) return `$${val.toFixed(6)}`;
  if (val < 1) return `$${val.toFixed(4)}`;
  return `$${val.toFixed(2)}`;
}

function formatNumber(num: number): string {
  return (num || 0).toLocaleString('pt-BR');
}

function mergeWithAllProviders(items: ModelUsageBreakdown[], totalCost: number): ModelUsageBreakdown[] {
  const mapByProvider = new Map<string, ModelUsageBreakdown>();

  for (const item of items) {
    const key = item.provider.toLowerCase();
    const existing = mapByProvider.get(key);
    if (existing) {
      existing.request_count += item.request_count;
      existing.prompt_tokens += item.prompt_tokens;
      existing.completion_tokens += item.completion_tokens;
      existing.total_tokens += item.total_tokens;
      existing.total_cost_usd += item.total_cost_usd;
      existing.percentage_of_cost =
        totalCost > 0 ? Number(((existing.total_cost_usd / totalCost) * 100).toFixed(2)) : 0;
    } else {
      mapByProvider.set(key, { ...item });
    }
  }

  const allProviders = ['openai', 'anthropic', 'gemini', 'xai', 'qwen'];
  for (const prov of allProviders) {
    if (!mapByProvider.has(prov)) {
      mapByProvider.set(prov, {
        provider: prov,
        model_name: PROVIDER_CATALOG[prov]?.modelDisplay || prov,
        request_count: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        total_cost_usd: 0,
        percentage_of_cost: 0
      });
    }
  }

  return Array.from(mapByProvider.values()).sort(
    (a, b) => b.total_cost_usd - a.total_cost_usd || b.total_tokens - a.total_tokens
  );
}

export const TelemetryDashboard: React.FC = () => {
  const { isTelemetryOpen, setTelemetryOpen } = useChatStore();
  const { user } = useAuthStore();

  const isAdmin = user?.role === 'admin';
  const [activeTab, setActiveTab] = useState<'user' | 'admin'>('user');
  const [userMetrics, setUserMetrics] = useState<UserUsageSummaryResponse | null>(null);
  const [adminMetrics, setAdminMetrics] = useState<AdminUsageSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTelemetry = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const userRes = await apiService.getUserUsageMetrics();
      setUserMetrics(userRes);

      if (isAdmin) {
        const adminRes = await apiService.getAdminUsageMetrics();
        setAdminMetrics(adminRes);
      }
    } catch (err: any) {
      setError(err?.message || 'Erro ao carregar dados de telemetria.');
    } finally {
      setIsLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (isTelemetryOpen) {
      loadTelemetry();
    }
  }, [isTelemetryOpen, loadTelemetry]);

  if (!isTelemetryOpen) return null;

  const currentMonthLabel = new Intl.DateTimeFormat('pt-BR', {
    month: 'long',
    year: 'numeric'
  }).format(new Date());

  const userModelsList = mergeWithAllProviders(
    userMetrics?.by_model || [],
    userMetrics?.total_cost_usd || 0
  );

  const adminModelsList = mergeWithAllProviders(
    adminMetrics?.by_model || [],
    adminMetrics?.total_platform_cost_usd || 0
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-slate-950/80 backdrop-blur-md">
      <div className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-slate-900 border border-slate-700/80 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Top Modal Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Telemetria & Controle de Custos
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold uppercase tracking-wide">
                  FinOps USD
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Monitoramento em tempo real dos 5 provedores de IA (OpenAI, Anthropic, Gemini, xAI e Qwen)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isAdmin && (
              <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 mr-1">
                <button
                  type="button"
                  onClick={() => setActiveTab('user')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    activeTab === 'user'
                      ? 'bg-indigo-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Meu Consumo
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('admin')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    activeTab === 'admin'
                      ? 'bg-emerald-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Shield className="w-3.5 h-3.5" />
                  <span>Admin Global</span>
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={loadTelemetry}
              disabled={isLoading}
              title="Atualizar métricas"
              className="p-2 text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-indigo-400' : ''}`} />
            </button>

            <button
              type="button"
              onClick={() => setTelemetryOpen(false)}
              title="Fechar painel"
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {error && (
            <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {activeTab === 'user' ? (
            <>
              {/* KPI Summary Cards (User) */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Card 1: Current Month Spend */}
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800/90 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Consumo no Mês Atual
                    </span>
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                      <Calendar className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-emerald-400 tracking-tight">
                    {formatUsd(userMetrics?.current_month_cost_usd || 0)}
                  </div>
                  <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400">
                    <span className="capitalize">{currentMonthLabel}</span>
                    <span className="text-slate-300 font-medium">
                      {formatNumber(userMetrics?.current_month_tokens || 0)} tokens
                    </span>
                  </div>
                </div>

                {/* Card 2: Total All-Time Cost */}
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800/90 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Total Gasto Acumulado
                    </span>
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                      <DollarSign className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-slate-100 tracking-tight">
                    {formatUsd(userMetrics?.total_cost_usd || 0)}
                  </div>
                  <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400">
                    <span>Conta: {userMetrics?.username || user?.username}</span>
                    <span className="text-indigo-300 font-medium">
                      {formatNumber(userMetrics?.total_requests || 0)} chamadas
                    </span>
                  </div>
                </div>

                {/* Card 3: Total Tokens (Input vs Output) */}
                <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800/90 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Tokens Processados
                    </span>
                    <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
                      <Cpu className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-slate-100 tracking-tight">
                    {formatNumber(userMetrics?.total_tokens || 0)}
                  </div>
                  <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400">
                    <span>In: {formatNumber(userMetrics?.total_prompt_tokens || 0)}</span>
                    <span>Out: {formatNumber(userMetrics?.total_completion_tokens || 0)}</span>
                  </div>
                </div>
              </div>

              {/* Breakdown by AI Provider */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-indigo-400" />
                    Detalhamento Financeiro por Provedor de IA (5 Modelos)
                  </h3>
                  <span className="text-[11px] text-slate-400">
                    Tarifação oficial por 1M tokens (Input / Output)
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {userModelsList.map((item) => {
                    const meta = PROVIDER_CATALOG[item.provider.toLowerCase()] || {
                      label: item.provider.toUpperCase(),
                      modelDisplay: item.model_name,
                      rateInfo: 'Tarifa Padrão',
                      badgeClass: 'bg-slate-700 text-slate-200 border-slate-600',
                      barClass: 'from-indigo-500 to-indigo-400'
                    };

                    return (
                      <div
                        key={`${item.provider}-${item.model_name}`}
                        className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700/80 transition-all"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                          <div className="flex items-center gap-2.5">
                            <span
                              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-lg border ${meta.badgeClass}`}
                            >
                              {meta.label}
                            </span>
                            <span className="text-sm font-semibold text-slate-100">
                              {item.model_name}
                            </span>
                            <span className="text-[11px] text-slate-500 hidden sm:inline">
                              ({meta.rateInfo})
                            </span>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-xs text-slate-400">
                              {formatNumber(item.request_count)} reqs
                            </span>
                            <span className="text-sm font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">
                              {formatUsd(item.total_cost_usd)}
                            </span>
                          </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full h-2 bg-slate-800/90 rounded-full overflow-hidden mb-2.5">
                          <div
                            className={`h-full rounded-full bg-gradient-to-r ${meta.barClass} transition-all duration-500`}
                            style={{ width: `${Math.max(item.total_tokens > 0 ? 3 : 0, Math.min(100, item.percentage_of_cost))}%` }}
                          />
                        </div>

                        <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
                          <div className="flex items-center gap-4">
                            <span>
                              Prompt (Input):{' '}
                              <strong className="text-slate-200">
                                {formatNumber(item.prompt_tokens)}
                              </strong>
                            </span>
                            <span>
                              Completion (Output):{' '}
                              <strong className="text-slate-200">
                                {formatNumber(item.completion_tokens)}
                              </strong>
                            </span>
                            <span>
                              Total:{' '}
                              <strong className="text-indigo-300">
                                {formatNumber(item.total_tokens)} tokens
                              </strong>
                            </span>
                          </div>
                          <span className="font-medium text-slate-300">
                            {item.percentage_of_cost.toFixed(1)}% do custo total
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            /* ADMIN VIEW: Global Platform Cost + User Ranking */
            <div className="space-y-6">
              {/* Admin KPI Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                <div className="p-4 rounded-2xl bg-slate-950/90 border border-emerald-500/30">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold uppercase mb-1">
                    <span>Custo Global (Mês)</span>
                    <Calendar className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div className="text-xl font-bold text-emerald-400">
                    {formatUsd(adminMetrics?.current_month_platform_cost_usd || 0)}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1 capitalize">{currentMonthLabel}</p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/90 border border-indigo-500/30">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold uppercase mb-1">
                    <span>Custo Global Total</span>
                    <DollarSign className="w-4 h-4 text-indigo-400" />
                  </div>
                  <div className="text-xl font-bold text-slate-100">
                    {formatUsd(adminMetrics?.total_platform_cost_usd || 0)}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">Acumulado da plataforma</p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/90 border border-slate-800">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold uppercase mb-1">
                    <span>Tokens Globais</span>
                    <Activity className="w-4 h-4 text-amber-400" />
                  </div>
                  <div className="text-xl font-bold text-slate-100">
                    {formatNumber(adminMetrics?.total_platform_tokens || 0)}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {formatNumber(adminMetrics?.total_platform_requests || 0)} requisições totais
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-950/90 border border-slate-800">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold uppercase mb-1">
                    <span>Usuários Ativos</span>
                    <Users className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div className="text-xl font-bold text-slate-100">
                    {adminMetrics?.active_users_count || 0}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">Whitelist autorizada</p>
                </div>
              </div>

              {/* User Ranking Table */}
              <div className="rounded-2xl bg-slate-950/80 border border-slate-800 overflow-hidden">
                <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Trophy className="w-4 h-4 text-amber-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Ranking de Consumo por Usuário (Top Consumers)
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-400">
                    Ordenado por maior gasto acumulado (USD)
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800/80 text-[11px] uppercase tracking-wider text-slate-400 bg-slate-900/50">
                        <th className="py-3 px-4">#</th>
                        <th className="py-3 px-4">Usuário</th>
                        <th className="py-3 px-4">Role</th>
                        <th className="py-3 px-4 text-right">Chamadas</th>
                        <th className="py-3 px-4 text-right">Tokens (In / Out)</th>
                        <th className="py-3 px-4 text-right">Mês Atual (USD)</th>
                        <th className="py-3 px-4 text-right">Total Gasto (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-xs">
                      {(adminMetrics?.user_ranking || []).map((u, idx) => (
                        <tr key={u.user_id} className="hover:bg-slate-900/60 transition-colors">
                          <td className="py-3 px-4 font-bold text-slate-400">#{idx + 1}</td>
                          <td className="py-3 px-4">
                            <div className="font-semibold text-slate-100">{u.username}</div>
                            <div className="text-[11px] text-slate-500">{u.email}</div>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                                u.role === 'admin'
                                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                  : 'bg-slate-800 text-slate-300 border border-slate-700'
                              }`}
                            >
                              {u.role}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right text-slate-300 font-medium">
                            {formatNumber(u.request_count)}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="font-semibold text-slate-200">
                              {formatNumber(u.total_tokens)}
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {formatNumber(u.prompt_tokens)} in / {formatNumber(u.completion_tokens)} out
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right font-semibold text-indigo-300">
                            {formatUsd(u.current_month_cost_usd)}
                          </td>
                          <td className="py-3 px-4 text-right font-bold text-emerald-400">
                            {formatUsd(u.total_cost_usd)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Global Breakdown by Model */}
              <div className="space-y-2.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Consumo Global da Plataforma por Provedor de IA
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {adminModelsList.map((m) => {
                    const meta = PROVIDER_CATALOG[m.provider.toLowerCase()];
                    return (
                      <div
                        key={`admin-${m.provider}-${m.model_name}`}
                        className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-slate-200">
                            {meta?.label || m.provider.toUpperCase()}
                          </span>
                          <span className="text-xs font-bold text-emerald-400">
                            {formatUsd(m.total_cost_usd)}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center justify-between">
                          <span>{formatNumber(m.total_tokens)} tokens</span>
                          <span>{formatNumber(m.request_count)} reqs</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

