import { NextRequest, NextResponse } from 'next/server'
import { proxyAuthenticatedRequest } from '@/lib/proxy-auth'

async function forwardResponse(response: Response): Promise<NextResponse> {
  const body = await response.text()
  return new NextResponse(body || null, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  })
}

export async function GET(request: NextRequest) {
  const response = await proxyAuthenticatedRequest(
    request,
    '/api-internal/v1/workflows/operations'
  )
  return forwardResponse(response)
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const workflowId = typeof body?.workflow_id === 'string' ? body.workflow_id : ''

  if (!workflowId) {
    return NextResponse.json(
      { success: false, error: 'workflow_id is required' },
      { status: 400 }
    )
  }

  const response = await proxyAuthenticatedRequest(
    request,
    `/api-internal/v1/workflows/${encodeURIComponent(workflowId)}/runs`,
    {
      method: 'POST',
      body: JSON.stringify({
        input_data: body?.input_data || {},
        execute_now: true,
      }),
    }
  )
  return forwardResponse(response)
}
