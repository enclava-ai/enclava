import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET(request: NextRequest) {
  try {
    // Get query parameters from the request
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()
    const endpoint = `/api/v1/audit${queryString ? `?${queryString}` : ''}`
    
    const response = await proxyRequest(endpoint)
    const data = await handleProxyResponse(response, 'Failed to fetch audit logs')
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching audit logs:', error)
    return NextResponse.json(
      { error: 'Failed to fetch audit logs' },
      { status: 500 }
    )
  }
}