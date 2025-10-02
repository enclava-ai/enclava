// Centralized playground configuration
export const playgroundConfig = {
  // Working models (avoiding rate-limited ones)
  availableModels: [
    {
      id: 'openrouter-gpt-4',
      name: 'GPT-4 (OpenRouter)', 
      provider: 'OpenRouter',
      category: 'chat',
      status: 'available'
    },
    {
      id: 'openrouter-claude-3-sonnet',
      name: 'Claude 3 Sonnet (OpenRouter)',
      provider: 'OpenRouter', 
      category: 'chat',
      status: 'available'
    }
  ],

  // Rate limited models to avoid
  rateLimitedModels: [
    'ollama-qwen3-235b',
    'ollama-gemini-2.0-flash', 
    'ollama-gemini-2.5-pro'
  ],

  // Default settings
  defaults: {
    model: 'openrouter-gpt-4',
    temperature: 0.7,
    maxTokens: 150,
    systemPrompt: 'You are a helpful AI assistant.'
  },

  // Error handling
  errorMessages: {
    rateLimited: 'Model is currently rate limited. Please try another model.',
    authFailed: 'Authentication failed. Please refresh the page.',
    networkError: 'Network error. Please check your connection.'
  }
}

export default playgroundConfig