import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'
const REQUEST_TIMEOUT = 30000 // 30 seconds

interface ChatRequestBody {
  chatbot_id: string
  message: string
  conversation_id?: string
}

function generateMessageId(): string {
  const timestamp = Date.now()
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `msg_${timestamp}_${random}`
}

export async function POST(request: NextRequest) {
  try {
    const token = request.headers.get('authorization')
    
    if (!token) {
      return NextResponse.json({ 
        error: 'Unauthorized',
        message: 'Authentication required' 
      }, { status: 401 })
    }

    let body: ChatRequestBody
    try {
      body = await request.json()
    } catch (error) {
      return NextResponse.json({ 
        error: 'Invalid JSON',
        message: 'Request body must be valid JSON' 
      }, { status: 400 })
    }
    
    // Validate request body
    const { chatbot_id, message, conversation_id } = body
    
    if (!chatbot_id || typeof chatbot_id !== 'string') {
      return NextResponse.json({ 
        error: 'Validation Error',
        message: 'chatbot_id is required and must be a string' 
      }, { status: 400 })
    }

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      return NextResponse.json({ 
        error: 'Validation Error',
        message: 'message is required and cannot be empty' 
      }, { status: 400 })
    }

    if (message.length > 4000) {
      return NextResponse.json({ 
        error: 'Validation Error',
        message: 'Message is too long (maximum 4000 characters)' 
      }, { status: 400 })
    }

    // Create request body for backend
    const backendBody = { 
      message: message.trim(), 
      conversation_id 
    }

    // Add timeout to backend request
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)

    let response: Response
    try {
      response = await fetch(`${BACKEND_URL}/api/v1/chatbot/chat/${encodeURIComponent(chatbot_id)}`, {
        method: 'POST',
        headers: {
          'Authorization': token,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendBody),
        signal: controller.signal,
      })
    } catch (fetchError: any) {
      if (fetchError.name === 'AbortError') {
        return NextResponse.json(
          { 
            error: 'Request Timeout',
            message: 'The request took too long to process. Please try again.'
          },
          { status: 408 }
        )
      }
      
      // Network or connection error
      return NextResponse.json(
        { 
          error: 'Service Unavailable',
          message: 'Unable to connect to the chatbot service. Please try again later.'
        },
        { status: 503 }
      )
    } finally {
      clearTimeout(timeoutId)
    }

    if (!response.ok) {
      let errorData: string
      try {
        const errorJson = await response.json()
        errorData = errorJson.detail || errorJson.error || errorJson.message || 'Unknown error'
      } catch {
        errorData = await response.text()
      }

      // Map backend status codes to appropriate frontend responses
      const errorMessage = response.status === 404 
        ? 'Chatbot not found or access denied'
        : response.status === 429
        ? 'Too many requests. Please wait a moment and try again.'
        : response.status >= 500
        ? 'Server error. Please try again in a moment.'
        : 'Failed to send message'

      return NextResponse.json(
        { 
          error: errorMessage,
          details: errorData 
        },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Ensure we have a message_id for frontend compatibility
    const messageId = data.message_id || generateMessageId()
    
    return NextResponse.json({
      ...data,
      message_id: messageId
    })
  } catch (error) {
    console.error('Error in chat API route:', error)
    return NextResponse.json(
      { 
        error: 'Internal Server Error',
        message: 'An unexpected error occurred. Please try again.'
      },
      { status: 500 }
    )
  }
}