import { NextRequest, NextResponse } from 'next/server'

export async function PUT(
  request: NextRequest,
  { params }: { params: { category: string } }
) {
  try {
    // Extract authorization header from the incoming request
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      )
    }
    
    const { category } = params
    const body = await request.json()
    
    // Get backend API base URL
    const baseUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`
    
    // Update each setting in the category individually
    const results = []
    const errors = []
    
    for (const [key, value] of Object.entries(body)) {
      try {
        const url = `${baseUrl}/api/settings/${category}/${key}`
        const response = await fetch(url, {
          method: 'PUT',
          headers: {
            'Authorization': authHeader,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            value: value,
            description: `Updated via settings UI`
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          results.push({ key, success: true, data })
        } else {
          const errorData = await response.json()
          errors.push({ key, error: errorData.detail || 'Update failed' })
        }
      } catch (error) {
        errors.push({ key, error: `Request failed: ${error}` })
      }
    }
    
    // Return success if most updates succeeded
    if (errors.length === 0) {
      return NextResponse.json({
        success: true,
        message: `${category} settings updated successfully`,
        updated: results.length
      })
    } else if (results.length > 0) {
      // Partial success
      return NextResponse.json({
        success: true,
        message: `${results.length} settings updated, ${errors.length} failed`,
        updated: results.length,
        errors: errors
      }, { status: 207 }) // Multi-status
    } else {
      // All failed
      return NextResponse.json({
        success: false,
        message: `Failed to update ${category} settings`,
        errors: errors
      }, { status: 400 })
    }
    
  } catch (error) {
    console.error(`Error updating ${params.category} settings:`, error)
    return NextResponse.json(
      { error: 'Failed to update category settings' },
      { status: 500 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { category: string } }
) {
  try {
    // Extract authorization header from the incoming request
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json(
        { error: 'Authorization header required' },
        { status: 401 }
      )
    }
    
    const { category } = params
    
    // Get backend API base URL
    const baseUrl = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}`
    const url = `${baseUrl}/api/settings?category=${category}`
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()
    
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status })
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error(`Error fetching ${params.category} settings:`, error)
    return NextResponse.json(
      { error: 'Failed to fetch category settings' },
      { status: 500 }
    )
  }
}