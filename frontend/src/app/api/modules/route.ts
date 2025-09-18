import { NextRequest, NextResponse } from 'next/server'
import { apiClient } from '@/lib/api-client'

export async function GET() {
  try {
    // Use the authenticated API client which handles JWT tokens automatically
    const data = await apiClient.get('/modules/')

    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch modules' },
      { status: 500 }
    )
  }
}