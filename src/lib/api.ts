import { ModelConfig } from '../types';

export const callModelApi = async (
  model: ModelConfig,
  messages: { role: string; content: string }[],
  onChunk: (chunk: string) => void
): Promise<string> => {
  try {
    // Default OpenAI-compatible implementation
    // This works for OpenAI, DeepSeek, OpenRouter, LocalAI (Ollama), etc.
    const baseUrl = model.baseUrl?.replace(/\/$/, '') || 'https://api.openai.com/v1';
    
    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${model.apiKey}`,
      },
      body: JSON.stringify({
        model: model.modelName,
        messages,
        stream: true,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`API Error ${response.status}: ${errText}`);
    }
    
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              const content = parsed.choices[0]?.delta?.content || '';
              if (content) {
                fullContent += content;
                onChunk(fullContent);
              }
            } catch (e) {
              // ignore parse error
            }
          }
        }
      }
    }
    return fullContent;
  } catch (error: any) {
    throw new Error(error.message || 'Unknown error');
  }
};
