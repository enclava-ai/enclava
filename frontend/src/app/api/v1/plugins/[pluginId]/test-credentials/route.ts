import { NextRequest, NextResponse } from 'next/server'

export async function POST(
  request: NextRequest,
  { params }: { params: { pluginId: string } }
) {
  try {
    // Extract authorization header from the incoming request
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      )
    }
    
    const body = await request.json()
    const { pluginId } = params
    
    // Make request to backend plugin test-credentials endpoint
    const baseUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL
    const url = `${baseUrl}/api/v1/plugins/${pluginId}/test-credentials`
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    })

    const data = await response.json()
    
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('Error testing plugin credentials:', error)
    return NextResponse.json(
      { error: 'Failed to test plugin credentials' },
      { status: 500 }
    )
  }
}