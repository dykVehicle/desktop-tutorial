import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { ChatArea } from './ChatArea';
import { SettingsModal } from './SettingsModal';
import { useChatStore } from '../store/useChatStore';

export const Layout = () => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const createSession = useChatStore((state) => state.createSession);

  // Ensure a session exists
  React.useEffect(() => {
    // Only create if we strictly have no sessions and no current ID
    // Check inside a small timeout or just rely on store state
    const unsubscribe = useChatStore.subscribe((state) => {
       if (state.sessions.length === 0 && !state.currentSessionId) {
         createSession();
       }
    });
    return unsubscribe;
  }, [createSession]);

  return (
    <div className="flex h-screen bg-gray-900 text-white overflow-hidden font-sans">
      <Sidebar onOpenSettings={() => setIsSettingsOpen(true)} />
      <main className="flex-1 flex flex-col relative w-full h-full">
        <ChatArea />
      </main>
      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
    </div>
  );
};
