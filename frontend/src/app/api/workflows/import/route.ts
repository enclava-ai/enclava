import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function POST(request: NextRequest) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const formData = await request.formData()
    const file = formData.get('workflow_file') as File

    if (!file) {
      return NextResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      )
    }

    // Check file type
    if (!file.name.endsWith('.json')) {
      return NextResponse.json(
        { error: 'Only JSON files are supported' },
        { status: 400 }
      )
    }

    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      return NextResponse.json(
        { error: 'File too large. Maximum size is 10MB' },
        { status: 400 }
      )
    }

    // Read file content
    const fileContent = await file.text()
    
    let workflowData
    try {
      workflowData = JSON.parse(fileContent)
    } catch (error) {
      return NextResponse.json(
        { error: 'Invalid JSON format' },
        { status: 400 }
      )
    }

    // Validate required fields
    const requiredFields = ['name', 'description', 'steps']
    for (const field of requiredFields) {
      if (!workflowData[field]) {
        return NextResponse.json(
          { error: `Missing required field: ${field}` },
          { status: 400 }
        )
      }
    }

    // Generate new ID if not provided
    if (!workflowData.id) {
      workflowData.id = `imported-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    }

    // Add import metadata
    workflowData.metadata = {
      ...workflowData.metadata,
      imported_at: new Date().toISOString(),
      imported_from: file.name,
      imported_by: 'user'
    }

    // Validate workflow through backend
    const validateResponse = await fetch(`${BACKEND_URL}/api/modules/workflow/execute`, {
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
        { 
          error: 'Workflow validation failed', 
          details: errorData.response?.errors || ['Unknown validation error'],
          workflow_data: workflowData
        },
        { status: 400 }
      )
    }

    const validationResult = await validateResponse.json()
    if (!validationResult.response?.valid) {
      return NextResponse.json(
        { 
          error: 'Workflow validation failed', 
          details: validationResult.response?.errors || ['Workflow is not valid'],
          workflow_data: workflowData
        },
        { status: 400 }
      )
    }

    // Create workflow via backend
    const createResponse = await fetch(`${BACKEND_URL}/api/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'create_workflow',
        workflow_def: workflowData
      })
    })

    if (!createResponse.ok) {
      const errorData = await createResponse.text()
      return NextResponse.json(
        { error: 'Failed to create workflow', details: errorData },
        { status: createResponse.status }
      )
    }

    const createData = await createResponse.json()
    return NextResponse.json({ 
      success: true,
      message: 'Workflow imported successfully',
      workflow: createData.response?.workflow || workflowData,
      validation_passed: true
    })

  } catch (error) {
    console.error('Error importing workflow:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}