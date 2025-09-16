export const config = {
  API_BASE_URL: process.env.NEXT_PUBLIC_BASE_URL || '',
  APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || 'Enclava',
  DEFAULT_LANGUAGE: 'en',
  SUPPORTED_LANGUAGES: ['en', 'es', 'fr', 'de', 'it'],
  getPublicApiUrl() {
    if (this.API_BASE_URL) {
      return this.API_BASE_URL
    }

    if (typeof window !== 'undefined' && window.location.origin) {
      return window.location.origin
    }

    return ''
  },

  // Feature flags
  FEATURES: {
    RAG: true,
    PLUGINS: true,
    ANALYTICS: true,
    AUDIT_LOGS: true,
    BUDGET_MANAGEMENT: true,
  },

  // Default values
  DEFAULTS: {
    TEMPERATURE: 0.7,
    MAX_TOKENS: 1000,
    TOP_K: 5,
    MEMORY_LENGTH: 10,
  },

  // API endpoints
  ENDPOINTS: {
    AUTH: {
      LOGIN: '/api/auth/login',
      REGISTER: '/api/auth/register',
      REFRESH: '/api/auth/refresh',
      ME: '/api/auth/me',
    },
    CHATBOT: {
      LIST: '/api/chatbot/list',
      CREATE: '/api/chatbot/create',
      UPDATE: '/api/chatbot/update/:id',
      DELETE: '/api/chatbot/delete/:id',
      CHAT: '/api/chatbot/chat',
    },
    LLM: {
      MODELS: '/api/llm/models',
      API_KEYS: '/api/llm/api-keys',
      BUDGETS: '/api/llm/budgets',
    },
    RAG: {
      COLLECTIONS: '/api/rag/collections',
      DOCUMENTS: '/api/rag/documents',
    },
  },
};
