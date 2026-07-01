"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreHorizontal, Play, Pause, Trash2, RefreshCw, History, FileText, Clock, AlertCircle } from "lucide-react"

interface ConnectorCardProps {
  id: number
  name: string
  connector_type: string
  status: string
  last_sync_status?: string
  last_synced_at?: string | null
  last_sync_error?: string | null
  last_sync_docs_indexed?: number | null
  last_sync_docs_failed?: number | null
  collection_id: number
  onSync: (id: number) => void
  onPause: (id: number) => void
  onResume: (id: number) => void
  onDelete: (id: number) => void
  onEdit: (id: number) => void
  onViewHistory?: (id: number, name: string) => void
}

const CONNECTOR_TYPE_INFO: Record<string, { icon: string; label: string; color: string }> = {
  notion: { icon: "📄", label: "Notion", color: "bg-info-soft text-info-soft-foreground" },
  github: { icon: "🐙", label: "GitHub", color: "bg-muted text-muted-foreground" },
  slack: { icon: "💬", label: "Slack", color: "bg-muted text-muted-foreground" },
  linear: { icon: "📐", label: "Linear", color: "bg-muted text-muted-foreground" },
}

function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return "Never"

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return "Just now"
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? "" : "s"} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`

  return date.toLocaleDateString()
}

function getStatusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "active":
      return "default"
    case "paused":
      return "secondary"
    case "error":
      return "destructive"
    default:
      return "outline"
  }
}

export function ConnectorCard({
  id,
  name,
  connector_type,
  status,
  last_sync_status,
  last_synced_at,
  last_sync_error,
  last_sync_docs_indexed,
  last_sync_docs_failed,
  onSync,
  onPause,
  onResume,
  onDelete,
  onEdit,
  onViewHistory,
}: ConnectorCardProps) {
  const [isSyncing, setIsSyncing] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)

  const typeInfo = CONNECTOR_TYPE_INFO[connector_type] || {
    icon: "🔌",
    label: connector_type,
    color: "bg-muted text-muted-foreground",
  }

  const handleSync = async () => {
    setIsSyncing(true)
    try {
      await onSync(id)
    } finally {
      setIsSyncing(false)
    }
  }

  const handleStatusToggle = async () => {
    setIsUpdating(true)
    try {
      if (status === "active") {
        await onPause(id)
      } else {
        await onResume(id)
      }
    } finally {
      setIsUpdating(false)
    }
  }

  const truncatedError = last_sync_error
    ? last_sync_error.length > 100
      ? last_sync_error.substring(0, 100) + "..."
      : last_sync_error
    : null

  return (
    <Card className="relative">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden="true">
              {typeInfo.icon}
            </span>
            <div>
              <CardTitle className="text-lg">{name}</CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1">
                <span className={`text-xs px-2 py-0.5 rounded ${typeInfo.color}`}>{typeInfo.label}</span>
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={getStatusBadgeVariant(status)}>
              {status}
            </Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Open actions for ${name}`}>
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(id)}>
                  Edit
                </DropdownMenuItem>
                {status !== "pending" && (
                  <DropdownMenuItem onClick={handleStatusToggle} disabled={isUpdating}>
                    {status === "active" ? (
                      <>
                        <Pause className="mr-2 h-4 w-4" />
                        Pause
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Resume
                      </>
                    )}
                  </DropdownMenuItem>
                )}
                {onViewHistory && (
                  <DropdownMenuItem onClick={() => onViewHistory(id, name)}>
                    <History className="mr-2 h-4 w-4" />
                    View History
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => onDelete(id)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-3">
          {/* Last sync info */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              <span>{formatRelativeTime(last_synced_at)}</span>
            </div>
            {last_sync_docs_indexed !== null && last_sync_docs_indexed !== undefined && (
              <div className="flex items-center gap-1">
                <FileText className="h-4 w-4" />
                <span>{last_sync_docs_indexed.toLocaleString()} indexed</span>
                {last_sync_docs_failed && last_sync_docs_failed > 0 && (
                  <span className="text-destructive">({last_sync_docs_failed} failed)</span>
                )}
              </div>
            )}
          </div>

          {/* Error message */}
          {status === "error" && truncatedError && (
            <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 p-2 rounded">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span className="line-clamp-2">{truncatedError}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSync}
              disabled={isSyncing || status === "pending"}
              className="flex-1"
            >
              {isSyncing ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Sync Now
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
