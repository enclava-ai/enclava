import { NextRequest, NextResponse } from 'next/server';
import { tokenManager } from '@/lib/token-manager';

export async function POST(request: NextRequest) {
  try {
    // Get the search parameters from the query string
    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('query') || '';
    const max_results = searchParams.get('max_results') || '10';
    const score_threshold = searchParams.get('score_threshold') || '0.3';
    const collection_name = searchParams.get('collection_name');

    // Get the config from the request body
    const body = await request.json();

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

    // Build the proxy URL with query parameters
    const proxyUrl = `${backendUrl}/api-internal/v1/rag/debug/search?query=${encodeURIComponent(query)}&max_results=${max_results}&score_threshold=${score_threshold}${collection_name ? `&collection_name=${encodeURIComponent(collection_name)}` : ''}`;

    // Proxy the request to the backend with authentication
    const response = await fetch(proxyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend RAG search error:', response.status, errorText);
      return NextResponse.json(
        { error: `Backend request failed: ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('RAG debug search proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy RAG search request' },
      { status: 500 }
    );
  }
}