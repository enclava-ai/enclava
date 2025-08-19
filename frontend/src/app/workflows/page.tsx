"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/hooks/use-toast"
import { 
  Plus, 
  Play, 
  Settings, 
  Trash2, 
  Copy,
  Eye,
  Search,
  Filter,
  Clock,
  CheckCircle,
  XCircle,
  Loader,
  Workflow as WorkflowIcon,
  RotateCcw,
  Square,
  Activity,
  TrendingUp,
  AlertCircle,
  FileText,
  Download,
  RefreshCw,
  Upload
} from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import ProtectedRoute from "@/components/ProtectedRoute"

interface WorkflowDefinition {
  id: string
  name: string
  description: string
  version: string
  steps: any[]
  variables: Record<string, any>
  metadata: Record<string, any>
  created_at?: string
  updated_at?: string
}

interface WorkflowExecution {
  id: string
  workflow_id: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  current_step?: string
  started_at?: string
  completed_at?: string
  error?: string
  results: Record<string, any>
}

interface WorkflowTemplate {
  id: string
  name: string
  description: string
  definition: WorkflowDefinition
  category?: string
}

const statusIcons = {
  pending: <Clock className="h-4 w-4 text-yellow-500" />,
  running: <Loader className="h-4 w-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
  cancelled: <XCircle className="h-4 w-4 text-gray-500" />
}

const statusColors = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300"
}

export default function WorkflowsPage() {
  const { toast } = useToast()
  const router = useRouter()
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [executions, setExecutions] = useState<WorkflowExecution[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null)
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showExecutionDetails, setShowExecutionDetails] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [activeTab, setActiveTab] = useState("workflows")
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [workflowToDelete, setWorkflowToDelete] = useState<WorkflowDefinition | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  // Real-time updates for executions
  useEffect(() => {
    if (!autoRefresh || activeTab !== "executions") return

    const interval = setInterval(() => {
      loadExecutions()
    }, 5000) // Refresh every 5 seconds

    return () => clearInterval(interval)
  }, [autoRefresh, activeTab])

  const loadData = async () => {
    try {
      setLoading(true)
      await Promise.all([
        loadWorkflows(),
        loadExecutions(),
        loadTemplates()
      ])
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load workflow data",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadWorkflows = async () => {
    try {
      const response = await fetch('/api/workflows')
      if (response.ok) {
        const data = await response.json()
        setWorkflows(data.workflows || [])
      } else {
        // Fallback to empty array if API fails
        console.error('Failed to load workflows from API')
        setWorkflows([])
      }
    } catch (error) {
      console.error('Error loading workflows:', error)
      // Fallback to empty array on error
      setWorkflows([])
    }
  }

  const loadExecutions = async () => {
    try {
      const response = await fetch('/api/workflows/executions')
      if (response.ok) {
        const data = await response.json()
        setExecutions(data.executions || [])
      } else {
        // Fallback to mock data for development
        setExecutions([
          {
            id: "ex-1",
            workflow_id: "wf-1",
            status: "completed",
            started_at: new Date(Date.now() - 300000).toISOString(),
            completed_at: new Date().toISOString(),
            results: { response: "Support ticket resolved successfully" }
          },
          {
            id: "ex-2",
            workflow_id: "wf-2", 
            status: "running",
            current_step: "research_phase",
            started_at: new Date(Date.now() - 60000).toISOString(),
            results: {}
          },
          {
            id: "ex-3",
            workflow_id: "wf-1",
            status: "failed",
            started_at: new Date(Date.now() - 180000).toISOString(),
            completed_at: new Date(Date.now() - 120000).toISOString(),
            error: "Chatbot service unavailable",
            results: {}
          }
        ])
      }
    } catch (error) {
      // Fallback to mock data
      setExecutions([
        {
          id: "ex-1",
          workflow_id: "wf-1",
          status: "completed",
          started_at: new Date(Date.now() - 300000).toISOString(),
          completed_at: new Date().toISOString(),
          results: { response: "Support ticket resolved successfully" }
        },
        {
          id: "ex-2",
          workflow_id: "wf-2", 
          status: "running",
          current_step: "research_phase",
          started_at: new Date(Date.now() - 60000).toISOString(),
          results: {}
        },
        {
          id: "ex-3",
          workflow_id: "wf-1",
          status: "failed",
          started_at: new Date(Date.now() - 180000).toISOString(),
          completed_at: new Date(Date.now() - 120000).toISOString(),
          error: "Chatbot service unavailable",
          results: {}
        }
      ])
    }
  }

  const loadTemplates = async () => {
    try {
      const response = await fetch('/api/workflows/templates')
      if (response.ok) {
        const data = await response.json()
        setTemplates(data.templates || [])
      }
    } catch (error) {
      // Set some default templates as fallback
      setTemplates([
        {
          id: "simple_chat",
          name: "Simple Chat Workflow",
          description: "Basic LLM chat interaction",
          definition: {
            id: "simple_chat",
            name: "Simple Chat",
            description: "Basic LLM chat interaction",
            version: "1.0.0",
            steps: [],
            variables: {},
            metadata: {}
          }
        }
      ])
    }
  }

  const executeWorkflow = async (workflow: WorkflowDefinition) => {
    try {
      const response = await fetch('/api/workflows/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_def: workflow,
          input_data: {}
        })
      })

      if (response.ok) {
        const result = await response.json()
        toast({
          title: "Workflow Started",
          description: `Execution ID: ${result.execution_id}`
        })
        await loadExecutions()
      } else {
        throw new Error('Failed to execute workflow')
      }
    } catch (error) {
      toast({
        title: "Execution Failed",
        description: "Failed to start workflow execution",
        variant: "destructive"
      })
    }
  }

  const createFromTemplate = (template: WorkflowTemplate) => {
    // Navigate to workflow builder with template
    router.push(`/workflows/builder?template=${template.id}`)
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setImportFile(file)
    }
  }

  const importWorkflow = async () => {
    if (!importFile) {
      toast({
        title: "No File Selected",
        description: "Please select a JSON file to import",
        variant: "destructive"
      })
      return
    }

    setIsImporting(true)
    try {
      const formData = new FormData()
      formData.append('workflow_file', importFile)

      const response = await fetch('/api/workflows/import', {
        method: 'POST',
        body: formData
      })

      const result = await response.json()

      if (response.ok) {
        toast({
          title: "Import Successful",
          description: `Workflow "${result.workflow?.name || 'Unknown'}" has been imported successfully`
        })
        setShowImportDialog(false)
        setImportFile(null)
        await loadWorkflows() // Refresh workflow list
      } else {
        throw new Error(result.error || 'Import failed')
      }
    } catch (error) {
      toast({
        title: "Import Failed",
        description: error instanceof Error ? error.message : "Failed to import workflow",
        variant: "destructive"
      })
    } finally {
      setIsImporting(false)
    }
  }

  const filteredWorkflows = workflows.filter(workflow =>
    workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const filteredExecutions = executions.filter(execution => 
    statusFilter === "all" || execution.status === statusFilter
  )

  const getWorkflowName = (workflowId: string) => {
    const workflow = workflows.find(w => w.id === workflowId)
    return workflow?.name || workflowId
  }

  const cancelExecution = async (executionId: string) => {
    try {
      const response = await fetch(`/api/workflows/executions/${executionId}/cancel`, {
        method: 'POST'
      })
      
      if (response.ok) {
        toast({
          title: "Execution Cancelled",
          description: `Execution ${executionId} has been cancelled`
        })
        await loadExecutions()
      } else {
        throw new Error('Failed to cancel execution')
      }
    } catch (error) {
      toast({
        title: "Cancel Failed", 
        description: "Failed to cancel execution",
        variant: "destructive"
      })
    }
  }

  const retryExecution = async (execution: WorkflowExecution) => {
    try {
      const workflow = workflows.find(w => w.id === execution.workflow_id)
      if (!workflow) throw new Error('Workflow not found')
      
      await executeWorkflow(workflow)
      toast({
        title: "Execution Retried",
        description: "A new execution has been started"
      })
    } catch (error) {
      toast({
        title: "Retry Failed",
        description: "Failed to retry execution", 
        variant: "destructive"
      })
    }
  }

  const confirmDeleteWorkflow = (workflow: WorkflowDefinition) => {
    setWorkflowToDelete(workflow)
    setShowDeleteDialog(true)
  }

  const deleteWorkflow = async () => {
    if (!workflowToDelete) return

    try {
      const response = await fetch(`/api/workflows/${workflowToDelete.id}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        toast({
          title: "Workflow Deleted",
          description: `"${workflowToDelete.name}" has been deleted successfully`
        })
        await loadWorkflows() // Refresh the workflow list
        setShowDeleteDialog(false)
        setWorkflowToDelete(null)
      } else {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to delete workflow')
      }
    } catch (error) {
      toast({
        title: "Delete Failed",
        description: error instanceof Error ? error.message : "Failed to delete workflow",
        variant: "destructive"
      })
    }
  }

  const viewExecutionDetails = (execution: WorkflowExecution) => {
    setSelectedExecution(execution)
    setShowExecutionDetails(true)
  }

  const getExecutionDuration = (execution: WorkflowExecution) => {
    if (!execution.started_at) return null
    
    const start = new Date(execution.started_at)
    const end = execution.completed_at ? new Date(execution.completed_at) : new Date()
    const duration = Math.round((end.getTime() - start.getTime()) / 1000)
    
    if (duration < 60) return `${duration}s`
    if (duration < 3600) return `${Math.round(duration / 60)}m ${duration % 60}s`
    return `${Math.round(duration / 3600)}h ${Math.round((duration % 3600) / 60)}m`
  }

  const getStatusSummary = () => {
    const summary = executions.reduce((acc, exec) => {
      acc[exec.status] = (acc[exec.status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    return {
      total: executions.length,
      running: summary.running || 0,
      completed: summary.completed || 0,
      failed: summary.failed || 0,
      pending: summary.pending || 0,
      cancelled: summary.cancelled || 0
    }
  }

  if (loading) {
    return (
      <ProtectedRoute>
        <div className="container mx-auto py-8">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </div>
      </ProtectedRoute>
    )
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <WorkflowIcon className="h-8 w-8" />
              Workflow Management
            </h1>
            <p className="text-muted-foreground">Create, manage, and execute automated workflows</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={loadData}>
              <Settings className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <Upload className="h-4 w-4 mr-2" />
                  Import Workflow
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Import Workflow</DialogTitle>
                  <DialogDescription>
                    Upload a JSON workflow file to import into your workspace
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="workflow-file">Select Workflow File</Label>
                    <Input
                      id="workflow-file"
                      type="file"
                      accept=".json"
                      onChange={handleFileUpload}
                      className="cursor-pointer"
                    />
                    <p className="text-xs text-muted-foreground">
                      Only JSON files are supported (max 10MB)
                    </p>
                  </div>
                  
                  {importFile && (
                    <div className="p-3 bg-muted rounded-md">
                      <p className="text-sm font-medium">Selected File:</p>
                      <p className="text-sm text-muted-foreground">{importFile.name}</p>
                      <p className="text-xs text-muted-foreground">
                        Size: {(importFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  )}
                  
                  <div className="flex gap-2 justify-end">
                    <Button 
                      variant="outline" 
                      onClick={() => {
                        setShowImportDialog(false)
                        setImportFile(null)
                      }}
                      disabled={isImporting}
                    >
                      Cancel
                    </Button>
                    <Button 
                      onClick={importWorkflow}
                      disabled={!importFile || isImporting}
                    >
                      {isImporting ? (
                        <>
                          <Loader className="h-4 w-4 mr-2 animate-spin" />
                          Importing...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4 mr-2" />
                          Import
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Workflow
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Create New Workflow</DialogTitle>
                  <DialogDescription>
                    Choose how to create your workflow
                  </DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card className="cursor-pointer hover:shadow-md transition-shadow">
                    <CardHeader>
                      <CardTitle className="text-lg">Start from Scratch</CardTitle>
                      <CardDescription>Create a custom workflow from the ground up</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button className="w-full" onClick={() => {
                        setShowCreateDialog(false)
                        router.push('/workflows/builder')
                      }}>
                        <Plus className="h-4 w-4 mr-2" />
                        Create Custom
                      </Button>
                    </CardContent>
                  </Card>
                  
                  <Card className="cursor-pointer hover:shadow-md transition-shadow">
                    <CardHeader>
                      <CardTitle className="text-lg">Use Template</CardTitle>
                      <CardDescription>Start with a pre-built workflow template</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button variant="outline" className="w-full" onClick={() => {
                        setShowCreateDialog(false)
                        setActiveTab("templates")
                      }}>
                        <Copy className="h-4 w-4 mr-2" />
                        Browse Templates
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList>
            <TabsTrigger value="workflows">Workflows ({workflows.length})</TabsTrigger>
            <TabsTrigger value="executions">Executions ({executions.length})</TabsTrigger>
            <TabsTrigger value="templates">Templates ({templates.length})</TabsTrigger>
          </TabsList>

          {/* Workflows Tab */}
          <TabsContent value="workflows" className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search workflows..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredWorkflows.map((workflow) => (
                <Card key={workflow.id} className="hover:shadow-md transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{workflow.name}</CardTitle>
                        <CardDescription>{workflow.description}</CardDescription>
                      </div>
                      <Badge variant="secondary">v{workflow.version}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{workflow.steps.length} steps</span>
                        <span>•</span>
                        <span>{Object.keys(workflow.variables).length} variables</span>
                      </div>
                      
                      {workflow.metadata.tags && (
                        <div className="flex flex-wrap gap-1">
                          {workflow.metadata.tags.map((tag: string) => (
                            <Badge key={tag} variant="outline" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}

                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          onClick={() => executeWorkflow(workflow)}
                          className="flex-1"
                        >
                          <Play className="h-3 w-3 mr-1" />
                          Execute
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setSelectedWorkflow(workflow)}>
                          <Eye className="h-3 w-3" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => router.push(`/workflows/builder?id=${workflow.id}`)}
                        >
                          <Settings className="h-3 w-3" />
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => confirmDeleteWorkflow(workflow)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {filteredWorkflows.length === 0 && (
              <Card>
                <CardContent className="text-center py-8">
                  <WorkflowIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No workflows found</h3>
                  <p className="text-muted-foreground mb-4">
                    {searchTerm ? "No workflows match your search criteria" : "Get started by creating your first workflow"}
                  </p>
                  <Button onClick={() => setShowCreateDialog(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Your First Workflow
                  </Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Executions Tab */}
          <TabsContent value="executions" className="space-y-4">
            {/* Execution Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {(() => {
                const summary = getStatusSummary()
                return (
                  <>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <Activity className="h-4 w-4 text-blue-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Total</p>
                            <p className="text-xl font-bold">{summary.total}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <Loader className="h-4 w-4 text-blue-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Running</p>
                            <p className="text-xl font-bold">{summary.running}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-4 w-4 text-green-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Completed</p>
                            <p className="text-xl font-bold">{summary.completed}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <XCircle className="h-4 w-4 text-red-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Failed</p>
                            <p className="text-xl font-bold">{summary.failed}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-yellow-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Pending</p>
                            <p className="text-xl font-bold">{summary.pending}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                          <Square className="h-4 w-4 text-gray-500" />
                          <div>
                            <p className="text-sm text-muted-foreground">Cancelled</p>
                            <p className="text-xl font-bold">{summary.cancelled}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </>
                )
              })()}
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={autoRefresh ? "bg-green-50 border-green-200" : ""}
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${autoRefresh ? "animate-spin" : ""}`} />
                  Auto Refresh {autoRefresh ? "On" : "Off"}
                </Button>
                <Button variant="outline" size="sm" onClick={loadExecutions}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh Now
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              {filteredExecutions.map((execution) => (
                <Card key={execution.id}>
                  <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          {statusIcons[execution.status]}
                          <Badge className={statusColors[execution.status]}>
                            {execution.status}
                          </Badge>
                        </div>
                        <div>
                          <p className="font-medium">{getWorkflowName(execution.workflow_id)}</p>
                          <p className="text-sm text-muted-foreground">
                            Execution ID: {execution.id}
                            {execution.current_step && ` • Current: ${execution.current_step}`}
                          </p>
                          {getExecutionDuration(execution) && (
                            <p className="text-xs text-muted-foreground">
                              Duration: {getExecutionDuration(execution)}
                            </p>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <div className="text-right text-sm text-muted-foreground mr-4">
                          {execution.started_at && (
                            <p>Started: {new Date(execution.started_at).toLocaleString()}</p>
                          )}
                          {execution.completed_at && (
                            <p>Completed: {new Date(execution.completed_at).toLocaleString()}</p>
                          )}
                          {execution.error && (
                            <p className="text-red-500">Error: {execution.error}</p>
                          )}
                        </div>
                        
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => viewExecutionDetails(execution)}
                          >
                            <Eye className="h-3 w-3" />
                          </Button>
                          
                          {execution.status === "running" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => cancelExecution(execution.id)}
                              className="text-red-600 hover:text-red-700"
                            >
                              <Square className="h-3 w-3" />
                            </Button>
                          )}
                          
                          {execution.status === "failed" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => retryExecution(execution)}
                              className="text-blue-600 hover:text-blue-700"
                            >
                              <RotateCcw className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {filteredExecutions.length === 0 && (
              <Card>
                <CardContent className="text-center py-8">
                  <Clock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No executions found</h3>
                  <p className="text-muted-foreground">
                    {statusFilter !== "all" ? `No executions with status "${statusFilter}"` : "No workflow executions yet"}
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Templates Tab */}
          <TabsContent value="templates" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <Card key={template.id} className="hover:shadow-md transition-shadow">
                  <CardHeader>
                    <CardTitle className="text-lg">{template.name}</CardTitle>
                    <CardDescription>{template.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {template.category && (
                        <Badge variant="outline">{template.category}</Badge>
                      )}
                      <Button 
                        className="w-full" 
                        onClick={() => createFromTemplate(template)}
                      >
                        <Copy className="h-4 w-4 mr-2" />
                        Use Template
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {templates.length === 0 && (
              <Card>
                <CardContent className="text-center py-8">
                  <Copy className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No templates available</h3>
                  <p className="text-muted-foreground">
                    Workflow templates help you get started quickly with pre-built workflows
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>

        {/* Execution Details Modal */}
        <Dialog open={showExecutionDetails} onOpenChange={setShowExecutionDetails}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Execution Details
              </DialogTitle>
              <DialogDescription>
                Detailed information about workflow execution
              </DialogDescription>
            </DialogHeader>
            
            {selectedExecution && (
              <div className="space-y-6">
                {/* Basic Information */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Basic Information</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Execution ID:</span>
                        <span className="text-sm font-mono">{selectedExecution.id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Workflow:</span>
                        <span className="text-sm">{getWorkflowName(selectedExecution.workflow_id)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Status:</span>
                        <Badge className={statusColors[selectedExecution.status]}>
                          {selectedExecution.status}
                        </Badge>
                      </div>
                      {selectedExecution.current_step && (
                        <div className="flex justify-between">
                          <span className="text-sm text-muted-foreground">Current Step:</span>
                          <span className="text-sm">{selectedExecution.current_step}</span>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Timing</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {selectedExecution.started_at && (
                        <div className="flex justify-between">
                          <span className="text-sm text-muted-foreground">Started:</span>
                          <span className="text-sm">{new Date(selectedExecution.started_at).toLocaleString()}</span>
                        </div>
                      )}
                      {selectedExecution.completed_at && (
                        <div className="flex justify-between">
                          <span className="text-sm text-muted-foreground">Completed:</span>
                          <span className="text-sm">{new Date(selectedExecution.completed_at).toLocaleString()}</span>
                        </div>
                      )}
                      {getExecutionDuration(selectedExecution) && (
                        <div className="flex justify-between">
                          <span className="text-sm text-muted-foreground">Duration:</span>
                          <span className="text-sm font-mono">{getExecutionDuration(selectedExecution)}</span>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Error Details */}
                {selectedExecution.error && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base text-red-600 flex items-center gap-2">
                        <AlertCircle className="h-4 w-4" />
                        Error Details
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="bg-red-50 border border-red-200 rounded-md p-3">
                        <p className="text-sm text-red-800 font-mono">{selectedExecution.error}</p>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Results */}
                {Object.keys(selectedExecution.results).length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        Results
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="bg-gray-50 border rounded-md p-3">
                        <pre className="text-xs overflow-x-auto">
                          {JSON.stringify(selectedExecution.results, null, 2)}
                        </pre>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-2">
                  {selectedExecution.status === "running" && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        cancelExecution(selectedExecution.id)
                        setShowExecutionDetails(false)
                      }}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Square className="h-4 w-4 mr-2" />
                      Cancel Execution
                    </Button>
                  )}
                  
                  {selectedExecution.status === "failed" && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        retryExecution(selectedExecution)
                        setShowExecutionDetails(false)
                      }}
                      className="text-blue-600 hover:text-blue-700"
                    >
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Retry Execution
                    </Button>
                  )}
                  
                  <Button
                    variant="outline"
                    onClick={() => {
                      const data = JSON.stringify(selectedExecution, null, 2)
                      const blob = new Blob([data], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `execution-${selectedExecution.id}.json`
                      document.body.appendChild(a)
                      a.click()
                      document.body.removeChild(a)
                      URL.revokeObjectURL(url)
                    }}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export Details
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <AlertCircle className="h-5 w-5" />
                Delete Workflow
              </DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this workflow? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            
            {workflowToDelete && (
              <div className="space-y-4">
                <div className="p-4 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-800">
                    <strong>Workflow:</strong> {workflowToDelete.name}
                  </p>
                  <p className="text-sm text-red-600 mt-1">
                    {workflowToDelete.description}
                  </p>
                </div>
                
                <div className="flex gap-2 justify-end">
                  <Button 
                    variant="outline" 
                    onClick={() => {
                      setShowDeleteDialog(false)
                      setWorkflowToDelete(null)
                    }}
                  >
                    Cancel
                  </Button>
                  <Button 
                    variant="destructive"
                    onClick={deleteWorkflow}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Workflow
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </ProtectedRoute>
  )
}