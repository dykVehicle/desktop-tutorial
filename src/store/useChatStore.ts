import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';
import type { ModelConfig, ChatSession, ChatTurn, ModelResponse } from '../types';

interface ChatState {
  models: ModelConfig[];
  sessions: ChatSession[];
  currentSessionId: string | null;
  
  // Actions
  addModel: (model: ModelConfig) => void;
  updateModel: (id: string, updates: Partial<ModelConfig>) => void;
  deleteModel: (id: string) => void;
  toggleModel: (id: string) => void;
  
  createSession: () => string;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  
  addTurn: (sessionId: string, userContent: string, activeModelIds: string[]) => string; // Returns turnId
  updateTurnResponse: (sessionId: string, turnId: string, modelId: string, content: string, status: 'loading' | 'success' | 'error', errorMessage?: string) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      models: [],
      sessions: [],
      currentSessionId: null,

      addModel: (model) => set((state) => ({ models: [...state.models, model] })),
      updateModel: (id, updates) => set((state) => ({
        models: state.models.map((m) => (m.id === id ? { ...m, ...updates } : m)),
      })),
      deleteModel: (id) => set((state) => ({ models: state.models.filter((m) => m.id !== id) })),
      toggleModel: (id) => set((state) => ({
        models: state.models.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m)),
      })),

      createSession: () => {
        const newSession: ChatSession = {
          id: uuidv4(),
          title: 'New Chat',
          turns: [],
          createdAt: Date.now(),
        };
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          currentSessionId: newSession.id,
        }));
        return newSession.id;
      },
      selectSession: (id) => set({ currentSessionId: id }),
      deleteSession: (id) => set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== id),
        currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
      })),

      addTurn: (sessionId, userContent, activeModelIds) => {
        const turnId = uuidv4();
        const newTurn: ChatTurn = {
          id: turnId,
          userMessage: {
            id: uuidv4(),
            role: 'user',
            content: userContent,
            timestamp: Date.now(),
          },
          responses: activeModelIds.reduce((acc, modelId) => {
            acc[modelId] = {
              modelId,
              status: 'loading',
              content: '',
            } as ModelResponse;
            return acc;
          }, {} as Record<string, ModelResponse>),
        };

        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id === sessionId) {
              return {
                ...s,
                turns: [...s.turns, newTurn],
                // Update title if it's the first turn
                title: s.turns.length === 0 ? userContent.slice(0, 30) : s.title,
              };
            }
            return s;
          }),
        }));
        return turnId;
      },

      updateTurnResponse: (sessionId, turnId, modelId, content, status, errorMessage) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id === sessionId) {
              return {
                ...s,
                turns: s.turns.map((t) => {
                  if (t.id === turnId) {
                    return {
                      ...t,
                      responses: {
                        ...t.responses,
                        [modelId]: {
                          ...t.responses[modelId],
                          content,
                          status,
                          errorMessage,
                        },
                      },
                    };
                  }
                  return t;
                }),
              };
            }
            return s;
          }),
        }));
      },
    }),
    {
      name: 'ai-chat-storage',
    }
  )
);
