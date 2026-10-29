import React, { useEffect, useRef } from 'react';
import {
  Bot,
  Code2,
  Globe,
  FileSearch,
  Cpu,
  AlertCircle,
  X
} from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';
import { MessageBubble } from './MessageBubble';

export const ChatArea: React.FC = () => {
  const {
    messages,
    selectedModel,
    activeProfile,
    error,
    clearError,
    sendMessage
  } = useChatStore();

  const effectiveProfile = selectedModel === 'Qwen3-Coder' ? 'software_engineer' : activeProfile;

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const starterPrompts = [
    {
      icon: <Code2 className="w-4 h-4 text-indigo-400" />,
      title: 'Arquitetura & Microsserviços',
      prompt: 'Projete uma arquitetura resiliente em FastAPI com Redis Pub/Sub e PostgreSQL assíncrono.'
    },
    {
      icon: <Globe className="w-4 h-4 text-emerald-400" />,
      title: 'Busca em Tempo Real na Web',
      prompt: 'Pesquise as últimas novidades sobre modelos de IA e lançamentos de tecnologia hoje.'
    },
    {
      icon: <FileSearch className="w-4 h-4 text-amber-400" />,
      title: 'Refatoração & Clean Code',
      prompt: 'Quais são as melhores práticas para implementar o padrão Strategy em Python 3.11 com tipagem estrita?'
    },
    {
      icon: <Cpu className="w-4 h-4 text-purple-400" />,
      title: 'Otimização SQL & Índices',
      prompt: 'Como otimizar consultas JSONB e índices B-Tree no PostgreSQL 16 para alto volume de leituras?'
    }
  ];

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col relative">
      {/* Error Banner */}
      {error && (
        <div className="sticky top-3 z-20 mx-auto max-w-3xl w-full px-4">
          <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-rose-950/90 border border-rose-500/40 text-rose-200 text-xs shadow-xl backdrop-blur-md">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={clearError}
              className="p-1 hover:bg-rose-900/60 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-3xl mx-auto w-full text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-indigo-700/20 border border-indigo-500/30 flex items-center justify-center mb-5 shadow-2xl shadow-indigo-500/10">
            <Bot className="w-9 h-9 text-indigo-400" />
          </div>

          <h2 className="text-xl sm:text-2xl font-bold text-slate-100 tracking-tight">
            {effectiveProfile === 'general_assistant'
              ? 'Como posso ajudar você hoje?'
              : 'Como posso acelerar seu código hoje?'}
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-2 max-w-lg">
            Conectado ao modelo <span className="text-indigo-300 font-medium">{selectedModel}</span>{' '}
            no perfil{' '}
            <span
              className={`font-medium ${
                effectiveProfile === 'general_assistant' ? 'text-emerald-300' : 'text-indigo-300'
              }`}
            >
              {effectiveProfile === 'general_assistant' ? 'Assistente Geral' : 'Engenheiro de Software'}
            </span>
            . Envie código, documentos PDF, imagens ou consulte dados em tempo real na web.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mt-8 text-left">
            {starterPrompts.map((item, idx) => (
              <button
                key={idx}
                onClick={() => sendMessage(item.prompt)}
                className="group p-4 rounded-2xl bg-slate-900/70 hover:bg-slate-800/80 border border-slate-800/90 hover:border-indigo-500/40 transition-all duration-150 flex flex-col justify-between gap-2 shadow-sm"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-200 group-hover:text-indigo-300">
                  {item.icon}
                  <span>{item.title}</span>
                </div>
                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                  {item.prompt}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 divide-y divide-slate-800/30 pb-6">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
};

