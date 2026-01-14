"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import {
  Plus,
  Settings,
  Trash2,
  Server,
  RefreshCw,
  TestTube,
  CheckCircle,
  XCircle,
  Clock,
  Globe,
  Lock,
  Loader2,
  Wrench
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { mcpServerApi } from "@/lib/api-client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type {
  MCPServer,
  MCPServerFormState,
  MCPServerTestResponse,
  MCPToolInfo,
  CreateMCPServerRequest,
  UpdateMCPServerRequest
} from "@/types/mcp-server"
import {
  DEFAULT_MCP_SERVER_FORM,
  API_KEY_HEADER_OPTIONS,
  validateMCPServerName,
  validateServerUrl,
  getConnectionStatus,
  getConnectionStatusColor,
  getConnectionStatusText
} from "@/types/mcp-server"

export function MCPServerManager() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showTestDialog, setShowTestDialog] = useState(false)
  const [deletingServer, setDeletingServer] = useState<MCPServer | null>(null)
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null)
  const [testResult, setTestResult] = useState<MCPServerTestResponse | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [refreshingId, setRefreshingId] = useState<number | null>(null)
  const { toast } = useToast()

  // Form state
  const [formData, setFormData] = useState<MCPServerFormState>(DEFAULT_MCP_SERVER_FORM)
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    loadServers()
  }, [])

  const loadServers = async () => {
    try {
      const data = await mcpServerApi.listServers()
      setServers(data.servers || [])
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load MCP servers",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}

    const nameError = validateMCPServerName(formData.name)
    if (nameError) errors.name = nameError

    if (!formData.display_name) errors.display_name = "Display name is required"

    const urlError = validateServerUrl(formData.server_url)
    if (urlError) errors.server_url = urlError

    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleCreateServer = async () => {
    if (!validateForm()) return

    setSaving(true)

    try {
      // Step 1: Test connection first
      const testResponse = await mcpServerApi.testConnection({
        server_url: formData.server_url,
        api_key: formData.api_key || undefined,
        api_key_header_name: formData.api_key_header_name,
        timeout_seconds: formData.timeout_seconds
      })

      if (!testResponse.success) {
        // Show test failure and don't create
        setTestResult(testResponse)
        setShowTestDialog(true)
        toast({
          title: "Connection Failed",
          description: testResponse.error || "Could not connect to MCP server. Please check your settings.",
          variant: "destructive"
        })
        return
      }

      // Step 2: Connection successful, create the server
      const request: CreateMCPServerRequest = {
        name: formData.name,
        display_name: formData.display_name,
        description: formData.description || undefined,
        server_url: formData.server_url,
        api_key: formData.api_key || undefined,
        api_key_header_name: formData.api_key_header_name,
        timeout_seconds: formData.timeout_seconds,
        max_retries: formData.max_retries,
        is_global: formData.is_global
      }

      const server = await mcpServerApi.createServer(request)
      setServers(prev => [...prev, server])
      setShowCreateDialog(false)
      resetForm()
      toast({
        title: "Success",
        description: `MCP server created with ${testResponse.tool_count} tools discovered`
      })
    } catch (error: any) {
      const errorMessage = error?.details?.detail || error?.message || "Failed to create MCP server"
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateServer = async () => {
    if (!editingServer || !validateForm()) return

    setSaving(true)

    try {
      // Check if connection-related settings changed
      const connectionChanged =
        formData.server_url !== editingServer.server_url ||
        formData.api_key_header_name !== editingServer.api_key_header_name ||
        formData.api_key // New API key provided

      // Test connection if connection settings changed
      if (connectionChanged) {
        const testResponse = await mcpServerApi.testConnection({
          server_url: formData.server_url,
          api_key: formData.api_key || undefined, // Use new key or test without (server will use existing)
          api_key_header_name: formData.api_key_header_name,
          timeout_seconds: formData.timeout_seconds
        })

        if (!testResponse.success) {
          setTestResult(testResponse)
          setShowTestDialog(true)
          toast({
            title: "Connection Failed",
            description: testResponse.error || "Could not connect to MCP server. Please check your settings.",
            variant: "destructive"
          })
          return
        }
      }

      const request: UpdateMCPServerRequest = {
        display_name: formData.display_name,
        description: formData.description || undefined,
        server_url: formData.server_url,
        api_key_header_name: formData.api_key_header_name,
        timeout_seconds: formData.timeout_seconds,
        max_retries: formData.max_retries,
        is_global: formData.is_global
      }

      // Only include api_key if it was changed (non-empty)
      if (formData.api_key) {
        request.api_key = formData.api_key
      }

      const updated = await mcpServerApi.updateServer(editingServer.id, request)
      setServers(prev => prev.map(s => s.id === updated.id ? updated : s))
      setShowEditDialog(false)
      setEditingServer(null)
      resetForm()
      toast({
        title: "Success",
        description: "MCP server updated successfully"
      })
    } catch (error: any) {
      const errorMessage = error?.details?.detail || error?.message || "Failed to update MCP server"
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteServer = async () => {
    if (!deletingServer) return

    try {
      await mcpServerApi.deleteServer(deletingServer.id)
      setServers(prev => prev.filter(s => s.id !== deletingServer.id))
      setShowDeleteDialog(false)
      setDeletingServer(null)
      toast({
        title: "Success",
        description: `${deletingServer.display_name} has been deleted`
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete MCP server",
        variant: "destructive"
      })
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)

    try {
      const result = await mcpServerApi.testConnection({
        server_url: formData.server_url,
        api_key: formData.api_key || undefined,
        api_key_header_name: formData.api_key_header_name,
        timeout_seconds: formData.timeout_seconds
      })
      setTestResult(result)
      setShowTestDialog(true)
    } catch (error: any) {
      setTestResult({
        success: false,
        message: "Connection test failed",
        tools: [],
        tool_count: 0,
        error: error?.message || "Unknown error"
      })
      setShowTestDialog(true)
    } finally {
      setTesting(false)
    }
  }

  const handleRefreshTools = async (server: MCPServer) => {
    setRefreshingId(server.id)

    try {
      const result = await mcpServerApi.refreshTools(server.id)

      if (result.success) {
        // Reload servers to get updated cached_tools
        await loadServers()
        toast({
          title: "Success",
          description: `Discovered ${result.tool_count} tools`
        })
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to refresh tools",
          variant: "destructive"
        })
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.message || "Failed to refresh tools",
        variant: "destructive"
      })
    } finally {
      setRefreshingId(null)
    }
  }

  const openEditDialog = (server: MCPServer) => {
    setEditingServer(server)
    setFormData({
      name: server.name,
      display_name: server.display_name,
      description: server.description || "",
      server_url: server.server_url,
      api_key: "", // Don't pre-fill API key for security
      api_key_header_name: server.api_key_header_name,
      timeout_seconds: server.timeout_seconds,
      max_retries: server.max_retries,
      is_global: server.is_global
    })
    setFormErrors({})
    setShowEditDialog(true)
  }

  const openDeleteDialog = (server: MCPServer) => {
    setDeletingServer(server)
    setShowDeleteDialog(true)
  }

  const resetForm = () => {
    setFormData(DEFAULT_MCP_SERVER_FORM)
    setFormErrors({})
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "Never"
    return new Date(dateStr).toLocaleDateString()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">MCP Servers</h2>
          <p className="text-muted-foreground">
            Configure external MCP servers to extend agent capabilities.
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={(open) => {
          setShowCreateDialog(open)
          if (!open) resetForm()
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Add MCP Server
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add MCP Server</DialogTitle>
              <DialogDescription>
                Configure a new MCP server for tool integration.
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="connection" className="mt-6">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="connection">Connection</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>

              <TabsContent value="connection" className="space-y-4 mt-6">
                <div>
                  <Label htmlFor="name">Server Name (ID) <span className="text-destructive">*</span></Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value.toLowerCase() }))}
                    placeholder="e.g., order-api"
                  />
                  {formErrors.name && (
                    <p className="text-xs text-destructive mt-1">{formErrors.name}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    Unique identifier (lowercase, numbers, hyphens)
                  </p>
                </div>

                <div>
                  <Label htmlFor="display_name">Display Name <span className="text-destructive">*</span></Label>
                  <Input
                    id="display_name"
                    value={formData.display_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
                    placeholder="e.g., Order Management API"
                  />
                  {formErrors.display_name && (
                    <p className="text-xs text-destructive mt-1">{formErrors.display_name}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="server_url">Server URL <span className="text-destructive">*</span></Label>
                  <Input
                    id="server_url"
                    value={formData.server_url}
                    onChange={(e) => setFormData(prev => ({ ...prev, server_url: e.target.value }))}
                    placeholder="https://mcp-server.example.com"
                  />
                  {formErrors.server_url && (
                    <p className="text-xs text-destructive mt-1">{formErrors.server_url}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="api_key">API Key (Optional)</Label>
                  <Input
                    id="api_key"
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
                    placeholder="Enter API key if required"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Stored securely on the server
                  </p>
                </div>

                <div>
                  <Label htmlFor="api_key_header_name">API Key Header</Label>
                  <Select
                    value={API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name) ? formData.api_key_header_name : "__custom__"}
                    onValueChange={(value) => {
                      if (value === "__custom__") {
                        // Keep current custom value or set empty for user to fill
                        if (API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name)) {
                          setFormData(prev => ({ ...prev, api_key_header_name: "" }))
                        }
                      } else {
                        setFormData(prev => ({ ...prev, api_key_header_name: value }))
                      }
                    }}
                  >
                    <SelectTrigger id="api_key_header_name">
                      <SelectValue placeholder="Select header name" />
                    </SelectTrigger>
                    <SelectContent>
                      {API_KEY_HEADER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                      <SelectItem value="__custom__">Other (Custom)</SelectItem>
                    </SelectContent>
                  </Select>
                  {!API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name) && (
                    <Input
                      className="mt-2"
                      value={formData.api_key_header_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, api_key_header_name: e.target.value }))}
                      placeholder="e.g., CONTEXT7_API_KEY"
                    />
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    HTTP header used to send the API key
                  </p>
                </div>

                <div>
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="What does this MCP server provide?"
                    className="min-h-[80px]"
                  />
                </div>

                <Button
                  variant="outline"
                  onClick={handleTestConnection}
                  disabled={testing || !formData.server_url}
                  className="w-full"
                >
                  {testing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testing Connection...
                    </>
                  ) : (
                    <>
                      <TestTube className="h-4 w-4 mr-2" />
                      Test Connection
                    </>
                  )}
                </Button>
              </TabsContent>

              <TabsContent value="settings" className="space-y-4 mt-6">
                <div>
                  <Label>Timeout: {formData.timeout_seconds}s</Label>
                  <Slider
                    value={[formData.timeout_seconds]}
                    onValueChange={([value]) => setFormData(prev => ({ ...prev, timeout_seconds: value }))}
                    min={5}
                    max={120}
                    step={5}
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Request timeout in seconds
                  </p>
                </div>

                <div>
                  <Label>Max Retries: {formData.max_retries}</Label>
                  <Slider
                    value={[formData.max_retries]}
                    onValueChange={([value]) => setFormData(prev => ({ ...prev, max_retries: value }))}
                    min={0}
                    max={10}
                    step={1}
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Number of retry attempts on failure
                  </p>
                </div>

                <div className="flex items-center space-x-2 pt-4">
                  <Checkbox
                    id="is_global"
                    checked={formData.is_global}
                    onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_global: checked as boolean }))}
                  />
                  <Label htmlFor="is_global" className="flex items-center">
                    <Globe className="h-4 w-4 mr-2" />
                    Make this server available to all users (Admin only)
                  </Label>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)} disabled={saving}>
                Cancel
              </Button>
              <Button
                onClick={handleCreateServer}
                disabled={saving || !formData.name || !formData.display_name || !formData.server_url}
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Testing & Creating...
                  </>
                ) : (
                  "Create Server"
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Server List */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {servers.map((server) => {
          const status = getConnectionStatus(server)
          const statusColor = getConnectionStatusColor(status)
          const statusText = getConnectionStatusText(status)

          return (
            <Card key={server.id} className="group hover:shadow-lg transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-muted">
                      <Server className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        {server.display_name}
                        {server.is_global && (
                          <Globe className="h-3 w-3 text-muted-foreground" title="Global server" />
                        )}
                      </CardTitle>
                      <CardDescription className="text-xs font-mono">
                        {server.name}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${statusColor}`} title={statusText} />
                    <Badge variant={server.is_active ? "default" : "secondary"} className="text-xs">
                      {server.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2 text-sm">
                  {server.description && (
                    <p className="text-muted-foreground line-clamp-2">
                      {server.description}
                    </p>
                  )}

                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center">
                      <Wrench className="h-3 w-3 mr-1" />
                      Tools
                    </span>
                    <Badge variant="outline">{server.tool_count}</Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center">
                      {server.has_api_key ? (
                        <Lock className="h-3 w-3 mr-1" />
                      ) : (
                        <Globe className="h-3 w-3 mr-1" />
                      )}
                      Auth
                    </span>
                    <span className="text-xs">{server.has_api_key ? "API Key" : "None"}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center">
                      <Clock className="h-3 w-3 mr-1" />
                      Last Connected
                    </span>
                    <span className="text-xs">{formatDate(server.last_connected_at)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-4 pt-3 border-t">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleRefreshTools(server)}
                    disabled={refreshingId === server.id}
                  >
                    {refreshingId === server.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-1" />
                        Refresh
                      </>
                    )}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => openEditDialog(server)}>
                    <Settings className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => openDeleteDialog(server)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}

        {servers.length === 0 && !loading && (
          <Card className="col-span-full">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Server className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No MCP servers configured</h3>
              <p className="text-muted-foreground text-center mb-4">
                Add your first MCP server to extend agent capabilities with external tools.
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add MCP Server
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={(open) => {
        setShowEditDialog(open)
        if (!open) {
          setEditingServer(null)
          resetForm()
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit MCP Server: {editingServer?.display_name}</DialogTitle>
            <DialogDescription>
              Update the server configuration.
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="connection" className="mt-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="connection">Connection</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
            </TabsList>

            <TabsContent value="connection" className="space-y-4 mt-6">
              <div>
                <Label htmlFor="edit-name">Server Name (ID)</Label>
                <Input
                  id="edit-name"
                  value={formData.name}
                  disabled
                  className="bg-muted"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Name cannot be changed after creation
                </p>
              </div>

              <div>
                <Label htmlFor="edit-display_name">Display Name <span className="text-destructive">*</span></Label>
                <Input
                  id="edit-display_name"
                  value={formData.display_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
                  placeholder="e.g., Order Management API"
                />
                {formErrors.display_name && (
                  <p className="text-xs text-destructive mt-1">{formErrors.display_name}</p>
                )}
              </div>

              <div>
                <Label htmlFor="edit-server_url">Server URL <span className="text-destructive">*</span></Label>
                <Input
                  id="edit-server_url"
                  value={formData.server_url}
                  onChange={(e) => setFormData(prev => ({ ...prev, server_url: e.target.value }))}
                  placeholder="https://mcp-server.example.com"
                />
                {formErrors.server_url && (
                  <p className="text-xs text-destructive mt-1">{formErrors.server_url}</p>
                )}
              </div>

              <div>
                <Label htmlFor="edit-api_key">API Key</Label>
                <Input
                  id="edit-api_key"
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
                  placeholder={editingServer?.has_api_key ? "Leave empty to keep current key" : "Enter API key if required"}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {editingServer?.has_api_key
                    ? "Leave empty to keep the current API key"
                    : "Stored securely on the server"}
                </p>
              </div>

              <div>
                <Label htmlFor="edit-api_key_header_name">API Key Header</Label>
                <Select
                  value={API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name) ? formData.api_key_header_name : "__custom__"}
                  onValueChange={(value) => {
                    if (value === "__custom__") {
                      // Keep current custom value or set empty for user to fill
                      if (API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name)) {
                        setFormData(prev => ({ ...prev, api_key_header_name: "" }))
                      }
                    } else {
                      setFormData(prev => ({ ...prev, api_key_header_name: value }))
                    }
                  }}
                >
                  <SelectTrigger id="edit-api_key_header_name">
                    <SelectValue placeholder="Select header name" />
                  </SelectTrigger>
                  <SelectContent>
                    {API_KEY_HEADER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                    <SelectItem value="__custom__">Other (Custom)</SelectItem>
                  </SelectContent>
                </Select>
                {!API_KEY_HEADER_OPTIONS.some(opt => opt.value === formData.api_key_header_name) && (
                  <Input
                    className="mt-2"
                    value={formData.api_key_header_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, api_key_header_name: e.target.value }))}
                    placeholder="e.g., CONTEXT7_API_KEY"
                  />
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  HTTP header used to send the API key
                </p>
              </div>

              <div>
                <Label htmlFor="edit-description">Description</Label>
                <Textarea
                  id="edit-description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="What does this MCP server provide?"
                  className="min-h-[80px]"
                />
              </div>

              <Button
                variant="outline"
                onClick={handleTestConnection}
                disabled={testing || !formData.server_url}
                className="w-full"
              >
                {testing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Testing Connection...
                  </>
                ) : (
                  <>
                    <TestTube className="h-4 w-4 mr-2" />
                    Test Connection
                  </>
                )}
              </Button>
            </TabsContent>

            <TabsContent value="settings" className="space-y-4 mt-6">
              <div>
                <Label>Timeout: {formData.timeout_seconds}s</Label>
                <Slider
                  value={[formData.timeout_seconds]}
                  onValueChange={([value]) => setFormData(prev => ({ ...prev, timeout_seconds: value }))}
                  min={5}
                  max={120}
                  step={5}
                  className="mt-2"
                />
              </div>

              <div>
                <Label>Max Retries: {formData.max_retries}</Label>
                <Slider
                  value={[formData.max_retries]}
                  onValueChange={([value]) => setFormData(prev => ({ ...prev, max_retries: value }))}
                  min={0}
                  max={10}
                  step={1}
                  className="mt-2"
                />
              </div>

              <div className="flex items-center space-x-2 pt-4">
                <Checkbox
                  id="edit-is_global"
                  checked={formData.is_global}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_global: checked as boolean }))}
                />
                <Label htmlFor="edit-is_global" className="flex items-center">
                  <Globe className="h-4 w-4 mr-2" />
                  Make this server available to all users (Admin only)
                </Label>
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
            <Button variant="outline" onClick={() => setShowEditDialog(false)} disabled={saving}>
              Cancel
            </Button>
            <Button
              onClick={handleUpdateServer}
              disabled={saving || !formData.display_name || !formData.server_url}
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Testing & Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete MCP Server</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingServer?.display_name}"? This will permanently
              remove the server configuration. Agents using this server will no longer have access to its tools.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setShowDeleteDialog(false)
              setDeletingServer(null)
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteServer}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Server
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Test Result Dialog */}
      <Dialog open={showTestDialog} onOpenChange={setShowTestDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {testResult?.success ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Connection Successful
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-red-500" />
                  Connection Failed
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {testResult?.message}
            </DialogDescription>
          </DialogHeader>

          {testResult?.success && testResult.tools.length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium mb-2">Discovered Tools ({testResult.tool_count})</h4>
              <div className="max-h-60 overflow-y-auto space-y-2">
                {testResult.tools.map((tool, idx) => (
                  <div key={idx} className="p-2 rounded bg-muted">
                    <p className="font-mono text-sm">{tool.name}</p>
                    {tool.description && (
                      <p className="text-xs text-muted-foreground mt-1">{tool.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {testResult?.error && (
            <div className="mt-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
              {testResult.error}
            </div>
          )}

          {testResult?.response_time_ms && (
            <p className="text-xs text-muted-foreground mt-4">
              Response time: {testResult.response_time_ms}ms
            </p>
          )}

          <div className="flex justify-end mt-6">
            <Button onClick={() => setShowTestDialog(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
