import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function POST(request: NextRequest) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const { workflow, test_data } = await request.json()

    // First validate the workflow
    const validateResponse = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'validate_workflow',
        workflow_def: workflow
      })
    })

    if (!validateResponse.ok) {
      const errorData = await validateResponse.json()
      return NextResponse.json(
        { 
          status: 'failed',
          error: 'Workflow validation failed', 
          details: errorData 
        },
        { status: 400 }
      )
    }

    // If validation passes, try a test execution
    const executeResponse = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'execute_workflow',
        workflow_def: workflow,
        input_data: test_data || {}
      })
    })

    if (!executeResponse.ok) {
      const errorData = await executeResponse.text()
      return NextResponse.json(
        { 
          status: 'failed',
          error: 'Workflow test execution failed', 
          details: errorData 
        },
        { status: 500 }
      )
    }

    const executionData = await executeResponse.json()
    return NextResponse.json({ 
      status: 'success',
      execution: executionData
    })
  } catch (error) {
    console.error('Error testing workflow:', error)
    return NextResponse.json(
      { 
        status: 'failed',
        error: 'Internal server error' 
      },
      { status: 500 }
    )
  }
}