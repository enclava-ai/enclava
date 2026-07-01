"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import {
  Zap,
  Edit3,
  RotateCcw,
  Loader2,
  Save,
  AlertTriangle,
  Plus,
  Sparkles,
  BarChart3
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { useAuth } from '@/components/providers/auth-provider'
import { useToast } from '@/hooks/use-toast'
import { useSearchParams } from 'next/navigation'
import ChatPlayground from '@/components/playground/ChatPlayground'
import EmbeddingPlayground from '@/components/playground/EmbeddingPlayground'
import ModelSelector from '@/components/playground/ModelSelector'
import UsageTab from '@/components/llm/UsageTab'
import ProvidersTab from '@/components/llm/ProvidersTab'

interface PromptTemplate {
  id: string
  name: string
  type_key: string
  description?: string
  system_prompt: string
  is_default: boolean
  is_active: boolean
  version: number
  created_at: string
  updated_at: string
}

interface PromptVariable {
  id: string
  variable_name: string
  description?: string
  example_value?: string
  is_active: boolean
}

export default function LLMPage() {
  return (
    <ProtectedRoute>
      <LLMPageContent />
    </ProtectedRoute>
  )
}

function LLMPageContent() {
  const searchParams = useSearchParams()
  const tabParam = searchParams.get('tab')
  const [activeTab, setActiveTab] = useState(() => {
    if (tabParam === 'prompt-templates') return 'prompt-templates'
    if (tabParam === 'playground') return 'playground'
    if (tabParam === 'providers') return 'providers'
    return 'usage' // Default to usage tab
  })
  const [selectedModel, setSelectedModel] = useState('')
  const [playgroundTab, setPlaygroundTab] = useState('chat')
  const { isAuthenticated } = useAuth()

  // Prompt Templates state
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [variables, setVariables] = useState<PromptVariable[]>([])
  const [loading, setLoading] = useState(true)
  const [editingTemplate, setEditingTemplate] = useState<PromptTemplate | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [saving, setSaving] = useState(false)
  const [improvingWithAI, setImprovingWithAI] = useState(false)
  const { toast } = useToast()
  const notifySuccess = (description: string) => toast({ title: 'Success', description })
  const notifyError = (description: string) => toast({ title: 'Error', description, variant: 'destructive' })

  // Form state for editing
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    system_prompt: '',
    is_active: true
  })

  // Form state for creating new templates
  const [createForm, setCreateForm] = useState({
    name: '',
    type_key: '',
    description: '',
    system_prompt: '',
    is_active: true
  })

  const [customTypeKey, setCustomTypeKey] = useState('')
  const [useCustomType, setUseCustomType] = useState(false)

  // Available agent types
  const AGENT_TYPES = [
    { value: "assistant", label: "General Assistant" },
    { value: "customer_support", label: "Customer Support" },
    { value: "teacher", label: "Educational Tutor" },
    { value: "researcher", label: "Research Assistant" },
    { value: "creative_writer", label: "Creative Writer" },
    { value: "custom", label: "Custom Agent" },
  ]

  useEffect(() => {
    if (isAuthenticated) {
      loadTemplates()
    } else {
      setLoading(false)
    }
  }, [isAuthenticated])

  const loadTemplates = async () => {
    try {
      setLoading(true)

      const [templatesResult, variablesResult] = await Promise.allSettled([
        apiClient.get('/api-internal/v1/prompt-templates/templates'),
        apiClient.get('/api-internal/v1/prompt-templates/variables')
      ])

      if (templatesResult.status === 'fulfilled') {
        const loadedTemplates = templatesResult.value
        setTemplates(loadedTemplates)

        if (loadedTemplates.length === 0) {
          try {
            await apiClient.post('/api-internal/v1/prompt-templates/seed-defaults', {})
            const newTemplates = await apiClient.get('/api-internal/v1/prompt-templates/templates')
            setTemplates(newTemplates)
          } catch (error) {
            console.error('Failed to seed default templates:', error)
          }
        }
      }

      if (variablesResult.status === 'fulfilled') {
        setVariables(variablesResult.value)
      }
    } catch (error) {
      console.error('Error loading prompt templates:', error)
      notifyError('Failed to load prompt templates')
    } finally {
      setLoading(false)
    }
  }

  const handleEditTemplate = (template: PromptTemplate) => {
    setEditingTemplate(template)
    setEditForm({
      name: template.name,
      description: template.description ?? '',
      system_prompt: template.system_prompt,
      is_active: template.is_active
    })
    setShowEditDialog(true)
  }

  const handleSaveTemplate = async () => {
    if (!editingTemplate) return

    try {
      setSaving(true)

      const updatedTemplate = await apiClient.put(`/api-internal/v1/prompt-templates/templates/${editingTemplate.type_key}`, {
        name: editForm.name,
        type_key: editingTemplate.type_key,
        description: editForm.description,
        system_prompt: editForm.system_prompt,
        is_active: editForm.is_active
      })

      setTemplates(templates.map(t =>
        t.type_key === editingTemplate.type_key ? updatedTemplate : t
      ))

      notifySuccess('Prompt template updated successfully')
      setShowEditDialog(false)
      setEditingTemplate(null)

    } catch (error) {
      notifyError(error instanceof Error ? error.message : 'Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  const handleResetTemplate = async (template: PromptTemplate) => {
    try {
      await apiClient.post(`/api-internal/v1/prompt-templates/templates/${template.type_key}/reset`, {})
      notifySuccess('Prompt template reset to default')
      await loadTemplates()
    } catch (error) {
      notifyError(error instanceof Error ? error.message : 'Failed to reset template')
    }
  }

  const handleCreateTemplate = async () => {
    const typeKey = useCustomType ? customTypeKey : createForm.type_key
    if (!createForm.name.trim() || !typeKey.trim() || !createForm.system_prompt.trim()) {
      notifyError('Please fill in all required fields')
      return
    }

    const finalForm = { ...createForm, type_key: typeKey }

    try {
      setSaving(true)

      const newTemplate = await apiClient.post('/api-internal/v1/prompt-templates/templates/create', {
        name: finalForm.name,
        type_key: finalForm.type_key,
        description: finalForm.description,
        system_prompt: finalForm.system_prompt,
        is_active: finalForm.is_active
      })

      setTemplates([...templates, newTemplate])
      notifySuccess('Prompt template created successfully')
      setShowCreateDialog(false)

      setCreateForm({
        name: '',
        type_key: '',
        description: '',
        system_prompt: '',
        is_active: true
      })
      setCustomTypeKey('')
      setUseCustomType(false)

    } catch (error) {
      notifyError(error instanceof Error ? error.message : 'Failed to create template')
    } finally {
      setSaving(false)
    }
  }

  const handleImproveWithAI = async (currentPrompt: string, agentType: string, isEditing: boolean = false) => {
    try {
      setImprovingWithAI(true)

      const result = await apiClient.post('/api-internal/v1/prompt-templates/improve', {
        current_prompt: currentPrompt,
        agent_type: agentType,
        improvement_instructions: null
      })

      if (isEditing) {
        setEditForm(prev => ({ ...prev, system_prompt: result.improved_prompt }))
      } else {
        setCreateForm(prev => ({ ...prev, system_prompt: result.improved_prompt }))
      }

      notifySuccess('Prompt improved with AI successfully')

    } catch (error) {
      notifyError(error instanceof Error ? error.message : 'Failed to improve prompt')
    } finally {
      setImprovingWithAI(false)
    }
  }

  const getTypeKeyDisplayName = (typeKey: string) => {
    const displayNames: Record<string, string> = {
      'assistant': 'General Assistant',
      'customer_support': 'Customer Support',
      'teacher': 'Educational Tutor',
      'researcher': 'Research Assistant',
      'creative_writer': 'Creative Writer',
      'custom': 'Custom Agent'
    }
    return displayNames[typeKey] || typeKey
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">LLM</h1>
        <p className="text-muted-foreground">
          Monitor usage statistics, test models in the playground, and manage prompt templates.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="usage" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Usage
          </TabsTrigger>
          <TabsTrigger value="playground">Playground</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="prompt-templates">Prompt Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="usage" className="mt-6">
          <UsageTab />
        </TabsContent>

        <TabsContent value="playground" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                AI Model Testing
              </CardTitle>
              <CardDescription>
                Select a model and test different AI capabilities.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <label className="text-sm font-medium mb-2 block">Select Model</label>
                <ModelSelector
                  value={selectedModel}
                  onValueChange={setSelectedModel}
                  className="w-full max-w-md"
                />
              </div>

              <Tabs value={playgroundTab} onValueChange={setPlaygroundTab}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="chat">Chat Completions</TabsTrigger>
                  <TabsTrigger value="embeddings">Embeddings</TabsTrigger>
                </TabsList>

                <TabsContent value="chat" className="mt-6">
                  <ChatPlayground selectedModel={selectedModel} />
                </TabsContent>

                <TabsContent value="embeddings" className="mt-6">
                  <EmbeddingPlayground />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="providers" className="mt-6">
          <ProvidersTab />
        </TabsContent>

        <TabsContent value="prompt-templates" className="mt-6">
          <div className="mb-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <p className="text-muted-foreground">
                  Customize the system prompts for different agent types. These prompts define how your agents behave and respond to users.
                </p>
              </div>
              <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="h-4 w-4 mr-2" />
                    Create New Template
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle>Create New Prompt Template</DialogTitle>
                    <DialogDescription>
                      Create a new system prompt template for a specific agent type.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="create-name">Name *</Label>
                      <Input
                        id="create-name"
                        value={createForm.name}
                        onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                        placeholder="Template name"
                      />
                    </div>

                    <div>
                      <Label>Agent Type *</Label>
                      <div className="space-y-3">
                        <div className="flex items-center space-x-2">
                          <input
                            type="radio"
                            id="use-existing-type"
                            name="type-selection"
                            checked={!useCustomType}
                            onChange={() => setUseCustomType(false)}
                            className="h-4 w-4"
                          />
                          <Label htmlFor="use-existing-type" className="text-sm">Use existing type</Label>
                        </div>

                        {!useCustomType && (
                          <select
                            value={createForm.type_key}
                            onChange={(e) => setCreateForm({ ...createForm, type_key: e.target.value })}
                            className="w-full px-3 py-2 border border-input bg-background rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={useCustomType}
                          >
                            <option value="">Select an agent type</option>
                            {AGENT_TYPES.map((type) => (
                              <option key={type.value} value={type.value}>
                                {type.label}
                              </option>
                            ))}
                          </select>
                        )}

                        <div className="flex items-center space-x-2">
                          <input
                            type="radio"
                            id="use-custom-type"
                            name="type-selection"
                            checked={useCustomType}
                            onChange={() => setUseCustomType(true)}
                            className="h-4 w-4"
                          />
                          <Label htmlFor="use-custom-type" className="text-sm">Create new type</Label>
                        </div>

                        {useCustomType && (
                          <Input
                            value={customTypeKey}
                            onChange={(e) => {
                              setCustomTypeKey(e.target.value)
                              setCreateForm({ ...createForm, type_key: e.target.value })
                            }}
                            placeholder="Enter custom type key (e.g., sales_agent, code_reviewer)"
                            className="w-full"
                          />
                        )}
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="create-description">Description</Label>
                      <Input
                        id="create-description"
                        value={createForm.description}
                        onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                        placeholder="Brief description of this template"
                      />
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label htmlFor="create-system-prompt">System Prompt *</Label>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handleImproveWithAI(createForm.system_prompt, useCustomType ? customTypeKey : createForm.type_key, false)}
                          disabled={!createForm.system_prompt.trim() || (!useCustomType && !createForm.type_key) || (useCustomType && !customTypeKey.trim()) || improvingWithAI}
                          className="flex items-center gap-2"
                        >
                          {improvingWithAI ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Sparkles className="h-3 w-3" />
                          )}
                          {improvingWithAI ? 'Improving...' : 'Improve with AI'}
                        </Button>
                      </div>
                      <Textarea
                        id="create-system-prompt"
                        value={createForm.system_prompt}
                        onChange={(e) => setCreateForm({ ...createForm, system_prompt: e.target.value })}
                        placeholder="Enter the system prompt that defines the agent's behavior..."
                        rows={12}
                        className="font-mono text-sm"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        Character count: {createForm.system_prompt.length}
                      </p>
                    </div>

                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="create-is-active"
                        checked={createForm.is_active}
                        onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.checked })}
                        className="h-4 w-4"
                      />
                      <Label htmlFor="create-is-active" className="text-sm">
                        Template is active
                      </Label>
                    </div>
                  </div>

                  <DialogFooter className="flex justify-between">
                    <div>
                      {variables.length > 0 && (
                        <p className="text-xs text-muted-foreground">
                          Use variables like {variables.slice(0, 2).map(v => v.variable_name).join(', ')} in your prompt
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => setShowCreateDialog(false)}
                        disabled={saving}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleCreateTemplate}
                        disabled={saving || !createForm.name.trim() || (!useCustomType && !createForm.type_key) || (useCustomType && !customTypeKey.trim()) || !createForm.system_prompt.trim()}
                      >
                        {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        <Save className="h-4 w-4 mr-2" />
                        Create Template
                      </Button>
                    </div>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            {variables.length > 0 && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="text-lg">Available Variables</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-3">
                    You can use these variables in your prompts. They will be automatically replaced with actual values.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {variables.map((variable) => (
                      <Badge key={variable.id} variant="secondary" className="text-xs">
                        {variable.variable_name}
                        {variable.description && (
                          <span className="ml-1 opacity-70">- {variable.description}</span>
                        )}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              Loading...
            </div>
          ) : (
            <div className="grid gap-6">
              {templates.map((template) => (
                <Card key={template.id} className="w-full">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                    <div>
                      <CardTitle className="text-xl">{template.name}</CardTitle>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {getTypeKeyDisplayName(template.type_key)}
                        </Badge>
                        {template.is_default && (
                          <Badge variant="secondary" className="text-xs">Default</Badge>
                        )}
                        <Badge variant={template.is_active ? "default" : "destructive"} className="text-xs">
                          {template.is_active ? "Active" : "Inactive"}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          v{template.version}
                        </span>
                      </div>
                      {template.description && (
                        <p className="text-sm text-muted-foreground mt-1">{template.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Dialog open={showEditDialog && editingTemplate?.id === template.id} onOpenChange={setShowEditDialog}>
                        <DialogTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditTemplate(template)}
                          >
                            <Edit3 className="h-4 w-4 mr-1" />
                            Edit
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                          <DialogHeader>
                            <DialogTitle>Edit Prompt Template</DialogTitle>
                            <DialogDescription>
                              Customize the system prompt for {template.name}. This defines how the agent will behave and respond.
                            </DialogDescription>
                          </DialogHeader>

                          <div className="space-y-4">
                            <div>
                              <Label htmlFor="template-name">Name</Label>
                              <Input
                                id="template-name"
                                value={editForm.name}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                placeholder="Template name"
                              />
                            </div>

                            <div>
                              <Label htmlFor="template-description">Description</Label>
                              <Input
                                id="template-description"
                                value={editForm.description}
                                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                                placeholder="Brief description of this template"
                              />
                            </div>

                            <div>
                              <div className="flex items-center justify-between mb-2">
                                <Label htmlFor="system-prompt">System Prompt</Label>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleImproveWithAI(editForm.system_prompt, editingTemplate?.type_key || '', true)}
                                  disabled={!editForm.system_prompt.trim() || !editingTemplate?.type_key || improvingWithAI}
                                  className="flex items-center gap-2"
                                >
                                  {improvingWithAI ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <Sparkles className="h-3 w-3" />
                                  )}
                                  {improvingWithAI ? 'Improving...' : 'Improve with AI'}
                                </Button>
                              </div>
                              <Textarea
                                id="system-prompt"
                                value={editForm.system_prompt}
                                onChange={(e) => setEditForm({ ...editForm, system_prompt: e.target.value })}
                                placeholder="Enter the system prompt that defines the agent's behavior..."
                                rows={12}
                                className="font-mono text-sm"
                              />
                              <p className="text-xs text-muted-foreground mt-1">
                                Character count: {editForm.system_prompt.length}
                              </p>
                            </div>

                            <div className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                id="is-active"
                                checked={editForm.is_active}
                                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                                className="h-4 w-4"
                              />
                              <Label htmlFor="is-active" className="text-sm">
                                Template is active
                              </Label>
                            </div>
                          </div>

                          <DialogFooter className="flex justify-between">
                            <div>
                              {variables.length > 0 && (
                                <p className="text-xs text-muted-foreground">
                                  Use variables like {variables.slice(0, 2).map(v => v.variable_name).join(', ')} in your prompt
                                </p>
                              )}
                            </div>
                            <div className="flex gap-2">
                              <Button
                                variant="outline"
                                onClick={() => setShowEditDialog(false)}
                                disabled={saving}
                              >
                                Cancel
                              </Button>
                              <Button
                                onClick={handleSaveTemplate}
                                disabled={saving || !editForm.name.trim() || !editForm.system_prompt.trim()}
                              >
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                <Save className="h-4 w-4 mr-2" />
                                Save Changes
                              </Button>
                            </div>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <RotateCcw className="h-4 w-4 mr-1" />
                            Reset
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle className="flex items-center gap-2">
                              <AlertTriangle className="h-5 w-5 text-warning" />
                              Reset Prompt Template
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              This will reset "{template.name}" to its default system prompt.
                              Any customizations you've made will be lost. This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleResetTemplate(template)}
                              className="bg-warning hover:bg-warning/90"
                            >
                              Reset to Default
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </CardHeader>

                  <CardContent>
                    <div className="bg-muted/50 p-4 rounded-lg">
                      <h4 className="text-sm font-medium mb-2">Current System Prompt:</h4>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono max-h-32 overflow-y-auto">
                        {template.system_prompt}
                      </pre>
                    </div>

                    <div className="mt-3 text-xs text-muted-foreground">
                      Last updated: {new Date(template.updated_at).toLocaleString()}
                    </div>
                  </CardContent>
                </Card>
              ))}

              {templates.length === 0 && (
                <Card>
                  <CardContent className="text-center py-8">
                    <p className="text-muted-foreground">No prompt templates found.</p>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
