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
  const templateId = url.searchParams.get('template_id')
  const stepType = url.searchParams.get('step_type')
  const workflowId = url.searchParams.get('workflow_id')

  if (resource === 'template' && !templateId) {
    return NextResponse.json(
      { success: false, error: 'template_id is required' },
      { status: 400 }
    )
  }
  if (resource === 'catalog_entry' && !stepType) {
    return NextResponse.json(
      { success: false, error: 'step_type is required' },
      { status: 400 }
    )
  }
  if (resource === 'workflow' && !workflowId) {
    return NextResponse.json(
      { success: false, error: 'workflow_id is required' },
      { status: 400 }
    )
  }

  let endpoint = '/api-internal/v1/workflows/operations'
  if (resource === 'workflow') {
    endpoint = `/api-internal/v1/workflows/${encodeURIComponent(workflowId || '')}`
  } else if (resource === 'runs') {
    endpoint = `/api-internal/v1/workflows/operations/runs${suffix}`
  } else if (resource === 'schedules') {
    endpoint = '/api-internal/v1/workflows/operations/schedules'
  } else if (resource === 'templates') {
    endpoint = '/api-internal/v1/workflows/operations/templates'
  } else if (resource === 'template_catalog') {
    endpoint = '/api-internal/v1/workflows/templates'
  } else if (resource === 'template') {
    endpoint = `/api-internal/v1/workflows/templates/${encodeURIComponent(templateId || '')}`
  } else if (resource === 'catalog') {
    endpoint = '/api-internal/v1/workflows/steps/catalog'
  } else if (resource === 'catalog_entry') {
    endpoint = `/api-internal/v1/workflows/steps/catalog/${encodeURIComponent(stepType || '')}`
  }

  const response = await proxyAuthenticatedRequest(
    request,
    endpoint
  )
  return forwardResponse(response)
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const workflowId = typeof body?.workflow_id === 'string' ? body.workflow_id : ''

  if (body?.action === 'validate_definition') {
    const response = await proxyAuthenticatedRequest(
      request,
      '/api-internal/v1/workflows/steps/validate',
      {
        method: 'POST',
        body: JSON.stringify(body?.definition || {}),
      }
    )
    return forwardResponse(response)
  }

  if (body?.action === 'preview_schedule_definition') {
    const response = await proxyAuthenticatedRequest(
      request,
      '/api-internal/v1/workflows/schedule/preview',
      {
        method: 'POST',
        body: JSON.stringify({
          cron: body?.cron,
          timezone: body?.timezone,
          count: body?.count,
          start_at: body?.start_at,
        }),
      }
    )
    return forwardResponse(response)
  }

  if (body?.action === 'create') {
    const response = await proxyAuthenticatedRequest(
      request,
      '/api-internal/v1/workflows/',
      {
        method: 'POST',
        body: JSON.stringify({
          name: body?.name,
          description: body?.description,
          definition: body?.definition,
          tags: body?.tags || [],
          metadata: body?.metadata || {},
        }),
      }
    )
    return forwardResponse(response)
  }

  if (!workflowId) {
    return NextResponse.json(
      { success: false, error: 'workflow_id is required' },
      { status: 400 }
    )
  }

  if (body?.action === 'update') {
    const payload: Record<string, unknown> = {}
    if (body?.name !== undefined) payload.name = body.name
    if (body?.description !== undefined) payload.description = body.description
    if (body?.definition !== undefined) payload.definition = body.definition
    if (body?.tags !== undefined) payload.tags = body.tags
    if (body?.metadata !== undefined) payload.metadata = body.metadata

    const response = await proxyAuthenticatedRequest(
      request,
      `/api-internal/v1/workflows/${encodeURIComponent(workflowId)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      }
    )
    return forwardResponse(response)
  }

  if (body?.action === 'publish') {
    const response = await proxyAuthenticatedRequest(
      request,
      `/api-internal/v1/workflows/${encodeURIComponent(workflowId)}/publish`,
      {
        method: 'POST',
        body: JSON.stringify({ reason: body?.reason }),
      }
    )
    return forwardResponse(response)
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
