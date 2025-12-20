"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Plus,
  Settings,
  Trash2,
  Play,
  Bot,
  Wrench,
  Brain,
  Code,
  Search,
  Globe,
  Server,
  Database
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { AgentChatInterface } from "./AgentChatInterface"
import { MCPServerManager } from "./MCPServerManager"
import ModelSelector from "@/components/playground/ModelSelector"
import { agentApi, toolApi, mcpServerApi, apiClient } from "@/lib/api-client"
import type { AgentConfig, CreateAgentConfigRequest, Tool, RagCollection } from "@/types/agent"
import { BUILTIN_TOOLS, AGENT_CATEGORIES } from "@/types/agent"
import type { AvailableMCPServersResponse } from "@/types/mcp-server"

const AGENT_TYPE_ICONS: Record<string, typeof Bot> = {
  support: Bot,
  development: Code,
  research: Brain,
  general: Wrench
}

export function AgentConfigManager() {
  const [mainTab, setMainTab] = useState<string>("agents")
  const [agents, setAgents] = useState<AgentConfig[]>([])
  const [availableTools, setAvailableTools] = useState<Tool[]>([])
  const [availableMCPServers, setAvailableMCPServers] = useState<AvailableMCPServersResponse["servers"]>([])
  const [ragCollections, setRagCollections] = useState<RagCollection[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deletingAgent, setDeletingAgent] = useState<AgentConfig | null>(null)
  const [editingAgent, setEditingAgent] = useState<AgentConfig | null>(null)
  const [showChatInterface, setShowChatInterface] = useState(false)
  const [testingAgent, setTestingAgent] = useState<AgentConfig | null>(null)
  const { toast } = useToast()

  // New agent form state
  const [newAgent, setNewAgent] = useState<CreateAgentConfigRequest>({
    name: "",
    display_name: "",
    description: "",
    system_prompt: "",
    model: "gpt-oss-120b",
    temperature: 0.7,
    max_tokens: 2000,
    builtin_tools: [],
    mcp_servers: [],
    include_custom_tools: true,
    tool_choice: "auto",
    max_iterations: 5,
    category: "general",
    tags: [],
    is_public: false,
    tool_resources: undefined
  })

  // Edit agent form state
  const [editAgent, setEditAgent] = useState<CreateAgentConfigRequest>({
    name: "",
    display_name: "",
    description: "",
    system_prompt: "",
    model: "gpt-oss-120b",
    temperature: 0.7,
    max_tokens: 2000,
    builtin_tools: [],
    mcp_servers: [],
    include_custom_tools: true,
    tool_choice: "auto",
    max_iterations: 5,
    category: "general",
    tags: [],
    is_public: false,
    tool_resources: undefined
  })

  useEffect(() => {
    loadAgents()
    loadTools()
    loadMCPServers()
    loadRagCollections()
  }, [])

  const loadAgents = async () => {
    try {
      const data = await agentApi.listAgents()
      setAgents(data.configs || [])
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load agents",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadTools = async () => {
    try {
      const data = await toolApi.listTools()
      setAvailableTools(data.tools || [])
    } catch (error) {
      console.error('Failed to load tools:', error)
    }
  }

  const loadMCPServers = async () => {
    try {
      const data = await mcpServerApi.getAvailableServers()
      setAvailableMCPServers(data.servers || [])
    } catch (error) {
      console.error('Failed to load MCP servers:', error)
    }
  }

  const loadRagCollections = async () => {
    try {
      const data = await apiClient.get('/api-internal/v1/rag/collections')
      setRagCollections(data.collections || [])
    } catch (error) {
      console.error('Failed to load RAG collections:', error)
    }
  }

  const handleTestChat = (agent: AgentConfig) => {
    setTestingAgent(agent)
    setShowChatInterface(true)
  }

  const handleEditAgent = (agent: AgentConfig) => {
    setEditingAgent(agent)
    setEditAgent({
      name: agent.name,
      display_name: agent.display_name,
      description: agent.description,
      system_prompt: agent.system_prompt,
      model: agent.model,
      temperature: agent.temperature,
      max_tokens: agent.max_tokens,
      builtin_tools: agent.tools_config.builtin_tools,
      mcp_servers: agent.tools_config.mcp_servers,
      include_custom_tools: agent.tools_config.include_custom_tools,
      tool_choice: agent.tools_config.tool_choice,
      max_iterations: agent.tools_config.max_iterations,
      category: agent.category,
      tags: agent.tags,
      is_public: agent.is_public,
      tool_resources: agent.tool_resources
    })
    setShowEditDialog(true)
  }

  const createAgent = async () => {
    try {
      const agent = await agentApi.createAgent(newAgent)
      setAgents(prev => [...prev, agent])
      setShowCreateDialog(false)
      resetForm()
      toast({
        title: "Success",
        description: "Agent created successfully"
      })
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message ||
                          error?.message ||
                          "Failed to create agent"
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive"
      })
    }
  }

  const updateAgent = async () => {
    if (!editingAgent) return

    try {
      const updatedAgent = await agentApi.updateAgent(editingAgent.id, editAgent)
      setAgents(prev => prev.map(a => a.id === updatedAgent.id ? updatedAgent : a))
      setShowEditDialog(false)
      setEditingAgent(null)
      resetEditForm()
      toast({
        title: "Success",
        description: "Agent updated successfully"
      })
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message ||
                          error?.message ||
                          "Failed to update agent"
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive"
      })
    }
  }

  const deleteAgent = async () => {
    if (!deletingAgent) return

    try {
      await agentApi.deleteAgent(deletingAgent.id)
      setAgents(prev => prev.filter(a => a.id !== deletingAgent.id))
      setShowDeleteDialog(false)
      setDeletingAgent(null)
      toast({
        title: "Success",
        description: `${deletingAgent.display_name} has been deleted`
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete agent",
        variant: "destructive"
      })
    }
  }

  const handleDeleteAgent = (agent: AgentConfig) => {
    setDeletingAgent(agent)
    setShowDeleteDialog(true)
  }

  const resetForm = () => {
    setNewAgent({
      name: "",
      display_name: "",
      description: "",
      system_prompt: "",
      model: "gpt-oss-120b",
      temperature: 0.7,
      max_tokens: 2000,
      builtin_tools: [],
      mcp_servers: [],
      include_custom_tools: true,
      tool_choice: "auto",
      max_iterations: 5,
      category: "general",
      tags: [],
      is_public: false,
      tool_resources: undefined
    })
  }

  const resetEditForm = () => {
    setEditAgent({
      name: "",
      display_name: "",
      description: "",
      system_prompt: "",
      model: "gpt-oss-120b",
      temperature: 0.7,
      max_tokens: 2000,
      builtin_tools: [],
      mcp_servers: [],
      include_custom_tools: true,
      tool_choice: "auto",
      max_iterations: 5,
      category: "general",
      tags: [],
      is_public: false,
      tool_resources: undefined
    })
  }

  const getCategoryInfo = (category?: string) => {
    const info = AGENT_CATEGORIES.find(c => c.value === category) || AGENT_CATEGORIES[3]
    const Icon = AGENT_TYPE_ICONS[category || 'general'] || Wrench
    return { ...info, Icon }
  }

  const toggleBuiltinTool = (toolName: string, isCreate: boolean) => {
    const setter = isCreate ? setNewAgent : setEditAgent
    const current = isCreate ? newAgent.builtin_tools || [] : editAgent.builtin_tools || []

    setter(prev => ({
      ...prev,
      builtin_tools: current.includes(toolName)
        ? current.filter(t => t !== toolName)
        : [...current, toolName]
    }))
  }

  const toggleMCPServer = (serverName: string, isCreate: boolean) => {
    const setter = isCreate ? setNewAgent : setEditAgent
    const current = isCreate ? newAgent.mcp_servers || [] : editAgent.mcp_servers || []

    setter(prev => ({
      ...prev,
      mcp_servers: current.includes(serverName)
        ? current.filter(s => s !== serverName)
        : [...current, serverName]
    }))
  }

  const toggleRagCollection = (collectionId: string, isCreate: boolean) => {
    const setter = isCreate ? setNewAgent : setEditAgent
    const agent = isCreate ? newAgent : editAgent
    const currentIds = agent.tool_resources?.file_search?.vector_store_ids || []

    setter(prev => ({
      ...prev,
      tool_resources: {
        ...prev.tool_resources,
        file_search: {
          vector_store_ids: currentIds.includes(collectionId)
            ? currentIds.filter(id => id !== collectionId)
            : [...currentIds, collectionId]
        }
      }
    }))
  }

  const getSelectedRagCollections = (isCreate: boolean): string[] => {
    const agent = isCreate ? newAgent : editAgent
    return agent.tool_resources?.file_search?.vector_store_ids || []
  }

  const getRagMaxResults = (isCreate: boolean): number => {
    const agent = isCreate ? newAgent : editAgent
    return agent.tool_resources?.file_search?.max_results || 5
  }

  const setRagMaxResults = (value: number, isCreate: boolean) => {
    const setter = isCreate ? setNewAgent : setEditAgent
    setter(prev => ({
      ...prev,
      tool_resources: {
        ...prev.tool_resources,
        file_search: {
          ...prev.tool_resources?.file_search,
          vector_store_ids: prev.tool_resources?.file_search?.vector_store_ids || [],
          max_results: value
        }
      }
    }))
  }

  // Check if knowledge base is enabled (has collections selected)
  const isKnowledgeBaseEnabled = (isCreate: boolean): boolean => {
    return getSelectedRagCollections(isCreate).length > 0
  }

  // Sync rag_search tool with knowledge base selection
  const syncRagSearchTool = (hasCollections: boolean, isCreate: boolean) => {
    const setter = isCreate ? setNewAgent : setEditAgent
    const current = isCreate ? newAgent.builtin_tools || [] : editAgent.builtin_tools || []

    if (hasCollections && !current.includes('rag_search')) {
      setter(prev => ({
        ...prev,
        builtin_tools: [...(prev.builtin_tools || []), 'rag_search']
      }))
    } else if (!hasCollections && current.includes('rag_search')) {
      setter(prev => ({
        ...prev,
        builtin_tools: (prev.builtin_tools || []).filter(t => t !== 'rag_search')
      }))
    }
  }

  // Enhanced toggle that also syncs rag_search tool
  const toggleRagCollectionWithSync = (collectionId: string, isCreate: boolean) => {
    const currentIds = getSelectedRagCollections(isCreate)
    const willHaveCollections = currentIds.includes(collectionId)
      ? currentIds.length > 1  // Removing one, check if others remain
      : true  // Adding one, will have at least one

    toggleRagCollection(collectionId, isCreate)

    // Use setTimeout to ensure state is updated before syncing
    setTimeout(() => syncRagSearchTool(willHaveCollections, isCreate), 0)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agent Manager</h1>
          <p className="text-muted-foreground">
            Configure AI agents and MCP servers for tool-enabled conversations.
          </p>
        </div>
      </div>

      <Tabs value={mainTab} onValueChange={setMainTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="agents" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Agents
          </TabsTrigger>
          <TabsTrigger value="mcp-servers" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            MCP Servers
          </TabsTrigger>
        </TabsList>

        <TabsContent value="agents" className="mt-6 space-y-6">
          <div className="flex justify-end">
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Agent
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create New Agent</DialogTitle>
              <DialogDescription>
                Configure your AI agent with specific tools and behaviors.
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="basic" className="mt-6">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="basic">Basic</TabsTrigger>
                <TabsTrigger value="personality">Personality</TabsTrigger>
                <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
                <TabsTrigger value="tools">Tools</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4 mt-6">
                <div>
                  <Label htmlFor="name">Agent Name (ID) <span className="text-destructive">*</span></Label>
                  <Input
                    id="name"
                    value={newAgent.name}
                    onChange={(e) => setNewAgent(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., customer-support-agent"
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">Unique identifier for the agent (required)</p>
                </div>

                <div>
                  <Label htmlFor="display_name">Display Name <span className="text-destructive">*</span></Label>
                  <Input
                    id="display_name"
                    value={newAgent.display_name}
                    onChange={(e) => setNewAgent(prev => ({ ...prev, display_name: e.target.value }))}
                    placeholder="e.g., Customer Support Agent"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={newAgent.description}
                    onChange={(e) => setNewAgent(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="What does this agent do?"
                    className="min-h-[80px]"
                  />
                </div>

                <div>
                  <Label htmlFor="category">Category</Label>
                  <Select
                    value={newAgent.category}
                    onValueChange={(value) => setNewAgent(prev => ({ ...prev, category: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {AGENT_CATEGORIES.map((cat) => (
                        <SelectItem key={cat.value} value={cat.value}>
                          {cat.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <ModelSelector
                    value={newAgent.model || ""}
                    onValueChange={(value) => setNewAgent(prev => ({ ...prev, model: value }))}
                    filter="chat"
                  />
                </div>
              </TabsContent>

              <TabsContent value="personality" className="space-y-4 mt-6">
                <div>
                  <Label htmlFor="prompt">System Prompt <span className="text-destructive">*</span></Label>
                  <Textarea
                    id="prompt"
                    value={newAgent.system_prompt}
                    onChange={(e) => setNewAgent(prev => ({ ...prev, system_prompt: e.target.value }))}
                    placeholder="You are a helpful AI agent. Your role is to..."
                    className="min-h-[200px] font-mono text-sm"
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Define the agent's personality, expertise, and behavior (required)
                  </p>
                </div>

                <div>
                  <Label>Temperature: {newAgent.temperature}</Label>
                  <Slider
                    value={[newAgent.temperature || 0.7]}
                    onValueChange={([value]) => setNewAgent(prev => ({ ...prev, temperature: value }))}
                    min={0}
                    max={2}
                    step={0.1}
                    className="mt-2"
                  />
                  <div className="flex justify-between text-sm text-muted-foreground mt-1">
                    <span>Focused</span>
                    <span>Creative</span>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="knowledge" className="space-y-4 mt-6">
                <div>
                  <Label className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Knowledge Base Collections
                  </Label>
                  <p className="text-sm text-muted-foreground mb-2">
                    Select which knowledge base collections this agent can search.
                    Selecting any collection will enable RAG search for this agent.
                  </p>
                  {ragCollections.length > 0 ? (
                    <div className="space-y-2 mt-2 max-h-64 overflow-y-auto border rounded-md p-3">
                      {ragCollections.map((collection) => (
                        <div key={collection.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`rag-${collection.id}`}
                            checked={getSelectedRagCollections(true).includes(String(collection.id))}
                            onCheckedChange={() => toggleRagCollectionWithSync(String(collection.id), true)}
                          />
                          <Label htmlFor={`rag-${collection.id}`} className="flex-1 cursor-pointer">
                            <span className="font-medium">{collection.name}</span>
                            <p className="text-sm text-muted-foreground">
                              {collection.document_count} documents
                            </p>
                          </Label>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 border rounded-md">
                      <Database className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">
                        No knowledge base collections available.
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Create collections in the RAG module first.
                      </p>
                    </div>
                  )}
                </div>

                {isKnowledgeBaseEnabled(true) && (
                  <div>
                    <Label>Search Results: {getRagMaxResults(true)}</Label>
                    <Slider
                      value={[getRagMaxResults(true)]}
                      onValueChange={([value]) => setRagMaxResults(value, true)}
                      min={1}
                      max={20}
                      step={1}
                      className="mt-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Maximum number of knowledge base results to include in agent context
                    </p>
                  </div>
                )}

                {isKnowledgeBaseEnabled(true) && (
                  <div className="flex items-center gap-2 p-3 rounded-md bg-muted/50">
                    <Search className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      RAG Search will be enabled with {getSelectedRagCollections(true).length} collection(s)
                    </span>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="tools" className="space-y-4 mt-6">
                <div>
                  <Label>Built-in Tools</Label>
                  <div className="space-y-2 mt-2">
                    {BUILTIN_TOOLS.map((tool) => (
                      <div key={tool.value} className="flex items-center space-x-2">
                        <Checkbox
                          id={`tool-${tool.value}`}
                          checked={newAgent.builtin_tools?.includes(tool.value)}
                          onCheckedChange={() => toggleBuiltinTool(tool.value, true)}
                        />
                        <Label htmlFor={`tool-${tool.value}`} className="flex-1 cursor-pointer">
                          <span className="font-medium">{tool.label}</span>
                          <p className="text-sm text-muted-foreground">{tool.description}</p>
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="flex items-center gap-2">
                    <Server className="h-4 w-4" />
                    MCP Servers
                  </Label>
                  <p className="text-sm text-muted-foreground mb-2">
                    Select external MCP servers this agent can access
                  </p>
                  {availableMCPServers.length > 0 ? (
                    <div className="space-y-2 mt-2">
                      {availableMCPServers.map((server) => (
                        <div key={server.name} className="flex items-center space-x-2">
                          <Checkbox
                            id={`mcp-${server.name}`}
                            checked={newAgent.mcp_servers?.includes(server.name)}
                            onCheckedChange={() => toggleMCPServer(server.name, true)}
                          />
                          <Label htmlFor={`mcp-${server.name}`} className="flex-1 cursor-pointer">
                            <span className="font-medium">{server.display_name}</span>
                            {server.is_global && (
                              <Badge variant="secondary" className="ml-2 text-xs">Global</Badge>
                            )}
                            <p className="text-sm text-muted-foreground">
                              {server.description || `${server.tool_count} tools available`}
                            </p>
                          </Label>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">
                      No MCP servers available. Add servers in the MCP Servers tab.
                    </p>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="include_custom"
                    checked={newAgent.include_custom_tools}
                    onCheckedChange={(checked) => setNewAgent(prev => ({ ...prev, include_custom_tools: checked as boolean }))}
                  />
                  <Label htmlFor="include_custom">Include custom tools</Label>
                </div>
              </TabsContent>

              <TabsContent value="advanced" className="space-y-4 mt-6">
                <div>
                  <Label>Max Response Length: {newAgent.max_tokens}</Label>
                  <Slider
                    value={[newAgent.max_tokens || 2000]}
                    onValueChange={([value]) => setNewAgent(prev => ({ ...prev, max_tokens: value }))}
                    min={50}
                    max={8000}
                    step={50}
                    className="mt-2"
                  />
                </div>

                <div>
                  <Label>Max Tool Iterations: {newAgent.max_iterations}</Label>
                  <Slider
                    value={[newAgent.max_iterations || 5]}
                    onValueChange={([value]) => setNewAgent(prev => ({ ...prev, max_iterations: value }))}
                    min={1}
                    max={10}
                    step={1}
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Maximum number of tool calls the agent can make per message
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="is_public"
                    checked={newAgent.is_public}
                    onCheckedChange={(checked) => setNewAgent(prev => ({ ...prev, is_public: checked as boolean }))}
                  />
                  <Label htmlFor="is_public">Make this agent public</Label>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={createAgent} disabled={!newAgent.name || !newAgent.display_name || !newAgent.system_prompt}>
                Create Agent
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Agents List */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => {
          const categoryInfo = getCategoryInfo(agent.category)
          const Icon = categoryInfo.Icon

          return (
            <Card key={agent.id} className="group hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-3 rounded-lg bg-primary">
                      <Icon className="h-5 w-5 text-primary-foreground" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{agent.display_name}</CardTitle>
                      <CardDescription>{categoryInfo.label}</CardDescription>
                    </div>
                  </div>
                  <Badge variant={agent.is_active ? "default" : "secondary"}>
                    {agent.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {agent.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {agent.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Model</span>
                    <Badge variant="outline" className="text-xs">{agent.model}</Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Built-in Tools</span>
                    <Badge variant="default">
                      {agent.tools_config.builtin_tools.length} enabled
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">MCP Servers</span>
                    <Badge variant={agent.tools_config.mcp_servers.length > 0 ? "default" : "secondary"}>
                      {agent.tools_config.mcp_servers.length} connected
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Usage</span>
                    <span>{agent.usage_count} chats</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 mt-4 pt-4 border-t">
                  <Button size="sm" className="flex-1" onClick={() => handleTestChat(agent)}>
                    <Play className="h-4 w-4 mr-2" />
                    Test Chat
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleEditAgent(agent)}>
                    <Settings className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteAgent(agent)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}

        {agents.length === 0 && !loading && (
          <Card className="col-span-full">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Bot className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No agents yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first AI agent with custom tools and capabilities.
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Agent
              </Button>
            </CardContent>
          </Card>
        )}
        </div>
        </TabsContent>

        <TabsContent value="mcp-servers" className="mt-6">
          <MCPServerManager />
        </TabsContent>
      </Tabs>

      {/* Chat Interface Modal */}
      {showChatInterface && testingAgent && (
        <Dialog open={showChatInterface} onOpenChange={setShowChatInterface}>
          <DialogContent className="max-w-6xl w-[90vw] h-[85vh] p-0 flex flex-col">
            <DialogHeader className="sr-only">
              <DialogTitle>Chat with {testingAgent.display_name}</DialogTitle>
              <DialogDescription>
                Test your agent by having a conversation
              </DialogDescription>
            </DialogHeader>
            <AgentChatInterface
              agentConfigId={testingAgent.id}
              agentName={testingAgent.display_name}
              onClose={() => setShowChatInterface(false)}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Edit Agent Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Agent: {editingAgent?.display_name}</DialogTitle>
            <DialogDescription>
              Update your agent's configuration and settings.
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="basic" className="mt-6">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="basic">Basic</TabsTrigger>
              <TabsTrigger value="personality">Personality</TabsTrigger>
              <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
              <TabsTrigger value="tools">Tools</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
            </TabsList>

            <TabsContent value="basic" className="space-y-4 mt-6">
              <div>
                <Label htmlFor="edit-name">Agent Name (ID) <span className="text-destructive">*</span></Label>
                <Input
                  id="edit-name"
                  value={editAgent.name}
                  onChange={(e) => setEditAgent(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., customer-support-agent"
                  required
                />
                <p className="text-xs text-muted-foreground mt-1">Unique identifier for the agent (required)</p>
              </div>

              <div>
                <Label htmlFor="edit-display_name">Display Name <span className="text-destructive">*</span></Label>
                <Input
                  id="edit-display_name"
                  value={editAgent.display_name}
                  onChange={(e) => setEditAgent(prev => ({ ...prev, display_name: e.target.value }))}
                  placeholder="e.g., Customer Support Agent"
                  required
                />
              </div>

              <div>
                <Label htmlFor="edit-description">Description</Label>
                <Textarea
                  id="edit-description"
                  value={editAgent.description}
                  onChange={(e) => setEditAgent(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="What does this agent do?"
                  className="min-h-[80px]"
                />
              </div>

              <div>
                <Label htmlFor="edit-category">Category</Label>
                <Select
                  value={editAgent.category}
                  onValueChange={(value) => setEditAgent(prev => ({ ...prev, category: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {AGENT_CATEGORIES.map((cat) => (
                      <SelectItem key={cat.value} value={cat.value}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <ModelSelector
                  value={editAgent.model || ""}
                  onValueChange={(value) => setEditAgent(prev => ({ ...prev, model: value }))}
                  filter="chat"
                />
              </div>
            </TabsContent>

            <TabsContent value="personality" className="space-y-4 mt-6">
              <div>
                <Label htmlFor="edit-prompt">System Prompt <span className="text-destructive">*</span></Label>
                <Textarea
                  id="edit-prompt"
                  value={editAgent.system_prompt}
                  onChange={(e) => setEditAgent(prev => ({ ...prev, system_prompt: e.target.value }))}
                  placeholder="You are a helpful AI agent. Your role is to..."
                  className="min-h-[200px] font-mono text-sm"
                  required
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Define the agent's personality, expertise, and behavior (required)
                </p>
              </div>

              <div>
                <Label>Temperature: {editAgent.temperature}</Label>
                <Slider
                  value={[editAgent.temperature || 0.7]}
                  onValueChange={([value]) => setEditAgent(prev => ({ ...prev, temperature: value }))}
                  min={0}
                  max={2}
                  step={0.1}
                  className="mt-2"
                />
                <div className="flex justify-between text-sm text-muted-foreground mt-1">
                  <span>Focused</span>
                  <span>Creative</span>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="knowledge" className="space-y-4 mt-6">
              <div>
                <Label className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Knowledge Base Collections
                </Label>
                <p className="text-sm text-muted-foreground mb-2">
                  Select which knowledge base collections this agent can search.
                  Selecting any collection will enable RAG search for this agent.
                </p>
                {ragCollections.length > 0 ? (
                  <div className="space-y-2 mt-2 max-h-64 overflow-y-auto border rounded-md p-3">
                    {ragCollections.map((collection) => (
                      <div key={collection.id} className="flex items-center space-x-2">
                        <Checkbox
                          id={`edit-rag-${collection.id}`}
                          checked={getSelectedRagCollections(false).includes(String(collection.id))}
                          onCheckedChange={() => toggleRagCollectionWithSync(String(collection.id), false)}
                        />
                        <Label htmlFor={`edit-rag-${collection.id}`} className="flex-1 cursor-pointer">
                          <span className="font-medium">{collection.name}</span>
                          <p className="text-sm text-muted-foreground">
                            {collection.document_count} documents
                          </p>
                        </Label>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 border rounded-md">
                    <Database className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No knowledge base collections available.
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Create collections in the RAG module first.
                    </p>
                  </div>
                )}
              </div>

              {isKnowledgeBaseEnabled(false) && (
                <div>
                  <Label>Search Results: {getRagMaxResults(false)}</Label>
                  <Slider
                    value={[getRagMaxResults(false)]}
                    onValueChange={([value]) => setRagMaxResults(value, false)}
                    min={1}
                    max={20}
                    step={1}
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Maximum number of knowledge base results to include in agent context
                  </p>
                </div>
              )}

              {isKnowledgeBaseEnabled(false) && (
                <div className="flex items-center gap-2 p-3 rounded-md bg-muted/50">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    RAG Search will be enabled with {getSelectedRagCollections(false).length} collection(s)
                  </span>
                </div>
              )}
            </TabsContent>

            <TabsContent value="tools" className="space-y-4 mt-6">
              <div>
                <Label>Built-in Tools</Label>
                <div className="space-y-2 mt-2">
                  {BUILTIN_TOOLS.map((tool) => (
                    <div key={tool.value} className="flex items-center space-x-2">
                      <Checkbox
                        id={`edit-tool-${tool.value}`}
                        checked={editAgent.builtin_tools?.includes(tool.value)}
                        onCheckedChange={() => toggleBuiltinTool(tool.value, false)}
                      />
                      <Label htmlFor={`edit-tool-${tool.value}`} className="flex-1 cursor-pointer">
                        <span className="font-medium">{tool.label}</span>
                        <p className="text-sm text-muted-foreground">{tool.description}</p>
                      </Label>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <Label className="flex items-center gap-2">
                  <Server className="h-4 w-4" />
                  MCP Servers
                </Label>
                <p className="text-sm text-muted-foreground mb-2">
                  Select external MCP servers this agent can access
                </p>
                {availableMCPServers.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {availableMCPServers.map((server) => (
                      <div key={server.name} className="flex items-center space-x-2">
                        <Checkbox
                          id={`edit-mcp-${server.name}`}
                          checked={editAgent.mcp_servers?.includes(server.name)}
                          onCheckedChange={() => toggleMCPServer(server.name, false)}
                        />
                        <Label htmlFor={`edit-mcp-${server.name}`} className="flex-1 cursor-pointer">
                          <span className="font-medium">{server.display_name}</span>
                          {server.is_global && (
                            <Badge variant="secondary" className="ml-2 text-xs">Global</Badge>
                          )}
                          <p className="text-sm text-muted-foreground">
                            {server.description || `${server.tool_count} tools available`}
                          </p>
                        </Label>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground italic">
                    No MCP servers available. Add servers in the MCP Servers tab.
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="edit-include_custom"
                  checked={editAgent.include_custom_tools}
                  onCheckedChange={(checked) => setEditAgent(prev => ({ ...prev, include_custom_tools: checked as boolean }))}
                />
                <Label htmlFor="edit-include_custom">Include custom tools</Label>
              </div>
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4 mt-6">
              <div>
                <Label>Max Response Length: {editAgent.max_tokens}</Label>
                <Slider
                  value={[editAgent.max_tokens || 2000]}
                  onValueChange={([value]) => setEditAgent(prev => ({ ...prev, max_tokens: value }))}
                  min={50}
                  max={8000}
                  step={50}
                  className="mt-2"
                />
              </div>

              <div>
                <Label>Max Tool Iterations: {editAgent.max_iterations}</Label>
                <Slider
                  value={[editAgent.max_iterations || 5]}
                  onValueChange={([value]) => setEditAgent(prev => ({ ...prev, max_iterations: value }))}
                  min={1}
                  max={10}
                  step={1}
                  className="mt-2"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Maximum number of tool calls the agent can make per message
                </p>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="edit-is_public"
                  checked={editAgent.is_public}
                  onCheckedChange={(checked) => setEditAgent(prev => ({ ...prev, is_public: checked as boolean }))}
                />
                <Label htmlFor="edit-is_public">Make this agent public</Label>
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
            <Button variant="outline" onClick={() => {
              setShowEditDialog(false)
              setEditingAgent(null)
              resetEditForm()
            }}>
              Cancel
            </Button>
            <Button onClick={updateAgent} disabled={!editAgent.name || !editAgent.display_name || !editAgent.system_prompt}>
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Agent</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingAgent?.display_name}"? This will permanently
              remove the agent configuration. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setShowDeleteDialog(false)
              setDeletingAgent(null)
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={deleteAgent}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Agent
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
