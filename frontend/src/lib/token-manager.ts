type Listener = (...args: any[]) => void

class SimpleEmitter {
  private listeners = new Map<string, Set<Listener>>()

  on(event: string, listener: Listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set())
    this.listeners.get(event)!.add(listener)
  }

  off(event: string, listener: Listener) {
    this.listeners.get(event)?.delete(listener)
  }

  emit(event: string, ...args: any[]) {
    this.listeners.get(event)?.forEach(l => l(...args))
  }
}

interface StoredTokens {
  access_token: string
  refresh_token: string
  access_expires_at: number // epoch ms
  refresh_expires_at?: number // epoch ms
}

const ACCESS_LIFETIME_FALLBACK_MS = 30 * 60 * 1000 // 30 minutes
const REFRESH_LIFETIME_FALLBACK_MS = 7 * 24 * 60 * 60 * 1000 // 7 days

function now() { return Date.now() }

function readTokens(): StoredTokens | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem('auth_tokens')
    return raw ? JSON.parse(raw) as StoredTokens : null
  } catch {
    return null
  }
}

function writeTokens(tokens: StoredTokens | null) {
  if (typeof window === 'undefined') return
  if (tokens) {
    window.localStorage.setItem('auth_tokens', JSON.stringify(tokens))
  } else {
    window.localStorage.removeItem('auth_tokens')
  }
}

class TokenManager extends SimpleEmitter {
  private refreshTimer: ReturnType<typeof setTimeout> | null = null

  isAuthenticated(): boolean {
    const t = readTokens()
    return !!t && t.access_expires_at > now()
  }

  getTokenExpiry(): Date | null {
    const t = readTokens()
    return t ? new Date(t.access_expires_at) : null
  }

  getRefreshTokenExpiry(): Date | null {
    const t = readTokens()
    return t?.refresh_expires_at ? new Date(t.refresh_expires_at) : null
  }

  setTokens(accessToken: string, refreshToken: string, expiresInSeconds?: number) {
    const access_expires_at = now() + (expiresInSeconds ? expiresInSeconds * 1000 : ACCESS_LIFETIME_FALLBACK_MS)
    const refresh_expires_at = now() + REFRESH_LIFETIME_FALLBACK_MS
    const tokens: StoredTokens = {
      access_token: accessToken,
      refresh_token: refreshToken,
      access_expires_at,
      refresh_expires_at,
    }
    writeTokens(tokens)
    this.scheduleRefresh()
    this.emit('tokensUpdated')
  }

  clearTokens() {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
      this.refreshTimer = null
    }
    writeTokens(null)
    this.emit('tokensCleared')
  }

  logout() {
    this.clearTokens()
    this.emit('logout')
  }

  private scheduleRefresh() {
    if (typeof window === 'undefined') return
    const t = readTokens()
    if (!t) return
    if (this.refreshTimer) clearTimeout(this.refreshTimer)
    const msUntilRefresh = Math.max(5_000, t.access_expires_at - now() - 60_000) // 1 minute before expiry
    this.refreshTimer = setTimeout(() => {
      this.refreshAccessToken().catch(() => {
        this.emit('sessionExpired', 'refresh_failed')
        this.clearTokens()
      })
    }, msUntilRefresh)
  }

  async getAccessToken(): Promise<string | null> {
    const t = readTokens()
    if (!t) return null
    if (t.access_expires_at - now() > 10_000) return t.access_token
    try {
      await this.refreshAccessToken()
      return readTokens()?.access_token || null
    } catch {
      this.emit('sessionExpired', 'expired')
      this.clearTokens()
      return null
    }
  }

  private async refreshAccessToken(): Promise<void> {
    const t = readTokens()
    if (!t?.refresh_token) throw new Error('No refresh token')
    const res = await fetch('/api-internal/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: t.refresh_token }),
    })
    if (!res.ok) throw new Error('Refresh failed')
    const data = await res.json()
    const expiresIn = data.expires_in as number | undefined
    this.setTokens(data.access_token, data.refresh_token || t.refresh_token, expiresIn)
  }
}

export const tokenManager = new TokenManager()

