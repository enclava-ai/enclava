import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function POST(
  request: NextRequest,
  { params }: { params: { name: string; action: string } }
) {
  try {
    const { name, action } = params
    
    const response = await proxyRequest(`/api/v1/modules/${name}/${action}`, { method: 'POST' })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: errorData || `Failed to ${action} module` },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Add flag to indicate modules state should be refreshed
    return NextResponse.json({
      ...data,
      refreshRequired: true
    })
  } catch (error) {
    console.error(`Error performing ${params.action} on module ${params.name}:`, error)
    return NextResponse.json(
      { error: `Failed to ${params.action} module` },
      { status: 500 }
    )
  }
}