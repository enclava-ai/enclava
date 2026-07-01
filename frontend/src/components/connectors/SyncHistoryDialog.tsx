"use client"

import { useState, useEffect, useCallback } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { apiClient } from "@/lib/api-client"
import { AlertCircle, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react"

interface SyncJob {
  id: number
  connector_id: number
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  started_at: string
  finished_at?: string | null
  docs_indexed: number
  docs_failed: number
  error_message?: string | null
}

interface SyncHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  connectorId: number
  connectorName: string
}

function formatDuration(startedAt: string, finishedAt?: string | null): string {
  if (!finishedAt) {
    const start = new Date(startedAt)
    const now = new Date()
    const diffMs = now.getTime() - start.getTime()
    const diffSecs = Math.floor(diffMs / 1000)
    const diffMins = Math.floor(diffSecs / 60)

    if (diffSecs < 60) return `${diffSecs}s`
    if (diffMins < 60) return `${diffMins}m ${diffSecs % 60}s`
    return `${Math.floor(diffMins / 60)}h ${diffMins % 60}m`
  }

  const start = new Date(startedAt)
  const end = new Date(finishedAt)
  const diffMs = end.getTime() - start.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)

  if (diffSecs < 60) return `${diffSecs}s`
  if (diffMins < 60) return `${diffMins}m ${diffSecs % 60}s`
  return `${Math.floor(diffMins / 60)}h ${diffMins % 60}m`
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function getStatusBadgeVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "completed":
      return "default"
    case "running":
      return "secondary"
    case "failed":
    case "cancelled":
      return "destructive"
    default:
      return "outline"
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-4 w-4 text-success" />
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-info" />
    case "failed":
      return <XCircle className="h-4 w-4 text-danger" />
    case "cancelled":
      return <AlertCircle className="h-4 w-4 text-warning" />
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />
  }
}

export function SyncHistoryDialog({
  open,
  onOpenChange,
  connectorId,
  connectorName,
}: SyncHistoryDialogProps) {
  const [jobs, setJobs] = useState<SyncJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<{ jobs: SyncJob[] }>(
        `/api-internal/v1/connectors/${connectorId}/jobs`
      )
      setJobs(data.jobs || [])
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load sync history"
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }, [connectorId])

  useEffect(() => {
    if (open) {
      fetchJobs()
    }
  }, [open, connectorId, fetchJobs])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[900px] max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Sync History - {connectorName}</DialogTitle>
          <DialogDescription>
            View the history of sync jobs for this connector
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-8 text-destructive">
              <AlertCircle className="h-5 w-5 mr-2" />
              {error}
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No sync jobs found for this connector
            </div>
          ) : (
            <ScrollArea className="h-[400px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="text-right">Indexed</TableHead>
                    <TableHead className="text-right">Failed</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <StatusIcon status={job.status} />
                          <Badge variant={getStatusBadgeVariant(job.status)}>
                            {job.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>{formatDateTime(job.started_at)}</TableCell>
                      <TableCell>
                        {formatDuration(job.started_at, job.finished_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        {job.docs_indexed.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        {job.docs_failed > 0 ? (
                          <span className="text-destructive">
                            {job.docs_failed.toLocaleString()}
                          </span>
                        ) : (
                          "0"
                        )}
                      </TableCell>
                      <TableCell>
                        {job.error_message ? (
                          <span
                            className="text-sm text-destructive truncate max-w-[150px] block"
                            title={job.error_message}
                          >
                            {job.error_message.length > 30
                              ? job.error_message.substring(0, 30) + "..."
                              : job.error_message}
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
