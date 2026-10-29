import React, { useState } from 'react';
import { Globe, ExternalLink, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { SearchSource } from '../../types/chat';

interface SearchIndicatorProps {
  isSearching?: boolean;
  query?: string;
  sources?: SearchSource[];
}

export const SearchIndicator: React.FC<SearchIndicatorProps> = ({
  isSearching,
  query,
  sources
}) => {
  const [expanded, setExpanded] = useState(true);

  if (!isSearching && (!sources || sources.length === 0)) {
    return null;
  }

  const getHostname = (url: string) => {
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return 'web';
    }
  };

  return (
    <div className="mb-3 rounded-xl bg-slate-900/90 border border-slate-800/90 overflow-hidden">
      {isSearching ? (
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-indigo-300">
          <Loader2 className="w-4 h-4 animate-spin text-indigo-400 shrink-0" />
          <span>
            Pesquisando na web em tempo real{query ? ` por "${query}"` : ''}...
          </span>
        </div>
      ) : (
        <div>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between px-3.5 py-2 text-xs text-slate-300 hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Globe className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-medium">
                {sources?.length} {sources?.length === 1 ? 'fonte consultada' : 'fontes consultadas'}
                {query ? ` para "${query}"` : ''}
              </span>
            </div>
            {expanded ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            )}
          </button>

          {expanded && sources && sources.length > 0 && (
            <div className="px-3 pb-3 pt-1 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-slate-800/60">
              {sources.map((src, idx) => (
                <a
                  key={idx}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-start justify-between gap-2 p-2.5 rounded-lg bg-slate-950/70 hover:bg-indigo-950/30 border border-slate-800/80 hover:border-indigo-500/40 transition-all"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300">
                        [{src.index || idx + 1}]
                      </span>
                      <span className="text-xs font-medium text-slate-200 group-hover:text-indigo-200 truncate">
                        {src.title}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 block mt-0.5 truncate">
                      {getHostname(src.url)}
                    </span>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 shrink-0 mt-0.5" />
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

