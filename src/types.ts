export type ModelType = 'openai' | 'anthropic' | 'gemini' | 'local' | 'other';

export interface ModelConfig {
  id: string;
  name: string;
  provider: ModelType;
  apiKey?: string;
  baseUrl?: string; // For local/openai-compatible
  modelName: string; // e.g. gpt-4, claude-3-opus
  enabled: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export interface ModelResponse {
  modelId: string;
  status: 'idle' | 'loading' | 'success' | 'error';
  content: string;
  errorMessage?: string;
  duration?: number; // ms
}

export interface ChatTurn {
  id: string;
  userMessage: Message;
  responses: Record<string, ModelResponse>; // Keyed by modelId
}

export interface ChatSession {
  id: string;
  title: string;
  turns: ChatTurn[];
  createdAt: number;
}
