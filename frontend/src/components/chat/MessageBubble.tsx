import React, { useState } from 'react';
import {
  Bot,
  User,
  Copy,
  Check,
  FileText,
  Image as ImageIcon,
  Music,
  FileDown,
  Loader2
} from 'lucide-react';
import { ChatMessage } from '../../types/chat';
import { apiService } from '../../services/api';
import { MarkdownRenderer } from './MarkdownRenderer';
import { SearchIndicator } from './SearchIndicator';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const [copied, setCopied] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  const isUser = message.role === 'user';
  const attachments = message.metadata_json?.attachments || [];
  const sources = message.metadata_json?.sources || [];
  const modelUsed = message.metadata_json?.model;

  const handleCopyMessage = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGeneratePdf = async () => {
    if (isGeneratingPdf || !message.content) return;
    setIsGeneratingPdf(true);
    try {
      const blob = await apiService.generatePdf({
        content: message.content,
        title: 'Relatório Técnico — RP_ChatBot',
        model_name: modelUsed || 'Multi-LLM'
      });

      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      link.href = objectUrl;
      link.download = `rp_chatbot_${timestamp}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);
    } catch (err: any) {
      console.error('Erro ao gerar PDF:', err);
      alert(err?.message || 'Não foi possível gerar o PDF.');
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const getAttachmentIcon = (type: string) => {
    if (type === 'image') return <ImageIcon className="w-3.5 h-3.5 text-indigo-400" />;
    if (type === 'audio') return <Music className="w-3.5 h-3.5 text-amber-400" />;
    return <FileText className="w-3.5 h-3.5 text-emerald-400" />;
  };

  return (
    <div
      className={`group flex gap-3 sm:gap-4 py-5 px-4 sm:px-6 transition-colors ${
        isUser ? 'bg-transparent' : 'bg-slate-900/40 border-y border-slate-800/40'
      }`}
    >
      <div className="max-w-4xl mx-auto w-full flex gap-3 sm:gap-4">
        {/* Avatar */}
        <div
          className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 shadow-md ${
            isUser
              ? 'bg-slate-800 border border-slate-700 text-slate-200'
              : 'bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-indigo-500/20'
          }`}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>

        {/* Content Body */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Header Info */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">
                {isUser ? 'Você' : 'RP_ChatBot'}
              </span>
              {!isUser && modelUsed && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/90 text-indigo-300 border border-slate-700/70 font-mono">
                  {modelUsed}
                </span>
              )}
            </div>

            {isUser && message.content && (
              <button
                onClick={handleCopyMessage}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-all flex items-center gap-1 text-[11px]"
                title="Copiar mensagem"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copiado</span>
                  </>
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            )}
          </div>

          {/* Attached Files Display (User Message) */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 pb-1">
              {attachments.map((att, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 text-xs text-slate-200"
                >
                  {getAttachmentIcon(att.type)}
                  <span className="truncate max-w-[200px] font-medium">{att.filename}</span>
                </div>
              ))}
            </div>
          )}

          {/* Web Search Status & Sources (Assistant Message) */}
          {!isUser && (
            <SearchIndicator
              isSearching={message.searchStatus?.isSearching}
              query={message.searchStatus?.query}
              sources={sources}
            />
          )}

          {/* Message Content or Streaming Indicator */}
          {message.content ? (
            <div className="relative">
              <MarkdownRenderer content={message.content} />
              {message.isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 align-middle bg-indigo-400 animate-pulse rounded-sm" />
              )}
            </div>
          ) : (
            message.isStreaming && (
              <div className="flex items-center gap-1.5 py-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" />
              </div>
            )
          )}

          {/* Assistant Bottom Action Bar (Copy & Generate PDF) */}
          {!isUser && message.content && !message.isStreaming && (
            <div className="pt-2 mt-2 border-t border-slate-800/60 flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopyMessage}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/70 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/60 transition-all text-xs font-medium"
                title="Copiar resposta em Markdown"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-300">Copiado</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-slate-400" />
                    <span>Copiar</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleGeneratePdf}
                disabled={isGeneratingPdf}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/15 hover:bg-indigo-600/25 disabled:opacity-50 text-indigo-300 hover:text-indigo-200 border border-indigo-500/30 transition-all text-xs font-medium"
                title="Exportar esta resposta para um documento PDF A4 formatado"
              >
                {isGeneratingPdf ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                    <span>Gerando PDF...</span>
                  </>
                ) : (
                  <>
                    <FileDown className="w-3.5 h-3.5 text-indigo-400" />
                    <span>📄 Gerar PDF</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
