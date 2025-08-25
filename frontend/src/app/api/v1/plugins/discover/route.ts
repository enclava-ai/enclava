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
    const query = searchParams.get('query') || ''
    const tags = searchParams.get('tags') || ''
    const category = searchParams.get('category') || ''
    const limit = searchParams.get('limit') || '20'
    
    // Build query string
    const queryParams = new URLSearchParams()
    if (query) queryParams.set('query', query)
    if (tags) queryParams.set('tags', tags)
    if (category) queryParams.set('category', category)
    if (limit) queryParams.set('limit', limit)
    
    // Make request to backend plugins discover endpoint
    const baseUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`
    const url = `${baseUrl}/api/plugins/discover?${queryParams.toString()}`
    
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
    console.error('Error discovering plugins:', error)
    return NextResponse.json(
      { error: 'Failed to discover plugins' },
      { status: 500 }
    )
  }
}