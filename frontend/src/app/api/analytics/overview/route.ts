import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET() {
  try {
    const response = await proxyRequest('/api-internal/v1/analytics/overview')
    const data = await handleProxyResponse(response, 'Failed to fetch analytics overview')
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching analytics overview:', error)
    return NextResponse.json(
      { error: 'Failed to fetch analytics overview' },
      { status: 500 }
    )
  }
}