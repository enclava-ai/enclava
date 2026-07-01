"use client"

import { useState, useEffect, useCallback } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Plus, Link2, AlertCircle } from "lucide-react"
import { ConnectorCard } from "@/components/connectors/ConnectorCard"
import { AddConnectorDialog } from "@/components/connectors/AddConnectorDialog"
import { SyncHistoryDialog } from "@/components/connectors/SyncHistoryDialog"
import { apiClient } from "@/lib/api-client"
import { toast } from "sonner"

interface Connector {
  id: number
  name: string
  connector_type: string
  status: "active" | "paused" | "error" | "pending"
  last_sync_status?: string
  last_synced_at?: string | null
  last_sync_error?: string | null
  last_sync_docs_indexed?: number | null
  last_sync_docs_failed?: number | null
  collection_id: number
  collection_name?: string
  created_at: string
  updated_at: string
}

interface Collection {
  id: number
  name: string
}

function ConnectorsPageContent() {
  const searchParams = useSearchParams()
  const [connectors, setConnectors] = useState<Connector[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [historyDialog, setHistoryDialog] = useState<{
    open: boolean
    connectorId: number
    connectorName: string
  }>({ open: false, connectorId: 0, connectorName: "" })

  // Check for OAuth success on mount
  useEffect(() => {
    const oauthSuccess = searchParams.get("oauth_success")
    const connectorId = searchParams.get("connector_id")

    if (oauthSuccess === "true" && connectorId) {
      toast.success("Connector created successfully", {
        description: `Your connector has been set up and is ready to use.`,
      })

      // Clear URL params without reload
      const url = new URL(window.location.href)
      url.searchParams.delete("oauth_success")
      url.searchParams.delete("connector_id")
      window.history.replaceState({}, "", url.toString())
    }
  }, [searchParams])

  // Fetch connectors and collections
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [connectorsData, collectionsData] = await Promise.all([
        apiClient.get<{ connectors: Connector[] }>("/api-internal/v1/connectors"),
        apiClient.get<{ collections: Collection[] }>("/api-internal/v1/connectors/collections"),
      ])

      setConnectors(connectorsData.connectors || [])
      setCollections(collectionsData.collections || [])
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load connectors"
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData()
    }, 30000)

    return () => clearInterval(interval)
  }, [fetchData])

  const handleSync = async (id: number) => {
    try {
      await apiClient.post(`/api-internal/v1/connectors/${id}/sync`)
      toast.success("Sync started", {
        description: "The connector sync has been initiated.",
      })
      // Refresh to show updated status
      fetchData()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to start sync"
      toast.error("Sync failed", {
        description: errorMessage,
      })
    }
  }

  const handlePause = async (id: number) => {
    try {
      await apiClient.patch(`/api-internal/v1/connectors/${id}`, { status: "paused" })
      toast.success("Connector paused")
      fetchData()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to pause connector"
      toast.error("Error", { description: errorMessage })
    }
  }

  const handleResume = async (id: number) => {
    try {
      await apiClient.patch(`/api-internal/v1/connectors/${id}`, { status: "active" })
      toast.success("Connector resumed")
      fetchData()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to resume connector"
      toast.error("Error", { description: errorMessage })
    }
  }

  const handleDelete = async (id: number) => {
    // Confirm before delete
    if (!window.confirm("Are you sure you want to delete this connector? This action cannot be undone.")) {
      return
    }

    try {
      await apiClient.delete(`/api-internal/v1/connectors/${id}`)
      toast.success("Connector deleted")
      fetchData()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to delete connector"
      toast.error("Error", { description: errorMessage })
    }
  }

  const handleEdit = (id: number) => {
    // For now, just show a toast - edit functionality can be added later
    toast.info("Edit functionality coming soon", {
      description: `Editing connector ${id}`,
    })
  }

  const handleViewHistory = (id: number, name: string) => {
    setHistoryDialog({ open: true, connectorId: id, connectorName: name })
  }

  // Calculate stats
  const activeCount = connectors.filter((c) => c.status === "active").length
  const errorCount = connectors.filter((c) => c.status === "error").length
  const pausedCount = connectors.filter((c) => c.status === "paused").length
  const totalDocsIndexed = connectors.reduce(
    (sum, c) => sum + (c.last_sync_docs_indexed || 0),
    0
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Connectors</h1>
          <p className="text-muted-foreground">
            Manage data source connectors to sync content into your knowledge base.
          </p>
        </div>
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Connector
        </Button>
      </div>

      {/* Error alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats overview */}
      {!loading && !error && connectors.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Connectors</CardTitle>
              <Link2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{connectors.length}</div>
              <p className="text-xs text-muted-foreground">
                {activeCount} active, {pausedCount} paused
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active</CardTitle>
              <Badge variant="default" className="h-4 w-fit">
                Active
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-success">{activeCount}</div>
              <p className="text-xs text-muted-foreground">Currently syncing</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Errors</CardTitle>
              <Badge variant="destructive" className="h-4 w-fit">
                Error
              </Badge>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${errorCount > 0 ? "text-danger" : ""}`}>
                {errorCount}
              </div>
              <p className="text-xs text-muted-foreground">Require attention</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Documents Indexed</CardTitle>
              <span className="text-muted-foreground text-sm">📄</span>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalDocsIndexed.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">Total across all connectors</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main content */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-[200px] w-full" />
          <Skeleton className="h-[200px] w-full" />
          <Skeleton className="h-[200px] w-full" />
          <Skeleton className="h-[200px] w-full" />
        </div>
      ) : connectors.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Link2 className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No connectors yet</h3>
            <p className="text-muted-foreground text-center mb-4 max-w-md">
              Connect external data sources like Notion, GitHub, Slack, or Linear to automatically
              sync content into your RAG collections.
            </p>
            <Button onClick={() => setIsAddDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Your First Connector
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {connectors.map((connector) => (
            <ConnectorCard
              key={connector.id}
              id={connector.id}
              name={connector.name}
              connector_type={connector.connector_type}
              status={connector.status}
              last_sync_status={connector.last_sync_status}
              last_synced_at={connector.last_synced_at}
              last_sync_error={connector.last_sync_error}
              last_sync_docs_indexed={connector.last_sync_docs_indexed}
              last_sync_docs_failed={connector.last_sync_docs_failed}
              collection_id={connector.collection_id}
              onSync={handleSync}
              onPause={handlePause}
              onResume={handleResume}
              onDelete={handleDelete}
              onEdit={handleEdit}
              onViewHistory={handleViewHistory}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <AddConnectorDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        collections={collections}
        onSuccess={() => {
          fetchData()
          toast.success("Connector created successfully")
        }}
      />

      <SyncHistoryDialog
        open={historyDialog.open}
        onOpenChange={(open) => setHistoryDialog((prev) => ({ ...prev, open }))}
        connectorId={historyDialog.connectorId}
        connectorName={historyDialog.connectorName}
      />
    </div>
  )
}

// Wrapper with Suspense boundary for useSearchParams
import { Suspense } from "react"

export default function ConnectorsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="h-9 w-48" />
              <Skeleton className="h-5 w-96 mt-2" />
            </div>
            <Skeleton className="h-10 w-32" />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-[100px] w-full" />
            <Skeleton className="h-[100px] w-full" />
            <Skeleton className="h-[100px] w-full" />
            <Skeleton className="h-[100px] w-full" />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-[200px] w-full" />
            <Skeleton className="h-[200px] w-full" />
          </div>
        </div>
      }
    >
      <ConnectorsPageContent />
    </Suspense>
  )
}
