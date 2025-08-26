"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { config } from "@/lib/config"
import { apiClient } from "@/lib/api-client"
import { 
  Settings, 
  Save, 
  RefreshCw, 
  Ticket, 
  Bot, 
  Plus, 
  Edit, 
  Trash2, 
  TestTube, 
  Play, 
  History,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock
} from "lucide-react"

interface ZammadConfiguration {
  id?: number
  name: string
  description?: string
  is_default: boolean
  zammad_url: string
  api_token: string
  chatbot_id: string
  process_state: string
  max_tickets: number
  skip_existing: boolean
  auto_process: boolean
  process_interval: number
  summary_template?: string
  custom_settings?: Record<string, any>
  created_at?: string
  updated_at?: string
  last_used_at?: string
}

interface Chatbot {
  id: string
  name: string
  chatbot_type: string
  model: string
  description?: string
}

interface ProcessingLog {
  id: number
  batch_id: string
  started_at: string
  completed_at?: string
  tickets_found: number
  tickets_processed: number
  tickets_failed: number
  tickets_skipped: number
  processing_time_seconds?: number
  status: string
}

interface ModuleStatus {
  module_health: {
    status: string
    message: string
    uptime: number
  }
  statistics: {
    total_tickets: number
    processed_tickets: number
    failed_tickets: number
    success_rate: number
  }
}

export function ZammadConfig() {
  const { toast } = useToast()
  const [configurations, setConfigurations] = useState<ZammadConfiguration[]>([])
  const [chatbots, setChatbots] = useState<Chatbot[]>([])
  const [processingLogs, setProcessingLogs] = useState<ProcessingLog[]>([])
  const [moduleStatus, setModuleStatus] = useState<ModuleStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [processing, setProcessing] = useState(false)
  
  // Form states
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingConfig, setEditingConfig] = useState<ZammadConfiguration | null>(null)
  // Get default Zammad URL from environment or use localhost fallback
  const getDefaultZammadUrl = () => {
    return process.env.NEXT_PUBLIC_DEFAULT_ZAMMAD_URL || "http://localhost:8080"
  }

  const [newConfig, setNewConfig] = useState<Partial<ZammadConfiguration>>({
    name: "",
    description: "",
    is_default: false,
    zammad_url: getDefaultZammadUrl(),
    api_token: "",
    chatbot_id: "",
    process_state: "open",
    max_tickets: 10,
    skip_existing: true,
    auto_process: false,
    process_interval: 30,
    summary_template: "Generate a concise summary of this support ticket including key issues, customer concerns, and any actions taken."
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      await Promise.all([
        fetchConfigurations(),
        fetchChatbots(),
        fetchProcessingLogs(),
        fetchModuleStatus()
      ])
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load Zammad configuration",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const fetchConfigurations = async () => {
    try {
      const data = await apiClient.get("/api-internal/v1/zammad/configurations")
      setConfigurations(data.configurations || [])
    } catch (error) {
      // Silent failure for configuration fetching
    }
  }

  const fetchChatbots = async () => {
    try {
      const data = await apiClient.get("/api-internal/v1/zammad/chatbots")
      setChatbots(data.chatbots || [])
    } catch (error) {
      // Silent failure for chatbot fetching
    }
  }

  const fetchProcessingLogs = async () => {
    try {
      const data = await apiClient.get("/api-internal/v1/zammad/processing-logs?limit=5")
      setProcessingLogs(data.logs || [])
    } catch (error) {
      // Silent failure for processing logs fetching
    }
  }

  const fetchModuleStatus = async () => {
    try {
      const data = await apiClient.get("/api-internal/v1/zammad/status")
      setModuleStatus(data)
    } catch (error) {
      // Silent failure for module status fetching
    }
  }

  const handleSaveConfiguration = async () => {
    try {
      setSaving(true)
      
      const url = editingConfig 
        ? `/api-internal/v1/zammad/configurations/${editingConfig.id}`
        : "/api-internal/v1/zammad/configurations"
      
      const method = editingConfig ? "PUT" : "POST"
      
      if (editingConfig) {
        await apiClient.put(url, newConfig)
      } else {
        await apiClient.post(url, newConfig)
      }

      toast({
        title: "Success",
        description: editingConfig 
          ? "Configuration updated successfully"
          : "Configuration created successfully"
      })

      setIsDialogOpen(false)
      setEditingConfig(null)
      setNewConfig({
        name: "",
        description: "",
        is_default: false,
        zammad_url: getDefaultZammadUrl(),
        api_token: "",
        chatbot_id: "",
        process_state: "open",
        max_tickets: 10,
        skip_existing: true,
        auto_process: false,
        process_interval: 30,
        summary_template: "Generate a concise summary of this support ticket including key issues, customer concerns, and any actions taken."
      })
      
      await fetchConfigurations()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save configuration",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    if (!newConfig.zammad_url || !newConfig.api_token) {
      toast({
        title: "Error",
        description: "Please enter Zammad URL and API token",
        variant: "destructive"
      })
      return
    }

    try {
      setTestingConnection(true)
      
      const data = await apiClient.post("/api-internal/v1/zammad/test-connection", {
        zammad_url: newConfig.zammad_url,
        api_token: newConfig.api_token
      })
      if (data.status === "success") {
        toast({
          title: "✅ Connection Successful",
          description: `Connected to Zammad as ${data.user}`,
          duration: 5000
        })
      } else {
        toast({
          title: "❌ Connection Failed",
          description: data.message || "Unknown error occurred",
          variant: "destructive",
          duration: 8000
        })
      }
    } catch (error) {
      toast({
        title: "⚠️ Connection Test Error",
        description: `Failed to test connection: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
        duration: 8000
      })
    } finally {
      setTestingConnection(false)
    }
  }

  const handleProcessTickets = async (configId?: number) => {
    try {
      setProcessing(true)
      
      const data = await apiClient.post("/api-internal/v1/zammad/process", {
        config_id: configId,
        filters: {}
      })

      toast({
        title: "Processing Started",
        description: data.message || "Ticket processing has been started"
      })

      // Refresh logs after a short delay
      setTimeout(() => {
        fetchProcessingLogs()
        fetchModuleStatus()
      }, 2000)
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to process tickets",
        variant: "destructive"
      })
    } finally {
      setProcessing(false)
    }
  }

  const handleDeleteConfiguration = async (id: number) => {
    try {
      await apiClient.delete(`/api-internal/v1/zammad/configurations/${id}`)

      toast({
        title: "Success",
        description: "Configuration deleted successfully"
      })

      await fetchConfigurations()
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete configuration",
        variant: "destructive"
      })
    }
  }

  const handleEditConfiguration = (config: ZammadConfiguration) => {
    setEditingConfig(config)
    setNewConfig({
      ...config,
      api_token: "" // Don't pre-fill the API token for security
    })
    setIsDialogOpen(true)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "running":
        return <Clock className="h-4 w-4 text-blue-500" />
      default:
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      completed: "default",
      failed: "destructive",
      running: "secondary"
    }
    return <Badge variant={variants[status] || "outline"}>{status}</Badge>
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center">
            <Ticket className="mr-3 h-8 w-8" />
            Zammad Integration
          </h1>
          <p className="text-muted-foreground">
            AI-powered ticket summarization for Zammad ticketing systems
          </p>
        </div>
        <div className="flex space-x-2">
          <Button onClick={fetchData} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Configuration
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>
                  {editingConfig ? "Edit Configuration" : "Add Zammad Configuration"}
                </DialogTitle>
                <DialogDescription>
                  Configure connection to your Zammad instance and processing settings
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4">
                {/* Basic Settings */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="name">Configuration Name</Label>
                    <Input
                      id="name"
                      value={newConfig.name || ""}
                      onChange={(e) => setNewConfig({ ...newConfig, name: e.target.value })}
                      placeholder="My Zammad Instance"
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={newConfig.is_default || false}
                      onCheckedChange={(checked) => setNewConfig({ ...newConfig, is_default: checked })}
                    />
                    <Label>Default Configuration</Label>
                  </div>
                </div>

                <div>
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    value={newConfig.description || ""}
                    onChange={(e) => setNewConfig({ ...newConfig, description: e.target.value })}
                    placeholder="Optional description"
                  />
                </div>

                {/* Zammad Connection */}
                <div className="space-y-4">
                  <h4 className="font-medium">Zammad Connection</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="zammad_url">Zammad URL</Label>
                      <Input
                        id="zammad_url"
                        value={newConfig.zammad_url || ""}
                        onChange={(e) => setNewConfig({ ...newConfig, zammad_url: e.target.value })}
                        placeholder={getDefaultZammadUrl()}
                      />
                    </div>
                    <div>
                      <Label htmlFor="api_token">API Token</Label>
                      <Input
                        id="api_token"
                        type="password"
                        value={newConfig.api_token || ""}
                        onChange={(e) => setNewConfig({ ...newConfig, api_token: e.target.value })}
                        placeholder="Your Zammad API token"
                      />
                    </div>
                  </div>
                  <Button 
                    onClick={handleTestConnection} 
                    variant="outline" 
                    disabled={testingConnection}
                  >
                    <TestTube className="mr-2 h-4 w-4" />
                    {testingConnection ? "Testing..." : "Test Connection"}
                  </Button>
                </div>

                {/* Chatbot Selection */}
                <div>
                  <Label htmlFor="chatbot_id">Chatbot</Label>
                  <Select
                    value={newConfig.chatbot_id || ""}
                    onValueChange={(value) => setNewConfig({ ...newConfig, chatbot_id: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a chatbot" />
                    </SelectTrigger>
                    <SelectContent>
                      {chatbots.map((chatbot) => (
                        <SelectItem key={chatbot.id} value={chatbot.id}>
                          {chatbot.name} ({chatbot.chatbot_type})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Processing Settings */}
                <div className="space-y-4">
                  <h4 className="font-medium">Processing Settings</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="process_state">Process State</Label>
                      <Select
                        value={newConfig.process_state || "open"}
                        onValueChange={(value) => setNewConfig({ ...newConfig, process_state: value })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="open">Open</SelectItem>
                          <SelectItem value="pending">Pending</SelectItem>
                          <SelectItem value="closed">Closed</SelectItem>
                          <SelectItem value="all">All</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="max_tickets">Max Tickets Per Run</Label>
                      <Input
                        id="max_tickets"
                        type="number"
                        min="1"
                        max="100"
                        value={newConfig.max_tickets || 10}
                        onChange={(e) => setNewConfig({ ...newConfig, max_tickets: parseInt(e.target.value) })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={newConfig.skip_existing || false}
                        onCheckedChange={(checked) => setNewConfig({ ...newConfig, skip_existing: checked })}
                      />
                      <Label>Skip Existing Summaries</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={newConfig.auto_process || false}
                        onCheckedChange={(checked) => setNewConfig({ ...newConfig, auto_process: checked })}
                      />
                      <Label>Auto Process</Label>
                    </div>
                  </div>

                  {newConfig.auto_process && (
                    <div>
                      <Label htmlFor="process_interval">Process Interval (minutes)</Label>
                      <Input
                        id="process_interval"
                        type="number"
                        min="5"
                        max="1440"
                        value={newConfig.process_interval || 30}
                        onChange={(e) => setNewConfig({ ...newConfig, process_interval: parseInt(e.target.value) })}
                      />
                    </div>
                  )}
                </div>

                {/* Summary Template */}
                <div>
                  <Label htmlFor="summary_template">Summary Template</Label>
                  <Textarea
                    id="summary_template"
                    value={newConfig.summary_template || ""}
                    onChange={(e) => setNewConfig({ ...newConfig, summary_template: e.target.value })}
                    placeholder="Custom template for AI summaries"
                    rows={3}
                  />
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveConfiguration} disabled={saving}>
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? "Saving..." : "Save"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Module Status */}
      {moduleStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Settings className="mr-2 h-5 w-5" />
              Module Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{moduleStatus.statistics.total_tickets}</div>
                <p className="text-xs text-muted-foreground">Total Tickets</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{moduleStatus.statistics.processed_tickets}</div>
                <p className="text-xs text-muted-foreground">Processed</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{moduleStatus.statistics.failed_tickets}</div>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">{moduleStatus.statistics.success_rate.toFixed(1)}%</div>
                <p className="text-xs text-muted-foreground">Success Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="configurations" className="space-y-6">
        <TabsList>
          <TabsTrigger value="configurations">Configurations</TabsTrigger>
          <TabsTrigger value="processing">Processing Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="configurations" className="space-y-4">
          {configurations.length === 0 ? (
            <Card>
              <CardContent className="text-center py-8">
                <p className="text-muted-foreground">No configurations found. Create your first configuration to get started.</p>
              </CardContent>
            </Card>
          ) : (
            configurations.map((config) => (
              <Card key={config.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center">
                        {config.name}
                        {config.is_default && (
                          <Badge variant="secondary" className="ml-2">Default</Badge>
                        )}
                      </CardTitle>
                      <CardDescription>
                        {config.description || config.zammad_url}
                      </CardDescription>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleProcessTickets(config.id)}
                        disabled={processing}
                      >
                        <Play className="mr-2 h-3 w-3" />
                        Process
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEditConfiguration(config)}
                      >
                        <Edit className="mr-2 h-3 w-3" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteConfiguration(config.id!)}
                      >
                        <Trash2 className="mr-2 h-3 w-3" />
                        Delete
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="font-medium">State:</span> {config.process_state}
                    </div>
                    <div>
                      <span className="font-medium">Max Tickets:</span> {config.max_tickets}
                    </div>
                    <div>
                      <span className="font-medium">Auto Process:</span> {config.auto_process ? "Yes" : "No"}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="processing" className="space-y-4">
          {processingLogs.length === 0 ? (
            <Card>
              <CardContent className="text-center py-8">
                <p className="text-muted-foreground">No processing logs found.</p>
              </CardContent>
            </Card>
          ) : (
            processingLogs.map((log) => (
              <Card key={log.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(log.status)}
                      <div>
                        <CardTitle className="text-lg">Batch {log.batch_id.slice(0, 8)}</CardTitle>
                        <CardDescription>
                          Started: {new Date(log.started_at).toLocaleString()}
                        </CardDescription>
                      </div>
                    </div>
                    {getStatusBadge(log.status)}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Found:</span> {log.tickets_found}
                    </div>
                    <div>
                      <span className="font-medium">Processed:</span> {log.tickets_processed}
                    </div>
                    <div>
                      <span className="font-medium">Failed:</span> {log.tickets_failed}
                    </div>
                    <div>
                      <span className="font-medium">Skipped:</span> {log.tickets_skipped}
                    </div>
                  </div>
                  {log.processing_time_seconds && (
                    <div className="mt-2 text-sm">
                      <span className="font-medium">Duration:</span> {log.processing_time_seconds}s
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}