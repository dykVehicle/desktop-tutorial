import { useState } from 'react';
import { useChatStore } from '../store/useChatStore';
import type { ModelConfig, ModelType } from '../types';
import { X, Plus, Trash2, Check } from 'lucide-react';

export const SettingsModal = ({ onClose }: { onClose: () => void }) => {
  const models = useChatStore((state) => state.models);
  const addModel = useChatStore((state) => state.addModel);
  const deleteModel = useChatStore((state) => state.deleteModel);
  const updateModel = useChatStore((state) => state.updateModel);

  const [isAdding, setIsAdding] = useState(false);
  const [newModel, setNewModel] = useState<Partial<ModelConfig>>({
    name: '',
    provider: 'openai',
    modelName: '',
    baseUrl: '',
    apiKey: '',
    enabled: true,
  });

  const handleSave = () => {
    if (!newModel.name || !newModel.modelName) return;
    addModel({
      id: crypto.randomUUID(),
      name: newModel.name,
      provider: newModel.provider as ModelType || 'openai',
      modelName: newModel.modelName,
      baseUrl: newModel.baseUrl || 'https://api.openai.com/v1',
      apiKey: newModel.apiKey || '',
      enabled: true,
    } as ModelConfig);
    setIsAdding(false);
    setNewModel({ name: '', provider: 'openai', modelName: '', baseUrl: '', apiKey: '', enabled: true });
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center backdrop-blur-sm">
      <div className="bg-gray-800 rounded-xl w-full max-w-3xl shadow-2xl border border-gray-700 flex flex-col max-h-[90vh]">
        <div className="p-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">Model Settings</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-4">
            {models.map((model) => (
              <div key={model.id} className="bg-gray-900 p-4 rounded-lg border border-gray-700 flex items-center justify-between">
                <div>
                  <div className="font-bold text-white">{model.name}</div>
                  <div className="text-xs text-gray-500">{model.modelName} • {model.provider}</div>
                </div>
                <div className="flex items-center gap-3">
                   <button
                    onClick={() => updateModel(model.id, { enabled: !model.enabled })}
                    className={`p-2 rounded-full ${model.enabled ? 'bg-green-600/20 text-green-400' : 'bg-gray-700 text-gray-500'}`}
                   >
                     <Check size={16} />
                   </button>
                   <button
                    onClick={() => deleteModel(model.id)}
                    className="p-2 text-red-400 hover:bg-red-400/10 rounded-full"
                   >
                     <Trash2 size={16} />
                   </button>
                </div>
              </div>
            ))}
          </div>

          {isAdding ? (
            <div className="mt-6 bg-gray-700/50 p-4 rounded-lg border border-gray-600 space-y-3">
               <div className="grid grid-cols-2 gap-4">
                 <input
                   placeholder="Display Name (e.g. GPT-4)"
                   className="bg-gray-900 border border-gray-700 p-2 rounded text-white text-sm"
                   value={newModel.name}
                   onChange={e => setNewModel({...newModel, name: e.target.value})}
                 />
                 <select
                   className="bg-gray-900 border border-gray-700 p-2 rounded text-white text-sm"
                   value={newModel.provider}
                   onChange={e => setNewModel({...newModel, provider: e.target.value as any})}
                 >
                   <option value="openai">OpenAI Compatible</option>
                   <option value="anthropic">Anthropic (Not impl)</option>
                   <option value="local">Local (Ollama/LM Studio)</option>
                 </select>
               </div>
               <div className="grid grid-cols-2 gap-4">
                 <input
                   placeholder="Model ID (e.g. gpt-4-turbo)"
                   className="bg-gray-900 border border-gray-700 p-2 rounded text-white text-sm"
                   value={newModel.modelName}
                   onChange={e => setNewModel({...newModel, modelName: e.target.value})}
                 />
                 <input
                   placeholder="Base URL (Optional)"
                   className="bg-gray-900 border border-gray-700 p-2 rounded text-white text-sm"
                   value={newModel.baseUrl}
                   onChange={e => setNewModel({...newModel, baseUrl: e.target.value})}
                 />
               </div>
               <input
                 placeholder="API Key"
                 type="password"
                 className="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white text-sm"
                 value={newModel.apiKey}
                 onChange={e => setNewModel({...newModel, apiKey: e.target.value})}
               />
               <div className="flex justify-end gap-2">
                 <button onClick={() => setIsAdding(false)} className="px-3 py-1 text-sm text-gray-400">Cancel</button>
                 <button onClick={handleSave} className="px-3 py-1 text-sm bg-blue-600 text-white rounded">Save</button>
               </div>
            </div>
          ) : (
            <button
              onClick={() => setIsAdding(true)}
              className="mt-6 w-full py-3 border-2 border-dashed border-gray-700 text-gray-400 rounded-lg hover:border-gray-500 hover:text-gray-300 transition-colors flex items-center justify-center gap-2"
            >
              <Plus size={20} /> Add Model
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
