import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    // Extract authorization header from the incoming request
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      )
    }
    
    // Get query parameters
    const { searchParams } = new URL(request.url)
    const limit = searchParams.get('limit')
    const offset = searchParams.get('offset')
    
    // Build query string
    const queryParams = new URLSearchParams()
    if (limit) queryParams.set('limit', limit)
    if (offset) queryParams.set('offset', offset)
    
    // Make request to backend Zammad processing-logs endpoint
    const baseUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`
    const url = `${baseUrl}/api/zammad/processing-logs?${queryParams.toString()}`
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()
    
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch Zammad processing logs' },
      { status: 500 }
    )
  }
}