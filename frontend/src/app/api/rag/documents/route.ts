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
    const backendUrl = new URL(`${BACKEND_URL}/api/v1/rag/documents`)
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
    console.error('Error fetching documents:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to fetch documents' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')

    // Forward the FormData directly to backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/rag/documents`, {
      method: 'POST',
      headers: {
        ...(authHeader && { 'Authorization': authHeader }),
        // Don't set Content-Type for FormData - let the browser set it with boundary
      },
      body: formData,
    })

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({ error: 'Unknown error' }))
      return NextResponse.json(
        { success: false, error: errorData.detail || errorData.error || 'Failed to upload document' },
        { status: backendResponse.status }
      )
    }

    const data = await backendResponse.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error uploading document:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to upload document' },
      { status: 500 }
    )
  }
}