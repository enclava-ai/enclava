import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function GET(request: NextRequest) {
  try {
    const token = request.headers.get('authorization')
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/prompt-templates/variables`, {
      headers: {
        'Authorization': token,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching prompt variables:', error)
    return NextResponse.json(
      { error: 'Failed to fetch prompt variables' },
      { status: 500 }
    )
  }
}