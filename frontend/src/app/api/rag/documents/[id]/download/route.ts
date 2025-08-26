import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://enclava-backend:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const documentId = params.id
    
    // Get auth token from request headers
    const authHeader = request.headers.get('authorization')

    // Forward request to backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/rag/documents/${documentId}/download`, {
      method: 'GET',
      headers: {
        ...(authHeader && { 'Authorization': authHeader }),
      },
    })

    if (!backendResponse.ok) {
      if (backendResponse.headers.get('content-type')?.includes('application/json')) {
        const errorData = await backendResponse.json().catch(() => ({ error: 'Unknown error' }))
        return NextResponse.json(
          { success: false, error: errorData.detail || errorData.error || 'Failed to download document' },
          { status: backendResponse.status }
        )
      } else {
        return NextResponse.json(
          { success: false, error: 'Document not found or file not available' },
          { status: backendResponse.status }
        )
      }
    }

    // Get the content and headers from backend response
    const contentType = backendResponse.headers.get('content-type') || 'application/octet-stream'
    const contentDisposition = backendResponse.headers.get('content-disposition')
    const contentLength = backendResponse.headers.get('content-length')

    // Stream the response from backend to client
    const headers = new Headers({
      'Content-Type': contentType,
      ...(contentDisposition && { 'Content-Disposition': contentDisposition }),
      ...(contentLength && { 'Content-Length': contentLength }),
    })

    return new NextResponse(backendResponse.body, { headers })
  } catch (error) {
    return NextResponse.json(
      { success: false, error: 'Failed to download document' },
      { status: 500 }
    )
  }
}