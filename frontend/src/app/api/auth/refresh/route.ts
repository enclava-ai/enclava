import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    // Get the request body (should contain refresh_token)
    const body = await request.json()
    
    // Make request to backend auth endpoint
    const baseUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`
    const url = `${baseUrl}/api/auth/refresh`
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
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
    return NextResponse.json(
      { error: 'Failed to refresh token' },
      { status: 500 }
    )
  }
}