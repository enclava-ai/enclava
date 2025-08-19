import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://shifra-backend:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const workflowId = params.id

    // Fetch workflow from the backend workflow module
    const response = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'get_workflow',
        workflow_id: workflowId
      }),
      cache: 'no-store'
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: 'Failed to fetch workflow', details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json({ 
      workflow: data.response?.workflow 
    })
  } catch (error) {
    console.error('Error fetching workflow:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const workflowId = params.id
    const workflowData = await request.json()

    // Validate workflow first
    const validateResponse = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'validate_workflow',
        workflow_def: workflowData
      })
    })

    if (!validateResponse.ok) {
      const errorData = await validateResponse.json()
      return NextResponse.json(
        { error: 'Workflow validation failed', details: errorData },
        { status: 400 }
      )
    }

    // Update workflow via backend workflow module
    const updateResponse = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'update_workflow',
        workflow_id: workflowId,
        workflow_def: workflowData
      })
    })

    if (!updateResponse.ok) {
      const errorData = await updateResponse.text()
      return NextResponse.json(
        { error: 'Failed to update workflow', details: errorData },
        { status: updateResponse.status }
      )
    }

    const updateData = await updateResponse.json()
    return NextResponse.json({ 
      workflow: updateData.response?.workflow 
    })
  } catch (error) {
    console.error('Error updating workflow:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const workflowId = params.id

    // Delete workflow via backend workflow module
    const response = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'delete_workflow',
        workflow_id: workflowId
      })
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: 'Failed to delete workflow', details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Check if the backend returned an error
    if (data.response?.error) {
      return NextResponse.json(
        { error: data.response.error },
        { status: 404 }
      )
    }
    
    return NextResponse.json({ 
      success: true,
      message: `Workflow ${workflowId} deleted successfully`,
      data: data.response
    })
  } catch (error) {
    console.error('Error deleting workflow:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}