import React, { useEffect, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { useChatStore } from './store/useChatStore';
import { useAuthStore } from './store/useAuthStore';
import { Sidebar } from './components/sidebar/Sidebar';
import { Header } from './components/header/Header';
import { ChatArea } from './components/chat/ChatArea';
import { ChatInput } from './components/chat/ChatInput';
import { SettingsModal } from './components/header/SettingsModal';
import { TelemetryDashboard } from './components/telemetry/TelemetryDashboard';
import { AuthGuard } from './components/auth/AuthGuard';

const AuthenticatedWorkspace: React.FC = () => {
  const { initApp, uploadFiles, resetChatState } = useChatStore();
  const { user } = useAuthStore();
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    initApp();
    return () => {
      resetChatState();
    };
  }, [initApp, resetChatState, user?.id]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await uploadFiles(e.dataTransfer.files);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 relative"
    >
      {/* Drag & Drop Overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-indigo-950/80 backdrop-blur-md border-4 border-dashed border-indigo-400 flex flex-col items-center justify-center pointer-events-none">
          <UploadCloud className="w-16 h-16 text-indigo-300 animate-bounce mb-3" />
          <p className="text-lg font-bold text-white">Solte os arquivos para anexar à conversa</p>
          <p className="text-xs text-indigo-200 mt-1">
            Suporta PDF, Python, JS/TS, Markdown, CSV, TXT e Imagens
          </p>
        </div>
      )}

      {/* Collapsible Sidebar */}
      <Sidebar />

      {/* Main Content Workspace */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <Header />
        <ChatArea />
        <ChatInput />
      </div>

      {/* Session Settings & System Prompt Modal */}
      <SettingsModal />

      {/* FinOps Telemetry & Cost Control Dashboard */}
      <TelemetryDashboard />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthGuard>
      <AuthenticatedWorkspace />
    </AuthGuard>
  );
};

export default App;
