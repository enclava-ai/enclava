import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://enclava-backend:8000'

export async function GET(request: NextRequest) {
  try {
    // Extract search params from the request
    const url = new URL(request.url)
    const searchParams = url.searchParams
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')
    
    // Build backend URL with query params
    const backendUrl = new URL(`${BACKEND_URL}/api/rag/documents`)
    searchParams.forEach((value, key) => {
      backendUrl.searchParams.append(key, value)
    })

    // Forward request to backend
    const backendResponse = await fetch(backendUrl.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader && { 'Authorization': authHeader }),
      },
    })

    if (!backendResponse.ok) {
      throw new Error(`Backend responded with ${backendResponse.status}`)
    }

    const data = await backendResponse.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { success: false, error: 'Failed to fetch documents' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    console.log('=== Document Upload API Route Called ===')

    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')
    console.log('Auth header present:', !!authHeader)

    // Get the original content type (includes multipart boundary)
    const contentType = request.headers.get('content-type')
    console.log('Original content type:', contentType)

    // Try to forward the original request body directly
    try {
      console.log('Request body type:', typeof request.body)
      console.log('Request body:', request.body)

      // Forward directly to backend with original body stream
      console.log('Sending request to backend:', `${BACKEND_URL}/api/rag/documents`)
      const backendResponse = await fetch(`${BACKEND_URL}/api/rag/documents`, {
        method: 'POST',
        headers: {
          ...(authHeader && { 'Authorization': authHeader }),
          ...(contentType && { 'Content-Type': contentType }),
        },
        body: request.body,
      })

      console.log('Backend response status:', backendResponse.status, backendResponse.statusText)

      if (!backendResponse.ok) {
        const errorData = await backendResponse.json().catch(() => ({ error: 'Unknown error' }))
        console.log('Backend error response:', errorData)
        return NextResponse.json(
          { success: false, error: errorData.detail || errorData.error || 'Failed to upload document' },
          { status: backendResponse.status }
        )
      }

      const data = await backendResponse.json()
      console.log('Backend success response:', data)
      return NextResponse.json(data)

    } catch (bodyError) {
      console.error('Error reading request body:', bodyError)
      throw bodyError
    }

  } catch (error) {
    console.error('Document upload error:', error)
    console.error('Error stack:', error.stack)
    return NextResponse.json(
      { success: false, error: 'Failed to upload document: ' + error.message },
      { status: 500 }
    )
  }
}