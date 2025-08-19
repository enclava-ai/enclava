import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://enclava-backend:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const adminToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzg0Nzk2NDI2LjA0NDYxOX0.YOTlUY8nowkaLAXy5EKfnZEpbDgGCabru5R0jdq_DOQ'

    const templateId = params.id

    // First get all templates
    const response = await fetch(`${BACKEND_URL}/api/v1/modules/workflow/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'get_workflow_templates'
      })
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: 'Failed to fetch workflow templates', details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    const templates = data.templates || []
    
    // Find the specific template
    const template = templates.find((t: any) => t.id === templateId)
    
    if (!template) {
      return NextResponse.json(
        { error: `Template with id '${templateId}' not found` },
        { status: 404 }
      )
    }

    return NextResponse.json({ template })
  } catch (error) {
    console.error('Error fetching workflow template:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}