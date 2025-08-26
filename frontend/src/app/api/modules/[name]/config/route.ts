import { NextRequest, NextResponse } from 'next/server'
import { proxyRequest, handleProxyResponse } from '@/lib/proxy-auth'

export async function GET(
  request: NextRequest,
  { params }: { params: { name: string } }
) {
  try {
    const { name } = params
    
    const response = await proxyRequest(`/api-internal/v1/modules/${name}/config`)

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}: ${response.statusText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch module configuration' },
      { status: 500 }
    )
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: { name: string } }
) {
  try {
    const { name } = params
    const config = await request.json()
    
    const response = await proxyRequest(`/api-internal/v1/modules/${name}/config`, {
      method: 'POST',
      body: JSON.stringify(config)
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: errorData || 'Failed to update module configuration' },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Trigger module refresh
    return NextResponse.json({
      ...data,
      refreshRequired: true
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to update module configuration' },
      { status: 500 }
    )
  }
}