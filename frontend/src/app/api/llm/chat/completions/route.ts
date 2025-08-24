import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function POST(request: NextRequest) {
  try {
    // Get the request body
    const body = await request.json()
    
    const response = await proxyRequest('/api-internal/v1/llm/chat/completions', {
      method: 'POST',
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error' }))
      return NextResponse.json(errorData, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error in chat completions:', error)
    return NextResponse.json(
      { error: 'Failed to process chat completion' },
      { status: 500 }
    )
  }
}