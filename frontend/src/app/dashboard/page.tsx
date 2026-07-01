"use client"

import Link from "next/link"
import { useState, useEffect } from "react"
import {
  Activity,
  Bot,
  CheckCircle,
  Code2,
  Copy,
  DollarSign,
  KeyRound,
  Server,
  Shield,
} from "lucide-react"

import { useAuth } from "@/components/providers/auth-provider"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useToast } from "@/hooks/use-toast"
import { config } from "@/lib/config"
import { apiClient } from "@/lib/api-client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBadge, type StatusBadgeStatus } from "@/components/ui/status-badge"

// Force dynamic rendering for authentication
export const dynamic = "force-dynamic"

interface DashboardStats {
  activeModules: number
  runningModules: number
  standbyModules: number
  totalRequests: number
  requestsChange: number
  totalUsers: number
  activeSessions: number
  uptime: number
}

interface ModuleInfo {
  id: string
  name: string
  description: string
  status: "running" | "standby" | "error"
  icon: string
}

interface AgentSummary {
  id: number
  name: string
  is_active: boolean
}

interface AttentionItem {
  title: string
  description: string
  status: StatusBadgeStatus
  href: string
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}

function DashboardContent() {
  const { user } = useAuth()
  const { toast } = useToast()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [loadingStats, setLoadingStats] = useState(true)
  const [agents, setAgents] = useState<AgentSummary[]>([])

  const apiUrl = config.getPublicApiUrl()
  const runningModules = stats?.runningModules ?? 0
  const standbyModules = stats?.standbyModules ?? 0
  const failedModules = modules.filter((module) => module.status === "error").length
  const activeAgents = agents.length
  const totalRequests = stats?.totalRequests ?? 0
  const reliability = stats?.uptime ?? (failedModules > 0 ? 92 : modules.length > 0 ? 99.9 : 0)
  const spendEstimate = "$0.00"

  const trustStatus: StatusBadgeStatus = failedModules > 0
    ? "danger"
    : modules.length === 0
      ? "warning"
      : "success"

  const attentionItems = buildAttentionItems({
    activeAgents,
    failedModules,
    modules,
    standbyModules,
  })

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast({
      title: "Copied",
      description: "API URL copied to clipboard",
    })
  }

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoadingStats(true)

      const [modulesRes, agentsRes] = await Promise.all([
        apiClient.get("/api-internal/v1/modules/").catch(() => null),
        apiClient.get("/agent/configs").catch(() => null),
      ])

      setStats({
        activeModules: 0,
        runningModules: 0,
        standbyModules: 0,
        totalRequests: 0,
        requestsChange: 0,
        totalUsers: 0,
        activeSessions: 0,
        uptime: 0,
      })

      if (modulesRes) {
        const loadedModules = modulesRes.modules || []
        setModules(loadedModules)
        setStats((prev) => ({
          ...prev!,
          activeModules: modulesRes.total || 0,
          runningModules: loadedModules.filter((module: ModuleInfo) => module.status === "running").length || 0,
          standbyModules: loadedModules.filter((module: ModuleInfo) => module.status === "standby").length || 0,
        }))
      } else {
        setModules([])
      }

      if (agentsRes && agentsRes.configs) {
        setAgents(agentsRes.configs.filter((agent: AgentSummary) => agent.is_active))
      } else {
        setAgents([])
      }
    } catch (error) {
      setStats({
        activeModules: 0,
        runningModules: 0,
        standbyModules: 0,
        totalRequests: 0,
        requestsChange: 0,
        totalUsers: 0,
        activeSessions: 0,
        uptime: 0,
      })
      setModules([])
      setAgents([])
    } finally {
      setLoadingStats(false)
    }
  }

  if (loadingStats) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">
          Welcome back, {user?.name || "User"}
        </h1>
        <p className="mt-1 text-muted-foreground">
          Private AI operations, usage, and attention signals.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-primary/10 p-2 text-primary">
              <Shield className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-foreground">Trust line</p>
                <StatusBadge status={trustStatus}>
                  {trustStatus === "success" ? "Protected" : trustStatus === "warning" ? "Needs setup" : "Attention"}
                </StatusBadge>
              </div>
              <p className="text-sm text-muted-foreground">
                {runningModules} running modules, {failedModules} requiring attention, {activeAgents} active agents.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="bg-muted text-muted-foreground">
              Confidential runtime
            </Badge>
            <Badge variant="outline" className="bg-muted text-muted-foreground">
              Policy aware
            </Badge>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          title="Spend"
          value={spendEstimate}
          description="Current period estimate"
          icon={DollarSign}
        />
        <KpiCard
          title="Requests"
          value={totalRequests.toLocaleString()}
          description={stats?.requestsChange ? `${stats.requestsChange}% change` : "No request trend yet"}
          icon={Activity}
        />
        <KpiCard
          title="Reliability"
          value={reliability ? `${reliability.toFixed(1)}%` : "No data"}
          description={failedModules > 0 ? `${failedModules} module issues` : "Operational"}
          icon={CheckCircle}
          status={failedModules > 0 ? "danger" : "success"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Usage chart</CardTitle>
            <CardDescription>Requests, modules, and active agents at a glance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <UsageBar label="Requests" value={totalRequests} max={Math.max(totalRequests, 1)} tone="primary" />
            <UsageBar label="Running modules" value={runningModules} max={Math.max(modules.length, 1)} tone="success" />
            <UsageBar label="Standby modules" value={standbyModules} max={Math.max(modules.length, 1)} tone="warning" />
            <UsageBar label="Active agents" value={activeAgents} max={Math.max(activeAgents, 1)} tone="info" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
            <CardDescription>Operational items to resolve first.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {attentionItems.map((item) => (
              <Link
                key={item.title}
                href={item.href}
                className="block rounded-md border border-border p-3 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{item.title}</p>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </div>
                  <StatusBadge status={item.status}>{item.status}</StatusBadge>
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connect</CardTitle>
          <CardDescription>Use Enclava from OpenAI-compatible clients and agent workflows.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center">
          <div className="flex min-w-0 items-center gap-2 rounded-md border border-border bg-muted p-2">
            <Code2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <code className="min-w-0 flex-1 truncate text-xs text-foreground">{apiUrl}</code>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => copyToClipboard(apiUrl)}
            >
              <Copy className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Copy API URL</span>
            </Button>
          </div>
          <Button variant="outline" asChild>
            <Link href="/admin/api-keys">
              <KeyRound className="mr-2 h-4 w-4" />
              API keys
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/agents">
              <Bot className="mr-2 h-4 w-4" />
              Agents
            </Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Module health</CardTitle>
          <CardDescription>Current runtime module status.</CardDescription>
        </CardHeader>
        <CardContent>
          {modules.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Server className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="font-medium text-foreground">No modules configured</p>
              <p className="text-sm text-muted-foreground">Configure modules to start private AI workflows.</p>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {modules.map((module) => (
                <div key={module.name} className="rounded-md border border-border bg-card p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">{module.name}</p>
                      <p className="text-sm text-muted-foreground">{module.description}</p>
                    </div>
                    <StatusBadge status={statusForModule(module.status)}>
                      {module.status}
                    </StatusBadge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function KpiCard({
  title,
  value,
  description,
  icon: Icon,
  status = "neutral",
}: {
  title: string
  value: string
  description: string
  icon: typeof Activity
  status?: StatusBadgeStatus
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className={status === "danger" ? "h-4 w-4 text-danger" : "h-4 w-4 text-primary"} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-foreground">{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

function UsageBar({
  label,
  value,
  max,
  tone,
}: {
  label: string
  value: number
  max: number
  tone: "primary" | "success" | "warning" | "info"
}) {
  const width = `${Math.min(100, Math.round((value / max) * 100))}%`
  const toneClass = {
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    info: "bg-info",
  }[tone]

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground">{value.toLocaleString()}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${toneClass}`} style={{ width }} />
      </div>
    </div>
  )
}

function buildAttentionItems({
  activeAgents,
  failedModules,
  modules,
  standbyModules,
}: {
  activeAgents: number
  failedModules: number
  modules: ModuleInfo[]
  standbyModules: number
}): AttentionItem[] {
  const items: AttentionItem[] = []

  if (failedModules > 0) {
    items.push({
      title: "Module errors",
      description: `${failedModules} module${failedModules === 1 ? "" : "s"} require review.`,
      status: "danger",
      href: "/settings",
    })
  }

  if (activeAgents === 0) {
    items.push({
      title: "No active agents",
      description: "Create or activate an agent for reusable private workflows.",
      status: "warning",
      href: "/agents",
    })
  }

  if (modules.length === 0 || standbyModules > 0) {
    items.push({
      title: "Module setup",
      description: modules.length === 0
        ? "Configure runtime modules before production use."
        : `${standbyModules} module${standbyModules === 1 ? "" : "s"} in standby.`,
      status: "info",
      href: "/settings",
    })
  }

  if (items.length === 0) {
    items.push({
      title: "No urgent items",
      description: "The current workspace has no immediate operational action.",
      status: "success",
      href: "/dashboard",
    })
  }

  return items
}

function statusForModule(status: ModuleInfo["status"]): StatusBadgeStatus {
  if (status === "running") return "success"
  if (status === "error") return "danger"
  return "warning"
}
