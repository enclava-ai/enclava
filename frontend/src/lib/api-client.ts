
export interface AppError extends Error {
  code: 'UNAUTHORIZED' | 'NETWORK_ERROR' | 'VALIDATION_ERROR' | 'NOT_FOUND' | 'FORBIDDEN' | 'TIMEOUT' | 'UNKNOWN'
  status?: number
  details?: any
}

function makeError(message: string, code: AppError['code'], status?: number, details?: any): AppError {
  const err = new Error(message) as AppError
  err.code = code
  err.status = status
  err.details = details
  return err
}

async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const { tokenManager } = await import('./token-manager')
    const token = await tokenManager.getAccessToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

async function request<T = any>(method: string, url: string, body?: any, extraInit?: RequestInit): Promise<T> {
  try {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      ...(method !== 'GET' && method !== 'HEAD' ? { 'Content-Type': 'application/json' } : {}),
      ...(await getAuthHeader()),
      ...(extraInit?.headers as Record<string, string> | undefined),
    }

    const res = await fetch(url, {
      method,
      headers,
      body: body != null && method !== 'GET' && method !== 'HEAD' ? JSON.stringify(body) : undefined,
      ...extraInit,
    })

    if (!res.ok) {
      // Read the body once to avoid "Body has already been consumed" errors on non-JSON responses
      const rawBody = await res.text().catch(() => '')
      let details: any = undefined
      try { details = rawBody ? JSON.parse(rawBody) : undefined } catch { details = rawBody }
      const status = res.status
      if (status === 401) throw makeError('Unauthorized', 'UNAUTHORIZED', status, details)
      if (status === 403) throw makeError('Forbidden', 'FORBIDDEN', status, details)
      if (status === 404) throw makeError('Not found', 'NOT_FOUND', status, details)
      if (status === 400 || status === 422) throw makeError('Validation error', 'VALIDATION_ERROR', status, details)
      throw makeError('Request failed', 'UNKNOWN', status, details)
    }

    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      return (await res.json()) as T
    }
    // @ts-expect-error allow non-json generic
    return (await res.text()) as T
  } catch (e: any) {
    if (e?.code) throw e
    if (e?.name === 'AbortError') throw makeError('Request timed out', 'TIMEOUT')
    throw makeError(e?.message || 'Network error', 'NETWORK_ERROR')
  }
}

export const apiClient = {
  get: <T = any>(url: string, init?: RequestInit) => request<T>('GET', url, undefined, init),
  post: <T = any>(url: string, body?: any, init?: RequestInit) => request<T>('POST', url, body, init),
  put: <T = any>(url: string, body?: any, init?: RequestInit) => request<T>('PUT', url, body, init),
  patch: <T = any>(url: string, body?: any, init?: RequestInit) => request<T>('PATCH', url, body, init),
  delete: <T = any>(url: string, init?: RequestInit) => request<T>('DELETE', url, undefined, init),
}

export const agentApi = {
  listAgents(params?: { category?: string; is_public?: boolean }) {
    const queryParams = new URLSearchParams()
    if (params?.category) queryParams.append('category', params.category)
    if (params?.is_public !== undefined) queryParams.append('is_public', String(params.is_public))
    const query = queryParams.toString()
    return apiClient.get(`/agent/configs${query ? `?${query}` : ''}`)
  },
  getAgent(id: number) {
    return apiClient.get(`/agent/configs/${id}`)
  },
  createAgent(config: any) {
    return apiClient.post('/agent/configs', config)
  },
  updateAgent(id: number, config: any) {
    return apiClient.put(`/agent/configs/${id}`, config)
  },
  deleteAgent(id: number) {
    return apiClient.delete(`/agent/configs/${id}`)
  },
  // OpenAI-compatible chat completions (internal, JWT auth)
  chat(agentConfigId: number, messages: Array<{role: string; content: string}>, options?: {
    temperature?: number
    max_tokens?: number
  }) {
    return apiClient.post(`/agent/${agentConfigId}/chat/completions`, {
      messages,
      ...options
    })
  },
  // Simple chat helper - wraps a single message in OpenAI format
  sendMessage(agentConfigId: number, message: string, history?: Array<{role: string; content: string}>) {
    const messages = [
      ...(history || []),
      { role: 'user', content: message }
    ]
    return apiClient.post(`/agent/${agentConfigId}/chat/completions`, { messages })
  }
}

export interface RagCollectionSummary {
  id: string | number
  name: string
  description?: string | null
  status?: string | null
  document_count?: number
  vector_count?: number
  is_managed?: boolean
  source?: string | null
}

export interface RagCollectionsApiResponse {
  success?: boolean
  collections: RagCollectionSummary[]
}

export const ragApi = {
  listCollections() {
    return apiClient.get<RagCollectionsApiResponse>('/api/rag/collections')
  },
}

export const toolApi = {
  listTools() {
    return apiClient.get('/api/v1/tool-calling/available')
  }
}

export const mcpServerApi = {
  /**
   * List all MCP servers accessible to the current user
   */
  listServers(includeInactive?: boolean) {
    const params = includeInactive ? '?include_inactive=true' : ''
    return apiClient.get(`/api/v1/mcp-servers${params}`)
  },

  /**
   * Get simplified list for agent configuration dropdowns
   */
  getAvailableServers() {
    return apiClient.get('/api/v1/mcp-servers/available')
  },

  /**
   * Get a specific MCP server by ID
   */
  getServer(id: number) {
    return apiClient.get(`/api/v1/mcp-servers/${id}`)
  },

  /**
   * Create a new MCP server
   */
  createServer(config: {
    name: string
    display_name: string
    description?: string
    server_url: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
    max_retries?: number
    is_global?: boolean
  }) {
    return apiClient.post('/api/v1/mcp-servers', config)
  },

  /**
   * Update an existing MCP server
   */
  updateServer(id: number, config: {
    display_name?: string
    description?: string
    server_url?: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
    max_retries?: number
    is_global?: boolean
    is_active?: boolean
  }) {
    return apiClient.put(`/api/v1/mcp-servers/${id}`, config)
  },

  /**
   * Delete an MCP server
   */
  deleteServer(id: number) {
    return apiClient.delete(`/api/v1/mcp-servers/${id}`)
  },

  /**
   * Test connection to an MCP server (before saving)
   */
  testConnection(config: {
    server_url: string
    api_key?: string
    api_key_header_name?: string
    timeout_seconds?: number
  }) {
    return apiClient.post('/api/v1/mcp-servers/test', config)
  },

  /**
   * Refresh cached tools for an existing MCP server
   */
  refreshTools(id: number) {
    return apiClient.post(`/api/v1/mcp-servers/${id}/refresh-tools`)
  }
}

export const extractApi = {
  /**
   * List all extraction templates
   */
  listTemplates() {
    return apiClient.get('/api/v1/extract/templates')
  },

  /**
   * Get a specific template by ID
   */
  getTemplate(templateId: string) {
    return apiClient.get(`/api/v1/extract/templates/${encodeURIComponent(templateId)}`)
  },

  /**
   * Create a new extraction template
   */
  createTemplate(template: {
    id: string
    description?: string
    system_prompt: string
    user_prompt: string
    output_schema?: any
    model?: string
  }) {
    return apiClient.post('/api/v1/extract/templates', template)
  },

  /**
   * Update an existing template
   */
  updateTemplate(templateId: string, updates: {
    description?: string
    system_prompt?: string
    user_prompt?: string
    output_schema?: any
    model?: string | null
  }) {
    return apiClient.put(`/api/v1/extract/templates/${encodeURIComponent(templateId)}`, updates)
  },

  /**
   * Delete a template
   */
  deleteTemplate(templateId: string) {
    return apiClient.delete(`/api/v1/extract/templates/${encodeURIComponent(templateId)}`)
  },

  /**
   * Reset default templates to their original state
   */
  resetDefaults() {
    return apiClient.post('/api/v1/extract/templates/reset-defaults')
  },

  /**
   * Template wizard - analyze a document and generate a template
   */
  async analyzeDocumentForTemplate(file: File, model?: string) {
    const formData = new FormData()
    formData.append('file', file)
    if (model) {
      formData.append('model', model)
    }

    const headers = await getAuthHeader()
    const res = await fetch('/api/v1/extract/templates/wizard', {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!res.ok) {
      const rawBody = await res.text().catch(() => '')
      let details: any = undefined
      try { details = rawBody ? JSON.parse(rawBody) : undefined } catch { details = rawBody }
      throw makeError('Template wizard failed', 'UNKNOWN', res.status, details)
    }

    return res.json()
  },

  /**
   * Get available models from the LLM service (internal API with JWT auth)
   */
  async getModels() {
    const headers = await getAuthHeader()
    const res = await fetch('/api-internal/v1/llm/models', {
      method: 'GET',
      headers,
    })

    if (!res.ok) {
      const rawBody = await res.text().catch(() => '')
      let details: any = undefined
      try { details = rawBody ? JSON.parse(rawBody) : undefined } catch { details = rawBody }
      throw makeError('Failed to fetch models', 'UNKNOWN', res.status, details)
    }

    return res.json()
  },

  /**
   * Process a document with Extract
   */
  async processDocument(file: File, template?: string, context?: Record<string, any>) {
    const formData = new FormData()
    formData.append('file', file)
    if (template) formData.append('template', template)
    if (context) formData.append('context', JSON.stringify(context))

    const headers = await getAuthHeader()
    const res = await fetch('/api/v1/extract/process', {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!res.ok) {
      const rawBody = await res.text().catch(() => '')
      let details: any = undefined
      try { details = rawBody ? JSON.parse(rawBody) : undefined } catch { details = rawBody }
      throw makeError('Processing failed', 'UNKNOWN', res.status, details)
    }

    return res.json()
  },

  /**
   * List Extract jobs for the current user
   */
  listJobs(params?: { limit?: number; offset?: number; status?: string }) {
    const queryParams = new URLSearchParams()
    if (params?.limit) queryParams.append('limit', String(params.limit))
    if (params?.offset) queryParams.append('offset', String(params.offset))
    if (params?.status) queryParams.append('status', params.status)
    const query = queryParams.toString()
    return apiClient.get(`/api/v1/extract/jobs${query ? `?${query}` : ''}`)
  },

  /**
   * Get job details and extraction result
   */
  getJob(jobId: string) {
    return apiClient.get(`/api/v1/extract/jobs/${jobId}`)
  },

  /**
   * Health check for Extract
   */
  health() {
    return apiClient.get('/api/v1/extract/health')
  }
}

export type WorkflowRunStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'paused'
  | 'skipped'

export type WorkflowHealthState =
  | 'healthy'
  | 'disabled'
  | 'running'
  | 'failed'
  | 'missed'
  | 'no_schedule'

export type WorkflowTriggerType =
  | 'manual'
  | 'schedule'
  | 'event'
  | 'api'

export type WorkflowDefinitionStatus =
  | 'draft'
  | 'active'
  | 'disabled'
  | 'archived'

export type WorkflowStepRunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped'
  | 'retrying'
  | 'cancelled'

export type WorkflowConcurrencyPolicy =
  | 'skip_if_running'
  | 'queue_after_current'
  | 'allow_parallel'

export type WorkflowMisfirePolicy =
  | 'skip'
  | 'run_once'
  | 'catch_up'

export type WorkflowRedactionPolicy =
  | 'default'
  | 'strict'
  | 'none'

export interface WorkflowRetryPolicy {
  max_attempts?: number
  backoff_seconds?: number
}

export interface WorkflowRuntimePolicy {
  concurrency_policy?: WorkflowConcurrencyPolicy
  timeout_seconds?: number
  budget_limit_cents?: number | null
  redaction_policy?: WorkflowRedactionPolicy
}

export interface WorkflowTriggerDefinition {
  type: WorkflowTriggerType
  cron?: string | null
  timezone?: string | null
  misfire_policy?: WorkflowMisfirePolicy
  catchup_limit?: number | null
  event_name?: string | null
  api_slug?: string | null
  config?: Record<string, any>
}

export interface WorkflowStepDefinition {
  key: string
  type: string
  name: string
  config: Record<string, any>
  depends_on?: string[]
  retry?: WorkflowRetryPolicy
  timeout_seconds?: number | null
}

export interface WorkflowDefinitionDocument {
  schema_version?: number
  trigger: WorkflowTriggerDefinition
  runtime?: WorkflowRuntimePolicy
  steps: WorkflowStepDefinition[]
  metadata?: Record<string, any>
}

export interface WorkflowStepCatalogEntry {
  type: string
  display_name: string
  description: string
  category?: string | null
  input_schema: Record<string, any>
  config_schema: Record<string, any>
  output_schema: Record<string, any>
  required_permissions: string[]
  supports_retry: boolean
  supports_test: boolean
  estimated_cost_kind?: string | null
  enabled: boolean
  disabled_reason?: string | null
}

export interface WorkflowStepCatalogApiResponse {
  success: boolean
  steps: WorkflowStepCatalogEntry[]
}

export interface WorkflowStepCatalogEntryApiResponse {
  success: boolean
  step: WorkflowStepCatalogEntry
}

export interface WorkflowValidationErrorItem {
  path: string
  message: string
  severity: string
  code?: string | null
  step_key?: string | null
  step_index?: number | null
}

export interface WorkflowValidationResponse {
  success: boolean
  valid: boolean
  definition?: WorkflowDefinitionDocument | null
  errors: WorkflowValidationErrorItem[]
}

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  definition: WorkflowDefinitionDocument
  tags: string[]
  required_placeholders: string[]
  builder_category?: string | null
  available_for_authoring: boolean
  unavailable_reason?: string | null
}

export interface WorkflowTemplateApiResponse {
  success: boolean
  template: WorkflowTemplate
}

export interface WorkflowTemplateCatalogApiResponse {
  success: boolean
  templates: WorkflowTemplate[]
}

export interface WorkflowVersionSummary {
  id: string
  version_number: number
  status: 'draft' | 'published' | 'deprecated'
  created_at?: string | null
  published_at?: string | null
}

export interface WorkflowTriggerSummary {
  id: string
  trigger_type: WorkflowTriggerType
  enabled: boolean
  cron_expression?: string | null
  timezone?: string | null
  misfire_policy?: string | null
  next_run_at?: string | null
}

export interface WorkflowDefinitionListItem {
  id: string
  name: string
  description?: string | null
  status: WorkflowDefinitionStatus
  owner_user_id?: number | null
  current_version_id?: string | null
  latest_version_number: number
  is_active: boolean
  trigger_type: WorkflowTriggerType
  tags: string[]
  created_at?: string | null
  updated_at?: string | null
  last_published_at?: string | null
  archived_at?: string | null
}

export interface WorkflowDefinitionDetail extends WorkflowDefinitionListItem {
  draft_definition: WorkflowDefinitionDocument
  metadata: Record<string, any>
  versions: WorkflowVersionSummary[]
  triggers: WorkflowTriggerSummary[]
}

export interface WorkflowDefinitionApiResponse {
  success: boolean
  workflow: WorkflowDefinitionDetail
}

export interface WorkflowCreatePayload {
  name: string
  description?: string | null
  definition: WorkflowDefinitionDocument
  tags?: string[]
  metadata?: Record<string, any>
}

export interface WorkflowUpdatePayload {
  name?: string
  description?: string | null
  definition?: WorkflowDefinitionDocument
  tags?: string[]
  metadata?: Record<string, any>
}

export interface WorkflowRedactedPayload {
  redacted: boolean
  policy: WorkflowRedactionPolicy
  value: any
}

export interface WorkflowArtifactSummary {
  id: string
  step_run_id?: string | null
  artifact_type: string
  name: string
  data?: WorkflowRedactedPayload | null
  storage_uri?: string | null
  redaction_policy: WorkflowRedactionPolicy
  created_at?: string | null
}

export interface WorkflowEventSummary {
  id: string
  event_type: string
  severity: string
  message: string
  data: Record<string, any>
  created_by_user_id?: number | null
  created_at?: string | null
}

export interface WorkflowRunSummary {
  id: string
  workflow_id: string
  workflow_name?: string | null
  version_id: string
  version_number?: number | null
  status: WorkflowRunStatus
  trigger_type: WorkflowTriggerType
  requested_by_user_id?: number | null
  retry_of_run_id?: string | null
  queued_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  duration_ms?: number | null
  budget_limit_cents?: number | null
  estimated_cost_cents: number
  actual_cost_cents: number
}

export interface WorkflowOperationsTotals {
  total: number
  active: number
  disabled: number
  running: number
  failed: number
  missed: number
}

export interface WorkflowOperationsRow {
  id: string
  name: string
  description?: string | null
  status: WorkflowDefinitionStatus
  health: WorkflowHealthState
  owner_user_id?: number | null
  owner_label?: string | null
  latest_version_number: number
  is_active: boolean
  tags: string[]
  trigger_type: WorkflowTriggerType
  trigger_enabled: boolean
  cron_expression?: string | null
  timezone?: string | null
  next_run_at?: string | null
  last_fire_at?: string | null
  latest_run?: WorkflowRunSummary | null
  active_run?: WorkflowRunSummary | null
  latest_failed_run?: WorkflowRunSummary | null
  last_successful_run?: WorkflowRunSummary | null
  run_count: number
  failure_count: number
  budget_limit_cents?: number | null
  estimated_cost_cents: number
  actual_cost_cents: number
  updated_at?: string | null
}

export interface WorkflowOperationsResponse {
  workflows: WorkflowOperationsRow[]
  totals: WorkflowOperationsTotals
}

export interface WorkflowOperationsApiResponse {
  success: boolean
  operations: WorkflowOperationsResponse
}

export interface WorkflowSchedulePreviewItem {
  run_at: string
  local_time: string
  timezone: string
}

export interface WorkflowScheduleBoardRun {
  workflow_id: string
  workflow_name: string
  trigger_id: string
  run_at: string
  local_time: string
  timezone: string
  health: WorkflowHealthState
  workflow_status: WorkflowDefinitionStatus
  trigger_enabled: boolean
}

export interface WorkflowScheduleBoardGroup {
  key: string
  label: string
  runs: WorkflowScheduleBoardRun[]
}

export interface WorkflowScheduleBoardItem {
  workflow_id: string
  workflow_name: string
  description?: string | null
  status: WorkflowDefinitionStatus
  health: WorkflowHealthState
  owner_label?: string | null
  tags: string[]
  trigger_id: string
  trigger_enabled: boolean
  cron_expression?: string | null
  timezone?: string | null
  misfire_policy?: string | null
  next_run_at?: string | null
  last_fire_at?: string | null
  latest_run?: WorkflowRunSummary | null
  active_run?: WorkflowRunSummary | null
  latest_failed_run?: WorkflowRunSummary | null
  preview: WorkflowSchedulePreviewItem[]
}

export interface WorkflowScheduleBoardResponse {
  schedules: WorkflowScheduleBoardItem[]
  groups: WorkflowScheduleBoardGroup[]
}

export interface WorkflowScheduleBoardApiResponse {
  success: boolean
  schedule_board: WorkflowScheduleBoardResponse
}

export interface WorkflowRunsApiResponse {
  success: boolean
  runs: WorkflowRunSummary[]
}

export interface WorkflowTemplateSummary {
  id: string
  name: string
  description: string
  trigger_type: WorkflowTriggerType
  step_count: number
  tags: string[]
  builder_category?: string | null
  available_for_authoring: boolean
  unavailable_reason?: string | null
}

export interface WorkflowTemplatesApiResponse {
  success: boolean
  templates: WorkflowTemplateSummary[]
}

export interface WorkflowSchedulePreviewApiResponse {
  success: boolean
  preview: {
    cron: string
    timezone: string
    next_runs: WorkflowSchedulePreviewItem[]
  }
}

export interface WorkflowStepRunDetail {
  id: string
  step_key: string
  step_type: string
  status: WorkflowStepRunStatus
  attempt: number
  input_data: WorkflowRedactedPayload
  output_data: WorkflowRedactedPayload
  error?: string | null
  started_at?: string | null
  completed_at?: string | null
  duration_ms?: number | null
  artifacts: WorkflowArtifactSummary[]
}

export interface WorkflowRunDetail {
  id: string
  workflow_id: string
  workflow_name?: string | null
  version_id: string
  version_number?: number | null
  status: WorkflowRunStatus
  trigger_type: string
  requested_by_user_id?: number | null
  retry_of_run_id?: string | null
  queued_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  duration_ms?: number | null
  budget_limit_cents?: number | null
  estimated_cost_cents: number
  actual_cost_cents: number
  trigger_id?: string | null
  idempotency_key?: string | null
  input_data: WorkflowRedactedPayload
  output_data: WorkflowRedactedPayload
  error?: string | null
  locked_by?: string | null
  lock_expires_at?: string | null
  cancel_requested_at?: string | null
  cancelled_by_user_id?: number | null
  redaction_policy: WorkflowRedactionPolicy
  steps: WorkflowStepRunDetail[]
  artifacts: WorkflowArtifactSummary[]
  events: WorkflowEventSummary[]
}

export interface WorkflowRunResponse {
  success: boolean
  run: WorkflowRunDetail
  error?: string
}

export const workflowApi = {
  getOperations() {
    return apiClient.get<WorkflowOperationsApiResponse>('/api/workflows')
  },
  getWorkflow(workflowId: string) {
    const query = new URLSearchParams({
      resource: 'workflow',
      workflow_id: workflowId,
    })
    return apiClient.get<WorkflowDefinitionApiResponse>(`/api/workflows?${query.toString()}`)
  },
  createWorkflow(payload: WorkflowCreatePayload) {
    return apiClient.post<WorkflowDefinitionApiResponse>('/api/workflows', {
      action: 'create',
      ...payload,
    })
  },
  updateWorkflow(workflowId: string, payload: WorkflowUpdatePayload) {
    return apiClient.post<WorkflowDefinitionApiResponse>('/api/workflows', {
      action: 'update',
      workflow_id: workflowId,
      ...payload,
    })
  },
  publishWorkflow(workflowId: string, reason?: string) {
    return apiClient.post<WorkflowDefinitionApiResponse>('/api/workflows', {
      action: 'publish',
      workflow_id: workflowId,
      reason,
    })
  },
  getStepCatalog() {
    return apiClient.get<WorkflowStepCatalogApiResponse>('/api/workflows?resource=catalog')
  },
  getStepCatalogEntry(stepType: string) {
    const query = new URLSearchParams({
      resource: 'catalog_entry',
      step_type: stepType,
    })
    return apiClient.get<WorkflowStepCatalogEntryApiResponse>(`/api/workflows?${query.toString()}`)
  },
  getTemplateCatalog() {
    return apiClient.get<WorkflowTemplateCatalogApiResponse>('/api/workflows?resource=template_catalog')
  },
  getTemplate(templateId: string) {
    const query = new URLSearchParams({
      resource: 'template',
      template_id: templateId,
    })
    return apiClient.get<WorkflowTemplateApiResponse>(`/api/workflows?${query.toString()}`)
  },
  validateDefinition(definition: WorkflowDefinitionDocument) {
    return apiClient.post<WorkflowValidationResponse>('/api/workflows', {
      action: 'validate_definition',
      definition,
    })
  },
  previewDefinitionSchedule(cron: string, timezone: string, count = 5) {
    return apiClient.post<WorkflowSchedulePreviewApiResponse>('/api/workflows', {
      action: 'preview_schedule_definition',
      cron,
      timezone,
      count,
    })
  },
  getRecentRuns(params?: {
    workflow_id?: string
    status?: WorkflowRunStatus
    limit?: number
  }) {
    const query = new URLSearchParams({ resource: 'runs' })
    if (params?.workflow_id) query.set('workflow_id', params.workflow_id)
    if (params?.status) query.set('status', params.status)
    if (params?.limit) query.set('limit', String(params.limit))
    return apiClient.get<WorkflowRunsApiResponse>(`/api/workflows?${query.toString()}`)
  },
  getScheduleBoard() {
    return apiClient.get<WorkflowScheduleBoardApiResponse>('/api/workflows?resource=schedules')
  },
  getTemplates() {
    return apiClient.get<WorkflowTemplatesApiResponse>('/api/workflows?resource=templates')
  },
  runNow(workflowId: string, inputData: Record<string, any> = {}) {
    return apiClient.post<WorkflowRunResponse>('/api/workflows', {
      workflow_id: workflowId,
      input_data: inputData,
    })
  },
  enableWorkflow(workflowId: string, reason?: string) {
    return apiClient.post<WorkflowDefinitionApiResponse>('/api/workflows', {
      action: 'enable',
      workflow_id: workflowId,
      reason,
    })
  },
  disableWorkflow(workflowId: string, reason?: string) {
    return apiClient.post<WorkflowDefinitionApiResponse>('/api/workflows', {
      action: 'disable',
      workflow_id: workflowId,
      reason,
    })
  },
  previewSchedule(workflowId: string, count = 5) {
    return apiClient.post<WorkflowSchedulePreviewApiResponse>('/api/workflows', {
      action: 'preview_schedule',
      workflow_id: workflowId,
      count,
    })
  },
}

export const workflowRunApi = {
  getRun(runId: string) {
    return apiClient.get<WorkflowRunResponse>(`/api/workflows/runs/${encodeURIComponent(runId)}`)
  },
  cancelRun(runId: string, reason?: string) {
    return apiClient.post<WorkflowRunResponse>(`/api/workflows/runs/${encodeURIComponent(runId)}`, {
      action: 'cancel',
      reason,
    })
  },
  retryRun(runId: string, reason?: string) {
    return apiClient.post<WorkflowRunResponse>(`/api/workflows/runs/${encodeURIComponent(runId)}`, {
      action: 'retry',
      reason,
    })
  },
  executeRun(runId: string) {
    return apiClient.post<WorkflowRunResponse>(`/api/workflows/runs/${encodeURIComponent(runId)}`, {
      action: 'execute',
    })
  },
}
