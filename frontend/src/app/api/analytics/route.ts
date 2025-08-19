import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET() {
  try {
    const response = await proxyRequest('/api/v1/analytics/')
    const data = await handleProxyResponse(response, 'Failed to fetch analytics')
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching analytics:', error)
    return NextResponse.json(
      { error: 'Failed to fetch analytics' },
      { status: 500 }
    )
  }
}