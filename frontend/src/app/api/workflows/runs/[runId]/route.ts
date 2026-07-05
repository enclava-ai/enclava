import { NextRequest, NextResponse } from 'next/server'
import { proxyAuthenticatedRequest } from '@/lib/proxy-auth'

type RouteContext = {
  params: Promise<{ runId: string }> | { runId: string }
}

async function runIdFrom(context: RouteContext): Promise<string> {
  const params = await Promise.resolve(context.params)
  return params.runId
}

async function forwardResponse(response: Response): Promise<NextResponse> {
  const body = await response.text()
  return new NextResponse(body || null, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  })
}

export async function GET(request: NextRequest, context: RouteContext) {
  const runId = await runIdFrom(context)
  const response = await proxyAuthenticatedRequest(
    request,
    `/api-internal/v1/workflows/runs/${encodeURIComponent(runId)}`
  )
  return forwardResponse(response)
}

export async function POST(request: NextRequest, context: RouteContext) {
  const runId = await runIdFrom(context)
  const body = await request.json().catch(() => ({}))
  const action = body?.action
  const reason = typeof body?.reason === 'string' ? body.reason : undefined

  if (!['cancel', 'retry', 'execute'].includes(action)) {
    return NextResponse.json({ error: 'Unsupported workflow run action' }, { status: 400 })
  }

  const response = await proxyAuthenticatedRequest(
    request,
    `/api-internal/v1/workflows/runs/${encodeURIComponent(runId)}/${action}`,
    {
      method: 'POST',
      body: action === 'execute' ? undefined : JSON.stringify({ reason }),
    }
  )
  return forwardResponse(response)
}
