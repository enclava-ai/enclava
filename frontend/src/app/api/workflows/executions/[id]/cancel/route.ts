import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const executionId = params.id

    // Cancel execution via workflow module
    const response = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'cancel_execution',
        execution_id: executionId
      }),
      cache: 'no-store'
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: 'Failed to cancel execution', details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json({
      success: true,
      message: `Execution ${executionId} cancelled successfully`,
      data: data.response
    })
  } catch (error) {
    console.error('Error cancelling execution:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}