import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://enclava-backend:8000'

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const documentId = params.id
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')

    // Forward request to backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/rag/documents/${documentId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader && { 'Authorization': authHeader }),
      },
    })

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({ error: 'Unknown error' }))
      return NextResponse.json(
        { success: false, error: errorData.detail || errorData.error || 'Failed to delete document' },
        { status: backendResponse.status }
      )
    }

    const data = await backendResponse.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error deleting document:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to delete document' },
      { status: 500 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const documentId = params.id
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')

    // Forward request to backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/rag/documents/${documentId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader && { 'Authorization': authHeader }),
      },
    })

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({ error: 'Unknown error' }))
      return NextResponse.json(
        { success: false, error: errorData.detail || errorData.error || 'Failed to fetch document' },
        { status: backendResponse.status }
      )
    }

    const data = await backendResponse.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching document:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to fetch document' },
      { status: 500 }
    )
  }
}