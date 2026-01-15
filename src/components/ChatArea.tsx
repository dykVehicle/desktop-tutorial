import React, { useState, useEffect, useRef } from 'react';
import { useChatStore } from '../store/useChatStore';
import { callModelApi } from '../lib/api';
import { MarkdownRenderer } from './MarkdownRenderer';
import { Send, CheckCircle2, Circle, AlertTriangle, Bot, GitCompare } from 'lucide-react';
import { ChatTurn } from '../types';

export const ChatArea = () => {
  const { currentSessionId, sessions, models, addTurn, updateTurnResponse } = useChatStore();
  const session = sessions.find((s) => s.id === currentSessionId);
  
  const [input, setInput] = useState('');
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Initialize selected models
  useEffect(() => {
    if (models.length > 0 && selectedModelIds.length === 0) {
      setSelectedModelIds(models.filter(m => m.enabled).map(m => m.id));
    }
  }, [models]);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [session?.turns]);

  const handleSend = async (overrideInput?: string, overrideModels?: string[]) => {
    const text = overrideInput ?? input;
    const targetModels = overrideModels ?? selectedModelIds;

    if (!text.trim() || !session || targetModels.length === 0) return;

    if (!overrideInput) setInput('');
    const turnId = addTurn(session.id, text, targetModels);
    
    setTimeout(scrollToBottom, 10);

    const targets = targetModels.map(id => models.find(m => m.id === id)).filter(Boolean);

    targets.forEach(async (model) => {
      if (!model) return;
      try {
        const messages = session.turns
          .filter(t => t.id !== turnId)
          .flatMap(t => {
            const msgs = [{ role: 'user', content: t.userMessage.content }];
            const resp = t.responses[model.id];
            if (resp && resp.status === 'success') {
              msgs.push({ role: 'assistant', content: resp.content });
            }
            return msgs;
          });
        
        messages.push({ role: 'user', content: text });

        const finalContent = await callModelApi(model, messages, (chunk) => {
           updateTurnResponse(session.id, turnId, model.id, chunk, 'loading');
           scrollToBottom();
        });
        
        updateTurnResponse(session.id, turnId, model.id, finalContent, 'success');
        
      } catch (e: any) {
        updateTurnResponse(session.id, turnId, model.id, '', 'error', e.message);
      }
    });
  };

  const handleCompare = (turn: ChatTurn) => {
    const prompt = `Here are the responses from different models to the prompt: "${turn.userMessage.content}"\n\n` + 
      Object.values(turn.responses).map((r) => {
         const mName = models.find(m => m.id === r.modelId)?.name || 'Unknown';
         return `### Response from ${mName}:\n${r.content}\n`;
      }).join('\n---\n\n');
    
    const context = `Please analyze and compare the differences in the responses above. Highlight key distinctions in reasoning, format, and accuracy.`;
    
    // Use the first selected model, or first enabled model
    const summarizerId = selectedModelIds[0] || models.find(m => m.enabled)?.id;
    if (summarizerId) {
        // We inject the context as a "User Message" that contains the data
        handleSend(`${prompt}\n\n${context}`, [summarizerId]);
    }
  };

  const toggleModelSelection = (modelId: string) => {
    setSelectedModelIds(prev => 
      prev.includes(modelId) ? prev.filter(id => id !== modelId) : [...prev, modelId]
    );
  };

  if (!session) return <div className="flex-1 flex items-center justify-center text-gray-500">Select or create a chat</div>;

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth" ref={scrollRef}>
        {session.turns.map((turn) => {
          const responseCount = Object.keys(turn.responses).length;
          const isMultiResponse = responseCount > 1;
          const allFinished = Object.values(turn.responses).every(r => r.status === 'success' || r.status === 'error');

          return (
            <div key={turn.id} className="space-y-4 border-b border-gray-800/50 pb-6 last:border-0">
              {/* User Message */}
              <div className="flex justify-end">
                <div className="bg-blue-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] shadow-lg">
                  <MarkdownRenderer content={turn.userMessage.content} />
                </div>
              </div>

              {/* Responses Grid */}
              <div className={`grid gap-4 ${isMultiResponse ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1'}`}>
                {Object.values(turn.responses).map((resp) => {
                  const model = models.find(m => m.id === resp.modelId);
                  return (
                    <div key={resp.modelId} className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden flex flex-col shadow-md">
                      <div className="bg-gray-900/50 p-2 border-b border-gray-700 flex items-center justify-between">
                        <span className="text-xs font-bold text-gray-300 flex items-center gap-2">
                          <Bot size={14} className="text-blue-400" /> 
                          {model?.name || 'Unknown Model'}
                        </span>
                        <div className="flex items-center gap-2">
                          {resp.status === 'loading' && <div className="animate-spin w-3 h-3 border-2 border-blue-500 rounded-full border-t-transparent"></div>}
                          {resp.status === 'error' && <AlertTriangle size={14} className="text-red-500" />}
                          {resp.status === 'success' && <CheckCircle2 size={14} className="text-green-500" />}
                        </div>
                      </div>
                      <div className="p-4 text-sm text-gray-300 min-h-[50px] max-h-[500px] overflow-y-auto">
                        {resp.errorMessage ? (
                          <span className="text-red-400 font-mono text-xs">Error: {resp.errorMessage}</span>
                        ) : (
                          <MarkdownRenderer content={resp.content} />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Compare Button */}
              {isMultiResponse && allFinished && (
                <div className="flex justify-center">
                  <button
                    onClick={() => handleCompare(turn)}
                    className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded-lg text-sm transition-colors border border-gray-600"
                  >
                    <GitCompare size={16} />
                    Compare Results
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-gray-800 border-t border-gray-700 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-600">
          {models.filter(m => m.enabled).map(model => (
            <button
              key={model.id}
              onClick={() => toggleModelSelection(model.id)}
              className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                selectedModelIds.includes(model.id) 
                  ? 'bg-blue-600 text-white shadow-sm shadow-blue-900/50' 
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              {selectedModelIds.includes(model.id) ? <CheckCircle2 size={12} /> : <Circle size={12} />}
              {model.name}
            </button>
          ))}
          {models.length === 0 && (
             <span className="text-xs text-yellow-500 flex items-center gap-1 bg-yellow-500/10 px-2 py-1 rounded">
               <AlertTriangle size={12}/> No models configured. Go to Settings.
             </span>
          )}
        </div>
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl p-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none h-[52px] max-h-[200px]"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || selectedModelIds.length === 0}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 rounded-xl transition-all shadow-lg shadow-blue-900/20 flex items-center justify-center"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
};
