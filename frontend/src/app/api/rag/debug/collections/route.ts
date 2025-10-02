import { NextRequest, NextResponse } from 'next/server';
import { tokenManager } from '@/lib/token-manager';

export async function GET(request: NextRequest) {
  try {
    // Get authentication token from Authorization header or tokenManager
    const authHeader = request.headers.get('authorization');
    let token;

    if (authHeader && authHeader.startsWith('Bearer ')) {
      token = authHeader.substring(7);
    } else {
      token = await tokenManager.getAccessToken();
    }

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Backend URL
    const backendUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`;

    // Build the proxy URL
    const proxyUrl = `${backendUrl}/api-internal/v1/rag/debug/collections`;

    // Proxy the request to the backend with authentication
    const response = await fetch(proxyUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend list collections error:', response.status, errorText);
      return NextResponse.json(
        { error: `Backend request failed: ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('RAG collections proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy collections request' },
      { status: 500 }
    );
  }
}