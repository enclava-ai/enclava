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
  const url = new URL(request.url)
  const resource = url.searchParams.get('resource')
  const query = new URLSearchParams(url.searchParams)
  query.delete('resource')
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const endpoint =
    resource === 'runs'
      ? `/api-internal/v1/workflows/operations/runs${suffix}`
      : resource === 'schedules'
        ? '/api-internal/v1/workflows/operations/schedules'
        : resource === 'templates'
          ? '/api-internal/v1/workflows/operations/templates'
          : '/api-internal/v1/workflows/operations'

  const response = await proxyAuthenticatedRequest(
    request,
    endpoint
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

  if (body?.action === 'enable' || body?.action === 'disable') {
    const response = await proxyAuthenticatedRequest(
      request,
      `/api-internal/v1/workflows/${encodeURIComponent(workflowId)}/${body.action}`,
      {
        method: 'POST',
        body: JSON.stringify({ reason: body?.reason }),
      }
    )
    return forwardResponse(response)
  }

  if (body?.action === 'preview_schedule') {
    const count = Number.isFinite(Number(body?.count)) ? Number(body.count) : 5
    const response = await proxyAuthenticatedRequest(
      request,
      `/api-internal/v1/workflows/${encodeURIComponent(workflowId)}/schedule/preview?count=${encodeURIComponent(String(count))}`,
      { method: 'POST' }
    )
    return forwardResponse(response)
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
