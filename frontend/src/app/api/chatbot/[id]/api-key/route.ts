import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const token = request.headers.get('authorization')
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/chatbot/${params.id}/api-key`, {
      method: 'POST',
      headers: {
        'Authorization': token,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(error, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error creating chatbot API key:', error)
    return NextResponse.json(
      { error: 'Failed to create chatbot API key' },
      { status: 500 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const token = request.headers.get('authorization')
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/chatbot/${params.id}/api-keys`, {
      method: 'GET',
      headers: {
        'Authorization': token,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(error, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error listing chatbot API keys:', error)
    return NextResponse.json(
      { error: 'Failed to list chatbot API keys' },
      { status: 500 }
    )
  }
}