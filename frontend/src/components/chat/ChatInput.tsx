import React, { useState, useRef, useEffect } from 'react';
import {
  Paperclip,
  SendHorizontal,
  Square,
  X,
  FileText,
  Image as ImageIcon,
  Loader2
} from 'lucide-react';
import { useChatStore } from '../../store/useChatStore';

export const ChatInput: React.FC = () => {
  const {
    pendingAttachments,
    isUploading,
    isStreaming,
    uploadFiles,
    removeAttachment,
    sendMessage,
    stopStreaming
  } = useChatStore();

  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [text]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (isStreaming || isUploading) return;
    if (!text.trim() && pendingAttachments.length === 0) return;

    const currentText = text;
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await sendMessage(currentText);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await uploadFiles(e.target.files);
      e.target.value = '';
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  return (
    <div className="p-3 sm:p-4 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="rounded-2xl bg-slate-900/95 border border-slate-700/80 focus-within:border-indigo-500/70 shadow-2xl shadow-black/50 transition-all overflow-hidden">
          {/* Pending Attachments Bar */}
          {(pendingAttachments.length > 0 || isUploading) && (
            <div className="px-3.5 pt-3 pb-1 flex flex-wrap items-center gap-2 border-b border-slate-800/70">
              {pendingAttachments.map((att, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 group"
                >
                  {att.type === 'image' ? (
                    <ImageIcon className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                  ) : (
                    <FileText className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  )}
                  <span className="truncate max-w-[160px] font-medium">{att.filename}</span>
                  {att.size_bytes && (
                    <span className="text-[10px] text-slate-500">{formatBytes(att.size_bytes)}</span>
                  )}
                  <button
                    type="button"
                    onClick={() => removeAttachment(index)}
                    className="p-0.5 text-slate-500 hover:text-rose-400 rounded transition-colors"
                    title="Remover anexo"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}

              {isUploading && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-300">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Extraindo conteúdo do arquivo...</span>
                </div>
              )}
            </div>
          )}

          {/* Input Row */}
          <form onSubmit={handleSubmit} className="flex items-end gap-2 p-2.5 sm:p-3">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.py,.js,.ts,.tsx,.jsx,.md,.csv,.json,.sql,.pdf,.jpg,.jpeg,.png,.webp,.mp3,.wav"
              onChange={handleFileChange}
              className="hidden"
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || isStreaming}
              className="p-2.5 text-slate-400 hover:text-indigo-300 hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-40 shrink-0"
              title="Anexar arquivos (.pdf, .py, .txt, .md, .csv, imagens)"
            >
              <Paperclip className="w-5 h-5" />
            </button>

            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Envie uma pergunta, cole código ou anexe documentos (Shift+Enter para nova linha)..."
              className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 text-sm sm:text-[15px] py-2 px-1 focus:outline-none resize-none max-h-44 custom-scrollbar"
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/25 transition-all shrink-0"
                title="Interromper geração"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                <span className="hidden sm:inline">Parar</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={(!text.trim() && pendingAttachments.length === 0) || isUploading}
                className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white shadow-lg shadow-indigo-600/20 transition-all shrink-0"
                title="Enviar mensagem"
              >
                <SendHorizontal className="w-5 h-5" />
              </button>
            )}
          </form>
        </div>

        <div className="text-center mt-2">
          <p className="text-[11px] text-slate-500">
            RP_ChatBot Multi-LLM • Respostas geradas por IA podem conter imprecisões.
          </p>
        </div>
      </div>
    </div>
  );
};

