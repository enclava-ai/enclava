import type { Page, Route } from "@playwright/test"

const future = Date.now() + 60 * 60 * 1000

export const testUser = {
  id: "1",
  username: "test-admin",
  email: "test-admin@example.com",
  name: "Test Admin",
  full_name: "Test Admin",
  role: "super_admin",
  is_superuser: true,
  permissions: ["*", "platform:*", "modules:*", "llm:*", "workflow.manage"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

const modules = [
  {
    name: "rag",
    id: "rag",
    version: "1.0.0",
    description: "Knowledge base and retrieval",
    initialized: true,
    enabled: true,
    status: "running",
    stats: { total_requests: 24, uptime: 99.9 },
  },
  {
    name: "extract",
    id: "extract",
    version: "1.0.0",
    description: "Document extraction",
    initialized: true,
    enabled: true,
    status: "running",
    stats: { total_requests: 12, uptime: 99.9 },
  },
  {
    name: "workflow",
    id: "workflow",
    version: "1.0.0",
    description: "Workflow automation",
    initialized: true,
    enabled: true,
    status: "running",
    stats: { total_requests: 9, uptime: 99.9 },
  },
]

const agents = [
  {
    id: 1,
    name: "Support Agent",
    description: "Answers customer questions with private context.",
    system_prompt: "You are a concise support agent.",
    model: "gpt-oss-120b",
    temperature: 0.3,
    max_tokens: 2000,
    tools_config: {
      builtin_tools: ["rag_search"],
      mcp_servers: [],
      include_custom_tools: true,
      tool_choice: "auto",
      max_iterations: 5,
    },
    tool_resources: {},
    category: "support",
    tags: ["support"],
    is_public: false,
    is_active: true,
    usage_count: 3,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
]

const collections = [
  {
    id: "1",
    name: "Product Docs",
    description: "Internal product documentation",
    document_count: 4,
    size_bytes: 4096,
    vector_count: 128,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    status: "active",
    is_active: true,
    is_managed: true,
    source: "database",
  },
]

const documents = [
  {
    id: "doc-1",
    title: "Getting Started",
    filename: "getting-started.md",
    original_filename: "getting-started.md",
    collection_id: "1",
    collection_name: "Product Docs",
    status: "processed",
    content_type: "text/markdown",
    file_type: "markdown",
    size_bytes: 2048,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    processed_at: "2026-01-02T00:01:00Z",
    metadata: { keywords: ["onboarding", "setup"], language: "en" },
  },
]

const workflowRun = {
  id: "run-1",
  workflow_id: "workflow-1",
  workflow_name: "Nightly RAG Summary",
  version_id: "version-1",
  version_number: 1,
  status: "succeeded",
  trigger_type: "schedule",
  queued_at: "2026-07-07T02:00:00Z",
  started_at: "2026-07-07T02:00:01Z",
  completed_at: "2026-07-07T02:00:06Z",
  created_at: "2026-07-07T02:00:00Z",
  updated_at: "2026-07-07T02:00:06Z",
  duration_ms: 5000,
  estimated_cost_cents: 1,
  actual_cost_cents: 1,
  redaction_policy: "default",
  input_data: { redacted: false, value: {} },
  output_data: { redacted: false, value: { message: "Summary generated" } },
  steps: [
    {
      id: "step-1",
      step_key: "notify_owner",
      step_type: "notify.in_app",
      status: "succeeded",
      attempt: 1,
      input_data: { redacted: false, value: {} },
      output_data: { redacted: false, value: { notification_ids: ["n-1"] } },
      artifacts: [],
    },
  ],
  artifacts: [{ id: "artifact-1", artifact_type: "summary", name: "Summary", data: {} }],
  events: [
    {
      id: "event-1",
      event_type: "run_succeeded",
      severity: "info",
      message: "Run succeeded",
      data: {},
      created_at: "2026-07-07T02:00:06Z",
    },
  ],
  approvals: [],
}

const workflowRow = {
  id: "workflow-1",
  name: "Nightly RAG Summary",
  description: "Summarizes new knowledge base data every night.",
  status: "active",
  health: "healthy",
  owner_user_id: 1,
  owner_label: "Test Admin",
  latest_version_number: 1,
  is_active: true,
  tags: ["rag", "schedule"],
  trigger_type: "schedule",
  trigger_enabled: true,
  cron_expression: "0 2 * * *",
  timezone: "UTC",
  next_run_at: "2026-07-08T02:00:00Z",
  latest_run: workflowRun,
  run_count: 7,
  failure_count: 0,
  estimated_cost_cents: 7,
  actual_cost_cents: 6,
  updated_at: "2026-07-07T02:00:06Z",
}

export async function setupApiMocks(page: Page) {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (!isAppApiPath(path)) {
      await route.fallback()
      return
    }

    await fulfillJson(route, responseFor(path, url, route.request().method()))
  })
}

export async function seedAuthenticatedSession(page: Page) {
  await page.addInitScript(
    ([accessExpiresAt]) => {
      window.localStorage.setItem(
        "auth_tokens",
        JSON.stringify({
          access_token: "e2e-access-token",
          refresh_token: "e2e-refresh-token",
          access_expires_at: accessExpiresAt,
          refresh_expires_at: accessExpiresAt + 7 * 24 * 60 * 60 * 1000,
        })
      )
    },
    [future]
  )
}

function isAppApiPath(path: string) {
  return (
    path.startsWith("/api/") ||
    path.startsWith("/api-internal/") ||
    path.startsWith("/api/v1/") ||
    path.startsWith("/agent/")
  )
}

function responseFor(path: string, url: URL, method: string) {
  if (path.endsWith("/auth/login")) {
    return {
      access_token: "e2e-access-token",
      refresh_token: "e2e-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
      user: testUser,
    }
  }
  if (path.endsWith("/auth/me")) return testUser
  if (path.endsWith("/auth/refresh")) {
    return { access_token: "e2e-access-token", refresh_token: "e2e-refresh-token", expires_in: 3600 }
  }

  if (path === "/api-internal/v1/modules/" || path === "/api-internal/v1/modules") {
    return { success: true, total: modules.length, module_count: modules.length, initialized: true, modules }
  }

  if (path === "/agent/configs") return { configs: agents, total: agents.length }
  if (path === "/api/v1/mcp-servers/available") return { servers: [] }
  if (path === "/api-internal/v1/rag/collections" || path === "/api/rag/collections") {
    return { success: true, collections, total: collections.length }
  }
  if (path === "/api-internal/v1/rag/documents" || path === "/api/rag/documents") {
    return { success: true, documents, total: documents.length }
  }
  if (path === "/api-internal/v1/rag/stats" || path === "/api/rag/stats") {
    return {
      collections: { total: 1, active: 1 },
      documents: { total: 4, processing: 0, processed: 4 },
      storage: { total_size_bytes: 4096, total_size_mb: 0.004 },
      vectors: { total: 128 },
    }
  }
  if (path === "/api-internal/v1/connectors") {
    return {
      success: true,
      connectors: [
        {
          id: "connector-1",
          name: "Docs GitHub",
          type: "github",
          connector_type: "github",
          status: "active",
          document_count: 4,
          last_sync: "2026-07-07T01:00:00Z",
        },
      ],
    }
  }

  if (path === "/api/v1/extract/templates") {
    return {
      templates: [
        {
          id: "invoice",
          description: "Invoice fields",
          system_prompt: "Extract invoice data",
          user_prompt: "Extract fields",
          output_schema: {},
          is_default: true,
          is_active: true,
        },
      ],
    }
  }
  if (path === "/api/v1/extract/models" || path === "/api-internal/v1/llm/models" || path === "/api/llm/models") {
    return { models: [{ id: "gpt-oss-120b", name: "GPT OSS 120B", provider: "test" }] }
  }
  if (path === "/api-internal/v1/extract/settings") {
    return {
      default_model: "gpt-oss-120b",
      enabled: true,
      max_file_size_mb: 25,
      allowed_file_types: ["pdf", "png", "jpg"],
    }
  }
  if (path === "/api/v1/extract/process") {
    return { job_id: "extract-job-1", status: "completed", result: { invoice_number: "INV-001" } }
  }

  if (path === "/api/workflows") return workflowResponseFor(url, method)
  if (path.startsWith("/api/workflows/runs/")) return { success: true, run: workflowRun }

  if (path === "/api-internal/v1/plugins/installed") return { plugins: [] }
  if (path.startsWith("/api-internal/v1/plugins/discover")) {
    return {
      plugins: [
        {
          id: "slack",
          name: "Slack",
          version: "1.0.0",
          description: "Send workflow notifications to Slack.",
          author: "Enclava",
          tags: ["notifications"],
          category: "communication",
          local_status: { installed: false },
        },
      ],
    }
  }

  if (path === "/api-internal/v1/analytics") {
    return {
      overview: { totalUsers: 3, totalRequests: 42, totalCost: 1.25, averageResponseTime: 0.12 },
      usage: { requests: [], models: [{ name: "gpt-oss-120b", count: 12, cost: 0.5 }], endpoints: [] },
      performance: { responseTime: [], errorRate: 0, uptime: 99.9 },
      costs: { daily: [], byModel: [], budget: { used: 12, limit: 100 } },
    }
  }
  if (path === "/api-internal/v1/budgets") {
    return { budgets: [], total: 0 }
  }
  if (path === "/api-internal/v1/budgets/stats") {
    return { total_budgets: 0, active_budgets: 0, over_threshold: 0, total_spending: 0, monthly_spending: 0, savings_percentage: 0 }
  }
  if (path === "/api-internal/v1/audit") {
    return { logs: [], total: 0, page: 1, size: 50 }
  }
  if (path === "/api-internal/v1/audit/stats") {
    return { total_logs: 0, success_rate: 100, failed_actions: 0, unique_users: 1, top_actions: [], recent_failures: 0 }
  }
  if (path === "/api-internal/v1/settings/" || path === "/api-internal/v1/settings") {
    return {
      notifications: {
        email_enabled: false,
        smtp_host: "",
        smtp_port: 587,
        smtp_username: "",
        smtp_use_tls: true,
        from_address: "noreply@example.com",
        budget_alerts: true,
        system_alerts: true,
      },
    }
  }

  if (path === "/api-internal/v1/prompt-templates/templates") {
    return [
      {
        id: "prompt-1",
        name: "General Assistant",
        type_key: "assistant",
        description: "Default assistant behavior",
        system_prompt: "You are helpful and concise.",
        is_default: true,
        is_active: true,
        version: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]
  }
  if (path === "/api-internal/v1/prompt-templates/variables") {
    return [{ id: "var-1", variable_name: "user_name", description: "Current user", is_active: true }]
  }
  if (path === "/api-internal/v1/providers/health") {
    return [
      {
        provider_id: "test",
        display_name: "Test Provider",
        healthy: true,
        last_check_at: "2026-07-07T00:00:00Z",
        last_healthy_at: "2026-07-07T00:00:00Z",
        error: null,
        attestation_details: null,
        pricing: { source: "manual", last_sync_at: "2026-07-07T00:00:00Z", model_count: 1 },
        models: [
          {
            id: "gpt-oss-120b",
            capabilities: ["chat"],
            context_window: 131072,
            max_output_tokens: 8192,
            supports_streaming: true,
            supports_function_calling: true,
            tasks: ["generate"],
            pricing: { input_per_million_cents: 100, output_per_million_cents: 200, source: "default" },
          },
        ],
      },
    ]
  }

  if (path.startsWith("/api-internal/v1/user-management/users")) {
    return {
      users: [
        {
          id: 1,
          email: testUser.email,
          username: testUser.username,
          full_name: testUser.full_name,
          is_active: true,
          is_verified: true,
          account_locked: false,
          role_id: 1,
          role: { id: 1, name: "super_admin", display_name: "Super Administrator", level: "super_admin" },
          created_at: "2026-01-01T00:00:00Z",
          last_login: "2026-07-07T00:00:00Z",
          failed_login_attempts: 0,
          budget_limit: 0,
          budget_spent: 0,
        },
      ],
      total: 1,
    }
  }
  if (path === "/api-internal/v1/user-management/roles") {
    return {
      roles: [
        {
          id: 1,
          name: "super_admin",
          display_name: "Super Administrator",
          description: "Full system access",
          level: "super_admin",
          permissions: { granted: ["*"], denied: [] },
          can_manage_users: true,
          can_manage_budgets: true,
          can_view_reports: true,
          can_manage_tools: true,
          inherits_from: ["admin"],
          is_active: true,
          is_system_role: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    }
  }
  if (path === "/api-internal/v1/user-management/statistics") {
    return { roles: { total_roles: 1, active_roles: 1, system_roles: 1, roles_by_level: { super_admin: 1 } } }
  }

  if (path.includes("/admin/pricing") || path.includes("/providers") || path.includes("/usage")) {
    return { success: true, providers: [], pricing: [], total: 0, summary: {} }
  }
  if (path.includes("/user-management") || path.includes("/users")) {
    return { users: [testUser], roles: [{ id: 1, name: "super_admin", display_name: "Super Administrator" }], total: 1 }
  }
  if (path.includes("/api-keys")) return { api_keys: [], keys: [], total: 0 }

  return { success: true }
}

function workflowResponseFor(url: URL, method: string) {
  if (method === "POST") {
    return { success: true, workflow: { ...workflowRow, draft_definition: workflowDefinition() }, run: workflowRun, valid: true, errors: [] }
  }

  const resource = url.searchParams.get("resource")
  if (!resource) {
    return {
      success: true,
      operations: {
        workflows: [workflowRow],
        totals: { total: 1, active: 1, disabled: 0, running: 0, failed: 0, missed: 0 },
      },
    }
  }
  if (resource === "runs") return { success: true, runs: [workflowRun] }
  if (resource === "schedules") {
    return {
      success: true,
      schedule_board: {
        schedules: [
          {
            workflow_id: workflowRow.id,
            workflow_name: workflowRow.name,
            status: "active",
            health: "healthy",
            tags: workflowRow.tags,
            trigger_id: "trigger-1",
            trigger_enabled: true,
            cron_expression: "0 2 * * *",
            timezone: "UTC",
            next_run_at: "2026-07-08T02:00:00Z",
            preview: [{ run_at: "2026-07-08T02:00:00Z", local_time: "2026-07-08T02:00:00Z", timezone: "UTC" }],
          },
        ],
        groups: [{ key: "upcoming", label: "Upcoming", runs: [] }],
      },
    }
  }
  if (resource === "templates" || resource === "template_catalog") {
    return {
      success: true,
      templates: [
        {
          id: "nightly-rag-summary",
          name: "Nightly RAG Summary",
          description: "Summarize new RAG documents on a schedule.",
          trigger_type: "schedule",
          step_count: 4,
          tags: ["rag", "agent", "schedule"],
          builder_category: "RAG",
          available_for_authoring: true,
          definition: workflowDefinition(),
        },
      ],
    }
  }
  if (resource === "catalog") {
    return {
      success: true,
      steps: [
        {
          type: "notify.in_app",
          display_name: "In-app notification",
          description: "Create an in-app notification.",
          category: "Notification",
          input_schema: {},
          config_schema: {},
          output_schema: {},
          required_permissions: ["notifications:create"],
          supports_retry: true,
          supports_test: false,
          enabled: true,
        },
      ],
    }
  }
  if (resource === "workflow" || resource === "template") {
    return { success: true, workflow: { ...workflowRow, draft_definition: workflowDefinition() }, template: { id: "nightly-rag-summary", definition: workflowDefinition() } }
  }
  if (resource === "admin_metrics") {
    return {
      success: true,
      metrics: {
        generated_at: "2026-07-07T02:00:00Z",
        window_hours: 24,
        scheduler_lag_seconds: 0,
        stale_lock_count: 0,
        long_running_count: 0,
        queued_runs: 0,
        running_runs: 0,
        paused_runs: 0,
        failed_runs_24h: 0,
        total_runs_24h: 7,
        failure_rate_24h: 0,
        failed_workflows: [],
        top_workflows_by_cost: [{ workflow_id: workflowRow.id, workflow_name: workflowRow.name, run_count: 7, actual_cost_cents: 6, estimated_cost_cents: 7 }],
      },
    }
  }
  return { success: true }
}

function workflowDefinition() {
  return {
    schema_version: 1,
    trigger: { type: "schedule", cron: "0 2 * * *", timezone: "UTC" },
    runtime: { concurrency_policy: "allow_parallel", timeout_seconds: 1800, redaction_policy: "default" },
    steps: [
      {
        key: "notify_owner",
        type: "notify.in_app",
        name: "Notify owner",
        config: { recipients: ["1"], title_template: "Summary ready" },
      },
    ],
  }
}

async function fulfillJson(route: Route, body: unknown) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}
