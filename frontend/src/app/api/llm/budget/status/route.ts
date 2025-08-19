import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET() {
  try {
    const response = await proxyRequest('/api/v1/llm/budget/status')
    const data = await handleProxyResponse(response, 'Failed to fetch budget status')
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching budget status:', error)
    return NextResponse.json(
      { error: 'Failed to fetch budget status' },
      { status: 500 }
    )
  }
}