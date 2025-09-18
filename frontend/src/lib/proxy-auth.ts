const BACKEND_URL = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`

function mapPath(path: string): string {
  // Convert '/api-internal/..' to backend '/api/..'
  if (path.startsWith('/api-internal/')) {
    return path.replace('/api-internal/', '/api/')
  }
  return path
}

export async function proxyRequest(path: string, init?: RequestInit): Promise<Response> {
  const url = `${BACKEND_URL}${mapPath(path)}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  return fetch(url, { ...init, headers })
}

export async function handleProxyResponse<T = any>(response: Response, defaultMessage = 'Request failed'): Promise<T> {
  if (!response.ok) {
    let details: any
    try { details = await response.json() } catch { details = await response.text() }
    throw new Error(typeof details === 'string' ? `${defaultMessage}: ${details}` : (details?.error || defaultMessage))
  }
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return (await response.json()) as T
  // @ts-ignore allow non-json
  return (await response.text()) as T
}

