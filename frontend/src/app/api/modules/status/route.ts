import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET() {
  try {
    const response = await proxyRequest('/api-internal/v1/modules/status')
    
    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}: ${response.statusText}`)
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching modules status:', error)
    return NextResponse.json(
      { error: 'Failed to fetch modules status' },
      { status: 500 }
    )
  }
}