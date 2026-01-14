
export interface AppError extends Error {
  code: 'UNAUTHORIZED' | 'NETWORK_ERROR' | 'VALIDATION_ERROR' | 'NOT_FOUND' | 'FORBIDDEN' | 'TIMEOUT' | 'UNKNOWN'
  status?: number
  details?: any
}

function makeError(message: string, code: AppError['code'], status?: number, details?: any): AppError {
  const err = new Error(message) as AppError
  err.code = code
  err.status = status
  err.details = details
  return err
}

async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const { tokenManager } = await import('./token-manager')
    const token = await tokenManager.getAccessToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

async function request<T = any>(method: string, url: string, body?: any, extraInit?: RequestInit): Promise<T> {
  try {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      ...(method !== 'GET' && method !== 'HEAD' ? { 'Content-Type': 'application/json' } : {}),
      ...(await getAuthHeader()),
      ...(extraInit?.headers as Record<string, string> | undefined),
    }

    const res = await fetch(url, {
      method,
      headers,
      body: body != null && method !== 'GET' && method !== 'HEAD' ? JSON.stringify(body) : undefined,
      ...extraInit,
    })

    if (!res.ok) {
      // Read the body once to avoid "Body has already been consumed" errors on non-JSON responses
      const rawBody = await res.text().catch(() => '')
      let details: any = undefined
      try { details = rawBody ? JSON.parse(rawBody) : undefined } catch { details = rawBody }
      const status = res.status
      if (status === 401) throw makeError('Unauthorized', 'UNAUTHORIZED', status, details)
      if (status === 403) throw makeError('Forbidden', 'FORBIDDEN', status, details)
      if (status === 404) throw makeError('Not found', 'NOT_FOUND', status, details)
      if (status === 400 || status === 422) throw makeError('Validation error', 'VALIDATION_ERROR', status, details)
      throw makeError('Request failed', 'UNKNOWN', status, details)
    }

    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      return (await res.json()) as T
    }
    // @ts-expect-error allow non-json generic
    return (await res.text()) as T
  } catch (e: any) {
    if (e?.code) throw e
    if (e?.name === 'AbortError') throw makeError('Request timed out', 'TIMEOUT')
    throw makeError(e?.message || 'Network error', 'NETWORK_ERROR')
  }
}

export const apiClient = {
  get: <T = any>(url: string, init?: RequestInit) => request<T>('GET', url, undefined, init),
  post: <T = any>(url: string, body?: any, init?: RequestInit) => request<T>('POST', url, body, init),
  put: <T = any>(url: string, body?: any, init?: RequestInit) => request<T>('PUT', url, body, init),
  delete: <T = any>(url: string, init?: RequestInit) => request<T>('DELETE', url, undefined, init),
}

export const chatbotApi = {
  async listChatbots() {
    try {
      return await apiClient.get('/api-internal/v1/chatbot/list')
    } catch {
      return await apiClient.get('/api-internal/v1/chatbot/instances')
    }
  },
  createChatbot(config: any) {
    return apiClient.post('/api-internal/v1/chatbot/create', config)
  },
  updateChatbot(id: string, config: any) {
    return apiClient.put(`/api-internal/v1/chatbot/update/${encodeURIComponent(id)}`, config)
  },
  deleteChatbot(id: string) {
    return apiClient.delete(`/api-internal/v1/chatbot/delete/${encodeURIComponent(id)}`)
  },
  // Legacy method with JWT auth (to be deprecated)
  sendMessage(chatbotId: string, message: string, conversationId?: string, history?: Array<{role: string; content: string}>) {
    const body: any = { message }
    if (conversationId) body.conversation_id = conversationId
    if (history) body.history = history
    return apiClient.post(`/api-internal/v1/chatbot/chat/${encodeURIComponent(chatbotId)}`, body)
  },
  // OpenAI-compatible chatbot API with API key auth
  sendOpenAIChatMessage(chatbotId: string, messages: Array<{role: string; content: string}>, apiKey: string, options?: {
    temperature?: number
    max_tokens?: number
    stream?: boolean
  }) {
    const body: any = {
      messages,
      ...options
    }
    return fetch(`/api/v1/chatbot/external/${encodeURIComponent(chatbotId)}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(body)
    }).then(res => res.json())
  }
}

export const agentApi = {
  listAgents(params?: { category?: string; is_public?: boolean }) {
    const queryParams = new URLSearchParams()
    if (params?.category) queryParams.append('category', params.category)
    if (params?.is_public !== undefined) queryParams.append('is_public', String(params.is_public))
    const query = queryParams.toString()
    return apiClient.get(`/agent/configs${query ? `?${query}` : ''}`)
  },
  getAgent(id: number) {
    return apiClient.get(`/agent/configs/${id}`)
  },
  createAgent(config: any) {
    return apiClient.post('/agent/configs', config)
  },
  updateAgent(id: number, config: any) {
    return apiClient.put(`/agent/configs/${id}`, config)
  },
  deleteAgent(id: number) {
    return apiClient.delete(`/agent/configs/${id}`)
  },
  // OpenAI-compatible chat completions (internal, JWT auth)
  chat(agentConfigId: number, messages: Array<{role: string; content: string}>, options?: {
    temperature?: number
    max_tokens?: number
  }) {
    return apiClient.post(`/agent/${agentConfigId}/chat/completions`, {
      messages,
      ...options
    })
  },
  // Simple chat helper - wraps a single message in OpenAI format
  sendMessage(agentConfigId: number, message: string, history?: Array<{role: string; content: string}>) {
    const messages = [
      ...(history || []),
      { role: 'user', content: message }
    ]
    return apiClient.post(`/agent/${agentConfigId}/chat/completions`, { messages })
  }
}

export const toolApi = {
  listTools() {
    return apiClient.get('/api/v1/tool-calling/available')
  }
}

export const mcpServerApi = {
  /**
   * List all MCP servers accessible to the current user
   */
  listServers(includeInactive?: boolean) {
    const params = includeInactive ? '?include_inactive=true' : ''
    return apiClient.get(`/api/v1/mcp-servers${params}`)
  },

  /**
   * Get simplified list for agent configuration dropdowns
   */
  getAvailableServers() {
    return apiClient.get('/api/v1/mcp-servers/available')
  },

  /**
   * Get a specific MCP server by ID
   */
  getServer(id: number) {
    return apiClient.get(`/api/v1/mcp-servers/${id}`)
  },

  /**
   * Create a new MCP server
   */
  createServer(config: {
    name: string
    display_name: string
    description?: string
    server_url: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
    max_retries?: number
    is_global?: boolean
  }) {
    return apiClient.post('/api/v1/mcp-servers', config)
  },

  /**
   * Update an existing MCP server
   */
  updateServer(id: number, config: {
    display_name?: string
    description?: string
    server_url?: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
    max_retries?: number
    is_global?: boolean
    is_active?: boolean
  }) {
    return apiClient.put(`/api/v1/mcp-servers/${id}`, config)
  },

  /**
   * Delete an MCP server
   */
  deleteServer(id: number) {
    return apiClient.delete(`/api/v1/mcp-servers/${id}`)
  },

  /**
   * Test connection to an MCP server (before saving)
   */
  testConnection(config: {
    server_url: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
  }) {
    return apiClient.post('/api/v1/mcp-servers/test', config)
  },

  /**
   * Refresh cached tools for an existing MCP server
   */
  refreshTools(id: number) {
    return apiClient.post(`/api/v1/mcp-servers/${id}/refresh-tools`)
  }
}
