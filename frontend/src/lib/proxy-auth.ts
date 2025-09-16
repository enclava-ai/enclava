import { NextRequest, NextResponse } from 'next/server';

// This is a proxy auth utility for server-side API routes
// It handles authentication and proxying requests to the backend

export interface ProxyAuthConfig {
  backendUrl: string;
  requireAuth?: boolean;
  allowedRoles?: string[];
}

export class ProxyAuth {
  private config: ProxyAuthConfig;

  constructor(config: ProxyAuthConfig) {
    this.config = {
      requireAuth: true,
      ...config,
    };
  }

  async authenticate(request: NextRequest): Promise<{ success: boolean; user?: any; error?: string }> {
    // For server-side auth, we would typically validate the token
    // This is a simplified implementation
    const authHeader = request.headers.get('authorization');

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return { success: false, error: 'Missing or invalid authorization header' };
    }

    const token = authHeader.substring(7);

    // Here you would validate the token with your auth service
    // For now, we'll just check if it exists
    if (!token) {
      return { success: false, error: 'Invalid token' };
    }

    // In a real implementation, you would decode and validate the JWT
    // and check user roles if required
    return {
      success: true,
      user: {
        id: 'user-id',
        email: 'user@example.com',
        role: 'user'
      }
    };
  }

  async proxyRequest(
    request: NextRequest,
    path: string,
    options?: {
      method?: string;
      headers?: Record<string, string>;
      body?: any;
    }
  ): Promise<NextResponse> {
    // Authenticate the request if required
    if (this.config.requireAuth) {
      const authResult = await this.authenticate(request);
      if (!authResult.success) {
        return NextResponse.json(
          { error: authResult.error || 'Authentication failed' },
          { status: 401 }
        );
      }

      // Check roles if specified
      if (this.config.allowedRoles && authResult.user) {
        if (!this.config.allowedRoles.includes(authResult.user.role)) {
          return NextResponse.json(
            { error: 'Insufficient permissions' },
            { status: 403 }
          );
        }
      }
    }

    // Build the target URL
    const targetUrl = new URL(path, this.config.backendUrl);

    // Copy query parameters
    targetUrl.search = request.nextUrl.search;

    // Prepare headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options?.headers,
    };

    // Forward authorization header if present
    const authHeader = request.headers.get('authorization');
    if (authHeader) {
      headers.authorization = authHeader;
    }

    try {
      const response = await fetch(targetUrl, {
        method: options?.method || request.method,
        headers,
        body: options?.body ? JSON.stringify(options.body) : request.body,
      });

      // Create a new response with the data
      const data = await response.json();

      return NextResponse.json(data, {
        status: response.status,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    } catch (error) {
      console.error('Proxy request failed:', error);
      return NextResponse.json(
        { error: 'Internal server error' },
        { status: 500 }
      );
    }
  }
}

// Utility function to create a proxy handler
export function createProxyHandler(config: ProxyAuthConfig) {
  const proxyAuth = new ProxyAuth(config);

  return async (request: NextRequest, { params }: { params: { path?: string[] } }) => {
    const path = params?.path ? params.path.join('/') : '';
    return proxyAuth.proxyRequest(request, path);
  };
}

// Simplified proxy request function for direct usage
export async function proxyRequest(
  request: NextRequest,
  backendUrl: string,
  path: string = '',
  options?: {
    method?: string;
    headers?: Record<string, string>;
    body?: any;
    requireAuth?: boolean;
  }
): Promise<NextResponse> {
  const proxyAuth = new ProxyAuth({
    backendUrl,
    requireAuth: options?.requireAuth ?? true,
  });

  return proxyAuth.proxyRequest(request, path, options);
}

// Helper function to handle proxy responses with error handling
export async function handleProxyResponse(
  request: NextRequest,
  backendUrl: string,
  path: string = '',
  options?: {
    method?: string;
    headers?: Record<string, string>;
    body?: any;
    requireAuth?: boolean;
  }
): Promise<NextResponse> {
  try {
    return await proxyRequest(request, backendUrl, path, options);
  } catch (error) {
    console.error('Proxy request failed:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}