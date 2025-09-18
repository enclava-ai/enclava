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
      let details: any = undefined
      try { details = await res.json() } catch { details = await res.text() }
      const status = res.status
      if (status === 401) throw makeError('Unauthorized', 'UNAUTHORIZED', status, details)
      if (status === 403) throw makeError('Forbidden', 'FORBIDDEN', status, details)
      if (status === 404) throw makeError('Not found', 'NOT_FOUND', status, details)
      if (status === 400) throw makeError('Validation error', 'VALIDATION_ERROR', status, details)
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
  sendMessage(chatbotId: string, message: string, conversationId?: string, history?: Array<{role: string; content: string}>) {
    const body: any = { chatbot_id: chatbotId, message }
    if (conversationId) body.conversation_id = conversationId
    if (history) body.history = history
    return apiClient.post('/api-internal/v1/chatbot/chat', body)
  },
}

