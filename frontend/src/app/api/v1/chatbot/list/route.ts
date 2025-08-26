import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function GET(request: NextRequest) {
  try {
    const token = request.headers.get('authorization')
    
    if (!token) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const response = await fetch(`${BACKEND_URL}/api/chatbot/list`, {
      method: 'GET',
      headers: {
        'Authorization': token,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: 'Failed to fetch chatbots', details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Transform the response to match expected format for plugin configuration
    const chatbots = Array.isArray(data) ? data : (data.chatbots || [])
    
    return NextResponse.json({
      chatbots: chatbots.map((chatbot: any) => ({
        id: chatbot.id,
        name: chatbot.name || 'Unnamed Chatbot',
        chatbot_type: chatbot.config?.chatbot_type || 'assistant',
        description: chatbot.description || '',
        created_at: chatbot.created_at,
        is_active: chatbot.is_active
      }))
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}