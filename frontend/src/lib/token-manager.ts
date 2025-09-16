import Cookies from 'js-cookie';
import { EventEmitter } from 'events';

interface TokenManagerEvents {
  tokensUpdated: [];
  tokensCleared: [];
}

export interface TokenManagerInterface {
  getTokens(): { access_token: string | null; refresh_token: string | null };
  setTokens(access_token: string, refresh_token: string): void;
  clearTokens(): void;
  isAuthenticated(): boolean;
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  getTokenExpiry(): { access_token_expiry: number | null; refresh_token_expiry: number | null };
  on<E extends keyof TokenManagerEvents>(
    event: E,
    listener: (...args: TokenManagerEvents[E]) => void
  ): this;
  off<E extends keyof TokenManagerEvents>(
    event: E,
    listener: (...args: TokenManagerEvents[E]) => void
  ): this;
}

class TokenManager extends EventEmitter implements TokenManagerInterface {
  private static instance: TokenManager;

  private constructor() {
    super();
    // Set max listeners to avoid memory leak warnings
    this.setMaxListeners(100);
  }

  static getInstance(): TokenManager {
    if (!TokenManager.instance) {
      TokenManager.instance = new TokenManager();
    }
    return TokenManager.instance;
  }

  getTokens() {
    return {
      access_token: Cookies.get('access_token'),
      refresh_token: Cookies.get('refresh_token'),
    };
  }

  setTokens(access_token: string, refresh_token: string) {
    // Set cookies with secure attributes
    Cookies.set('access_token', access_token, {
      expires: 7, // 7 days
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
    });

    Cookies.set('refresh_token', refresh_token, {
      expires: 30, // 30 days
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
    });

    // Emit event
    this.emit('tokensUpdated');
  }

  clearTokens() {
    Cookies.remove('access_token');
    Cookies.remove('refresh_token');
    this.emit('tokensCleared');
  }

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  getAccessToken(): string | null {
    return Cookies.get('access_token');
  }

  getRefreshToken(): string | null {
    return Cookies.get('refresh_token');
  }

  getTokenExpiry(): { access_token_expiry: number | null; refresh_token_expiry: number | null } {
    return {
      access_token_expiry: parseInt(Cookies.get('access_token_expiry') || '0') || null,
      refresh_token_expiry: parseInt(Cookies.get('refresh_token_expiry') || '0') || null,
    };
  }

  getRefreshTokenExpiry(): number | null {
    return parseInt(Cookies.get('refresh_token_expiry') || '0') || null;
  }
}

// Export singleton instance
export const tokenManager = TokenManager.getInstance();