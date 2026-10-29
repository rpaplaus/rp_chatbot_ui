import React, { useState } from 'react';
import { MessageSquare, Edit2, Trash2, Check, X } from 'lucide-react';
import { ChatSession } from '../../types/chat';

interface SessionItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, newTitle: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export const SessionItem: React.FC<SessionItemProps> = ({
  session,
  isActive,
  onSelect,
  onRename,
  onDelete
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [titleInput, setTitleInput] = useState(session.title);

  const handleSaveRename = async (e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (titleInput.trim() && titleInput.trim() !== session.title) {
      await onRename(session.id, titleInput.trim());
    }
    setIsEditing(false);
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setTitleInput(session.title);
    setIsEditing(false);
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(`Deseja realmente excluir a conversa "${session.title}"?`)) {
      await onDelete(session.id);
    }
  };

  return (
    <div
      onClick={() => !isEditing && onSelect(session.id)}
      className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 text-sm ${
        isActive
          ? 'bg-indigo-600/20 text-indigo-200 border border-indigo-500/30 font-medium shadow-sm'
          : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200 border border-transparent'
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <MessageSquare
          className={`w-4 h-4 shrink-0 ${
            isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-400'
          }`}
        />
        {isEditing ? (
          <form onSubmit={handleSaveRename} className="flex items-center gap-1 flex-1 min-w-0">
            <input
              type="text"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              autoFocus
              className="w-full bg-slate-900 text-slate-100 px-2 py-0.5 rounded border border-indigo-500/50 text-xs focus:outline-none"
            />
            <button
              type="submit"
              className="p-1 text-emerald-400 hover:bg-slate-700 rounded"
              title="Salvar"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleCancelRename}
              className="p-1 text-rose-400 hover:bg-slate-700 rounded"
              title="Cancelar"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <span className="truncate">{session.title}</span>
        )}
      </div>

      {!isEditing && (
        <div
          className={`flex items-center gap-1 ml-2 shrink-0 ${
            isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          } transition-opacity`}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              setTitleInput(session.title);
              setIsEditing(true);
            }}
            className="p-1 text-slate-400 hover:text-indigo-300 hover:bg-slate-700/60 rounded-lg transition-colors"
            title="Renomear conversa"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleDelete}
            className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            title="Excluir conversa"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

