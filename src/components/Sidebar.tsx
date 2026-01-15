import React from 'react';
import { useChatStore } from '../store/useChatStore';
import { Plus, MessageSquare, Settings, Trash2 } from 'lucide-react';

export const Sidebar = ({ onOpenSettings }: { onOpenSettings: () => void }) => {
  const sessions = useChatStore((state) => state.sessions);
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const selectSession = useChatStore((state) => state.selectSession);
  const deleteSession = useChatStore((state) => state.deleteSession);
  const createSession = useChatStore((state) => state.createSession);

  return (
    <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col flex-shrink-0">
      <div className="p-4 border-b border-gray-700">
        <button
          onClick={() => createSession()}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 p-2 rounded-lg transition-colors text-white font-medium"
        >
          <Plus size={20} />
          New Chat
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
              session.id === currentSessionId ? 'bg-gray-700' : 'hover:bg-gray-700/50'
            }`}
            onClick={() => selectSession(session.id)}
          >
            <div className="flex items-center gap-3 overflow-hidden">
              <MessageSquare size={16} className="text-gray-400 flex-shrink-0" />
              <span className="truncate text-sm text-gray-200">{session.title}</span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(session.id);
              }}
              className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded text-red-400 transition-opacity"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {sessions.length === 0 && (
          <div className="text-gray-500 text-center text-sm mt-10">
            No chats yet.
          </div>
        )}
      </div>

      <div className="p-4 border-t border-gray-700">
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-2 p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-300"
        >
          <Settings size={20} />
          Settings & Models
        </button>
      </div>
    </div>
  );
};
