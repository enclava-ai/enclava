"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useToast } from "@/hooks/use-toast"
import { 
  Save, 
  Play, 
  ArrowLeft, 
  Plus, 
  Settings, 
  Trash2, 
  Move,
  Zap,
  GitBranch,
  MessageSquare,
  Database,
  Workflow as WorkflowIcon,
  GripVertical
} from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import ProtectedRoute from "@/components/ProtectedRoute"
import StepConfigurationPanel from "@/components/workflows/StepConfigurationPanel"

interface WorkflowStep {
  id: string
  name: string
  type: string
  config: Record<string, any>
  position: { x: number; y: number }
  connections: string[]
}

interface WorkflowDefinition {
  id?: string
  name: string
  description: string
  version: string
  steps: WorkflowStep[]
  variables: Record<string, any>
  outputs: Record<string, string>
  metadata: Record<string, any>
}

const stepTypes = [
  {
    type: "llm_call",
    name: "LLM Call",
    description: "Make a call to a language model",
    icon: <MessageSquare className="h-4 w-4" />,
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
  },
  {
    type: "chatbot",
    name: "Chatbot",
    description: "Use a configured chatbot",
    icon: <MessageSquare className="h-4 w-4" />,
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
  },
  {
    type: "transform",
    name: "Transform",
    description: "Transform or process data",
    icon: <Zap className="h-4 w-4" />,
    color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300"
  },
  {
    type: "conditional",
    name: "Conditional",
    description: "Conditional logic and branching",
    icon: <GitBranch className="h-4 w-4" />,
    color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300"
  },
  {
    type: "parallel",
    name: "Parallel",
    description: "Execute multiple steps in parallel",
    icon: <Move className="h-4 w-4" />,
    color: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300"
  },
  {
    type: "rag_search",
    name: "RAG Search",
    description: "Search documents in RAG collection",
    icon: <Database className="h-4 w-4" />,
    color: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-300"
  }
]

export default function WorkflowBuilderPage() {
  const { toast } = useToast()
  const router = useRouter()
  const searchParams = useSearchParams()
  const workflowId = searchParams.get('id')
  const templateId = searchParams.get('template')

  const [workflow, setWorkflow] = useState<WorkflowDefinition>({
    name: "",
    description: "",
    version: "1.0.0",
    steps: [],
    variables: {},
    outputs: {},
    metadata: {}
  })
  
  const [selectedStep, setSelectedStep] = useState<WorkflowStep | null>(null)
  const [showStepPalette, setShowStepPalette] = useState(false)
  const [showVariablePanel, setShowVariablePanel] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [draggedStepIndex, setDraggedStepIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  
  // Configuration data
  const [availableChatbots, setAvailableChatbots] = useState<Array<{id: string, name: string}>>([])
  const [availableCollections, setAvailableCollections] = useState<string[]>([])

  // Helper function to ensure all steps have position properties
  const ensureStepPositions = (steps: any[]): WorkflowStep[] => {
    return steps.map((step, index) => ({
      ...step,
      position: step.position || { x: 100, y: 100 + index * 120 },
      connections: step.connections || []
    }))
  }

  const loadWorkflow = useCallback(async () => {
    try {
      setLoading(true)
      
      // Get auth token for API calls
      const token = localStorage.getItem('token')
      const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {}
      
      if (workflowId) {
        // Load existing workflow
        const response = await fetch(`/api/workflows/${workflowId}`, {
          headers: authHeaders
        })
        if (response.ok) {
          const data = await response.json()
          setWorkflow({
            ...data.workflow,
            steps: ensureStepPositions(data.workflow.steps || [])
          })
        }
      } else if (templateId) {
        // Load from template
        const response = await fetch(`/api/workflows/templates/${templateId}`, {
          headers: authHeaders
        })
        if (response.ok) {
          const data = await response.json()
          setWorkflow({
            ...data.template.definition,
            id: undefined, // Remove ID for new workflow
            name: `${data.template.definition.name} (Copy)`,
            steps: ensureStepPositions(data.template.definition.steps || [])
          })
        }
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load workflow",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }, [workflowId, templateId, toast])

  const loadConfigurationData = useCallback(async () => {
    try {
      // Get auth token (same pattern as playground)
      const token = localStorage.getItem('token')
      const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {}
      
      // Load available chatbots (existing platform component)
      try {
        const chatbotsResponse = await fetch('/api/chatbot/list', {
          headers: authHeaders
        })
        if (chatbotsResponse.ok) {
          const chatbotsData = await chatbotsResponse.json()
          
          // Backend returns a direct array of chatbot objects
          let chatbotOptions: Array<{id: string, name: string}> = []
          
          if (Array.isArray(chatbotsData)) {
            // Map to both ID and name for display purposes
            chatbotOptions = chatbotsData.map((chatbot: any) => ({
              id: chatbot.id || '',
              name: chatbot.name || chatbot.id || 'Unnamed Chatbot'
            }))
          }
          
          
          // Store full chatbot objects for better UX (names + IDs)
          setAvailableChatbots(chatbotOptions)
          
        }
      } catch (error) {
        // Silently handle error - chatbots will be empty array
      }

      // Load available RAG collections (existing platform component)
      try {
        const collectionsResponse = await fetch('/api/rag/collections', {
          headers: authHeaders
        })
        if (collectionsResponse.ok) {
          const collectionsData = await collectionsResponse.json()
          setAvailableCollections(collectionsData.collections?.map((c: any) => c.name) || [])
        }
      } catch (error) {
        // Silently handle error - collections will be empty array
      }
    } catch (error) {
      // Silently handle error - configuration will use defaults
    }
  }, [])

  useEffect(() => {
    loadWorkflow()
    loadConfigurationData()
  }, [loadWorkflow, loadConfigurationData])

  const saveWorkflow = async () => {
    try {
      setSaving(true)
      
      // Get auth token for API calls
      const token = localStorage.getItem('token')
      const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {}
      
      const method = workflowId ? 'PUT' : 'POST'
      const url = workflowId ? `/api/workflows/${workflowId}` : '/api/workflows'
      
      const response = await fetch(url, {
        method,
        headers: { 
          'Content-Type': 'application/json',
          ...authHeaders
        },
        body: JSON.stringify(workflow)
      })

      if (response.ok) {
        const data = await response.json()
        toast({
          title: "Success",
          description: workflowId ? "Workflow updated" : "Workflow created"
        })
        
        // Redirect to workflow list if this was a new workflow
        if (!workflowId) {
          router.push('/workflows')
        }
      } else {
        throw new Error('Failed to save workflow')
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save workflow",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const testWorkflow = async () => {
    try {
      // Get auth token for API calls
      const token = localStorage.getItem('token')
      const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {}
      
      const response = await fetch('/api/workflows/test', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...authHeaders
        },
        body: JSON.stringify({ workflow, test_data: {} })
      })

      if (response.ok) {
        const result = await response.json()
        toast({
          title: "Test Result",
          description: `Workflow test completed: ${result.status}`
        })
      } else {
        throw new Error('Test failed')
      }
    } catch (error) {
      toast({
        title: "Test Failed",
        description: "Failed to test workflow",
        variant: "destructive"
      })
    }
  }

  const addStep = (stepType: string) => {
    const newStep: WorkflowStep = {
      id: `step_${Date.now()}`,
      name: `New ${stepTypes.find(t => t.type === stepType)?.name || stepType}`,
      type: stepType,
      config: {},
      position: { x: 100, y: 100 + workflow.steps.length * 120 },
      connections: []
    }

    setWorkflow(prev => ({
      ...prev,
      steps: [...prev.steps, newStep]
    }))
    
    setSelectedStep(newStep)
    setShowStepPalette(false)
  }

  const updateStep = (stepId: string, updates: Partial<WorkflowStep>) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps.map(step =>
        step.id === stepId ? { ...step, ...updates } : step
      )
    }))
    
    if (selectedStep?.id === stepId) {
      setSelectedStep(prev => prev ? { ...prev, ...updates } : null)
    }
  }

  const deleteStep = (stepId: string) => {
    setWorkflow(prev => ({
      ...prev,
      steps: prev.steps.filter(step => step.id !== stepId)
    }))
    
    if (selectedStep?.id === stepId) {
      setSelectedStep(null)
    }
  }

  const addVariable = (name: string, value: any) => {
    setWorkflow(prev => ({
      ...prev,
      variables: { ...prev.variables, [name]: value }
    }))
  }

  const removeVariable = (name: string) => {
    const { [name]: removed, ...rest } = workflow.variables
    setWorkflow(prev => ({ ...prev, variables: rest }))
  }

  const reorderSteps = (fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex) return
    
    const newSteps = [...workflow.steps]
    const [draggedStep] = newSteps.splice(fromIndex, 1)
    newSteps.splice(toIndex, 0, draggedStep)
    
    // Recalculate canvas positions based on new order (vertical layout)
    const updatedSteps = newSteps.map((step, index) => ({
      ...step,
      position: { 
        x: 100, 
        y: 100 + index * 120 
      }
    }))
    
    setWorkflow(prev => ({
      ...prev,
      steps: updatedSteps
    }))
    
    // Update selected step if it was the one being dragged
    if (selectedStep?.id === draggedStep.id) {
      setSelectedStep(draggedStep)
    }
  }

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedStepIndex(index)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/html', e.currentTarget.outerHTML)
    
    // Add visual feedback
    if (e.currentTarget instanceof HTMLElement) {
      e.currentTarget.style.opacity = '0.5'
    }
  }

  const handleDragEnd = (e: React.DragEvent) => {
    setDraggedStepIndex(null)
    setDragOverIndex(null)
    
    // Reset visual feedback
    if (e.currentTarget instanceof HTMLElement) {
      e.currentTarget.style.opacity = '1'
    }
  }

  const handleDragOver = (e: React.DragEvent, overIndex: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    
    if (draggedStepIndex !== null && draggedStepIndex !== overIndex) {
      setDragOverIndex(overIndex)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    // Only clear if we're leaving the entire step element, not just a child
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOverIndex(null)
    }
  }

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault()
    
    if (draggedStepIndex !== null && draggedStepIndex !== dropIndex) {
      reorderSteps(draggedStepIndex, dropIndex)
    }
    
    setDraggedStepIndex(null)
    setDragOverIndex(null)
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
      <div className="h-screen flex flex-col overflow-hidden">
        {/* Header */}
        <div className="border-b bg-background/95 backdrop-blur">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" size="sm" onClick={() => router.back()}>
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back
                </Button>
                <div>
                  <h1 className="text-xl font-semibold flex items-center gap-2">
                    <WorkflowIcon className="h-5 w-5" />
                    {workflowId ? 'Edit Workflow' : 'New Workflow'}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {workflow.name || 'Untitled Workflow'}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setShowVariablePanel(true)}
                >
                  Variables ({Object.keys(workflow.variables).length})
                </Button>
                <Button variant="outline" size="sm" onClick={testWorkflow}>
                  <Play className="h-4 w-4 mr-2" />
                  Test
                </Button>
                <Button size="sm" onClick={saveWorkflow} disabled={saving}>
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Step Palette */}
          <div className="w-64 border-r bg-muted/50 overflow-y-auto">
            <div className="p-4">
              <h3 className="font-medium mb-3">Add Steps</h3>
              <div className="space-y-2">
                {stepTypes.map((stepType) => (
                  <Button
                    key={stepType.type}
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => addStep(stepType.type)}
                  >
                    {stepType.icon}
                    <span className="ml-2">{stepType.name}</span>
                  </Button>
                ))}
              </div>
              
              <Separator className="my-4" />
              
              <div className="mb-3">
                <h3 className="font-medium">Workflow Steps</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Drag steps to reorder them
                </p>
              </div>
              <div className="space-y-1">
                {workflow.steps.map((step, index) => (
                  <div
                    key={step.id}
                    draggable={true}
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, index)}
                    className={`p-2 rounded text-sm cursor-pointer border transition-all ${
                      selectedStep?.id === step.id 
                        ? 'bg-primary/10 border-primary' 
                        : 'bg-background border-border hover:bg-accent'
                    } ${
                      draggedStepIndex === index ? 'opacity-50' : ''
                    } ${
                      dragOverIndex === index && draggedStepIndex !== index 
                        ? 'border-primary/50 bg-primary/5' 
                        : ''
                    }`}
                    onClick={() => setSelectedStep(step)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <GripVertical className="h-3 w-3 text-muted-foreground cursor-grab" />
                        <span className="text-xs text-muted-foreground">
                          {index + 1}
                        </span>
                        {stepTypes.find(t => t.type === step.type)?.icon}
                        <span className="truncate">{step.name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteStep(step.id)
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                    <Badge variant="secondary" className="text-xs mt-1">
                      {step.type}
                    </Badge>
                  </div>
                ))}
                
                {workflow.steps.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No steps added yet
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Center Panel - Canvas */}
          <div className="flex-1 overflow-hidden">
            <div className="h-full bg-muted/20 relative" style={{
              backgroundImage: 'radial-gradient(circle, #0000001a 1px, transparent 1px)',
              backgroundSize: '20px 20px'
            }}>
              {/* Canvas Content */}
              <div className="absolute inset-0 overflow-auto p-8">
                {workflow.steps.length === 0 ? (
                  <div className="h-full flex items-center justify-center">
                    <div className="text-center">
                      <WorkflowIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                      <h3 className="text-lg font-semibold mb-2">Start Building Your Workflow</h3>
                      <p className="text-muted-foreground mb-4">
                        Add steps from the left panel to create your workflow
                      </p>
                      <Button onClick={() => addStep('llm_call')}>
                        <Plus className="h-4 w-4 mr-2" />
                        Add First Step
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="relative">
                    {/* Workflow Steps */}
                    {workflow.steps.map((step, index) => (
                      <div
                        key={step.id}
                        className={`absolute p-4 bg-background border rounded-lg shadow-sm cursor-pointer transition-all ${
                          selectedStep?.id === step.id 
                            ? 'border-primary shadow-md' 
                            : 'border-border hover:shadow-md'
                        }`}
                        style={{
                          left: step.position?.x || 100,
                          top: step.position?.y || (100 + index * 120),
                          width: '280px'
                        }}
                        onClick={() => setSelectedStep(step)}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <div className="flex items-center gap-1">
                            {stepTypes.find(t => t.type === step.type)?.icon}
                            <span className="text-xs font-medium">{index + 1}</span>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {step.type}
                          </Badge>
                        </div>
                        <h4 className="font-medium text-sm mb-1 truncate">{step.name}</h4>
                        <p className="text-xs text-muted-foreground">
                          {stepTypes.find(t => t.type === step.type)?.description}
                        </p>
                      </div>
                    ))}
                    
                    {/* Connection Lines - Vertical layout */}
                    <svg className="absolute inset-0 pointer-events-none">
                      {workflow.steps.map((step, index) => {
                        if (index < workflow.steps.length - 1) {
                          const nextStep = workflow.steps[index + 1]
                          return (
                            <line
                              key={`${step.id}-${nextStep.id}`}
                              x1={step.position.x + 140}
                              y1={step.position.y + 80}
                              x2={nextStep.position.x + 140}
                              y2={nextStep.position.y}
                              stroke="hsl(var(--border))"
                              strokeWidth="2"
                              markerEnd="url(#arrowhead)"
                            />
                          )
                        }
                        return null
                      })}
                      <defs>
                        <marker
                          id="arrowhead"
                          markerWidth="10"
                          markerHeight="7"
                          refX="9"
                          refY="3.5"
                          orient="auto"
                        >
                          <polygon
                            points="0 0, 10 3.5, 0 7"
                            fill="hsl(var(--border))"
                          />
                        </marker>
                      </defs>
                    </svg>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Panel - Properties */}
          <div className="w-80 border-l bg-muted/50 overflow-y-auto">
            <div className="p-4">
              <Tabs value={selectedStep ? "step" : "workflow"} className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="workflow">Workflow</TabsTrigger>
                  <TabsTrigger value="step" disabled={!selectedStep}>
                    Step
                  </TabsTrigger>
                </TabsList>
                
                {/* Workflow Properties */}
                <TabsContent value="workflow" className="space-y-4">
                  <div>
                    <Label htmlFor="name">Name</Label>
                    <Input
                      id="name"
                      value={workflow.name}
                      onChange={(e) => setWorkflow(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter workflow name"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      value={workflow.description}
                      onChange={(e) => setWorkflow(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Enter workflow description"
                      rows={3}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="version">Version</Label>
                    <Input
                      id="version"
                      value={workflow.version}
                      onChange={(e) => setWorkflow(prev => ({ ...prev, version: e.target.value }))}
                      placeholder="1.0.0"
                    />
                  </div>
                  
                  <Separator />
                  
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <Label>Variables</Label>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowVariablePanel(true)}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                        Add
                      </Button>
                    </div>
                    <div className="space-y-2">
                      {Object.entries(workflow.variables).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between p-2 bg-background rounded border">
                          <div>
                            <span className="text-sm font-medium">{key}</span>
                            <p className="text-xs text-muted-foreground truncate">
                              {String(value)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={() => removeVariable(key)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      ))}
                      
                      {Object.keys(workflow.variables).length === 0 && (
                        <p className="text-sm text-muted-foreground text-center py-4">
                          No variables defined
                        </p>
                      )}
                    </div>
                  </div>
                </TabsContent>
                
                {/* Step Properties */}
                <TabsContent value="step" className="space-y-4">
                  {selectedStep ? (
                    <>
                      <div>
                        <Label htmlFor="step-name">Step Name</Label>
                        <Input
                          id="step-name"
                          value={selectedStep.name}
                          onChange={(e) => updateStep(selectedStep.id, { name: e.target.value })}
                          placeholder="Enter step name"
                        />
                      </div>
                      
                      <div>
                        <Label>Step Type</Label>
                        <div className="flex items-center gap-2 mt-1">
                          {stepTypes.find(t => t.type === selectedStep.type)?.icon}
                          <Badge variant="secondary">{selectedStep.type}</Badge>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      <StepConfigurationPanel
                        step={selectedStep}
                        onUpdateStep={updateStep}
                        availableVariables={Object.keys(workflow.variables)}
                        availableChatbots={availableChatbots}
                        availableCollections={availableCollections}
                      />
                    </>
                  ) : (
                    <div className="text-center py-8">
                      <Settings className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">
                        Select a step to configure its properties
                      </p>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      </div>

      {/* Variables Dialog */}
      <Dialog open={showVariablePanel} onOpenChange={setShowVariablePanel}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manage Variables</DialogTitle>
            <DialogDescription>
              Add and manage workflow variables that can be used in step configurations
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="Variable name" id="var-name" />
              <Input placeholder="Variable value" id="var-value" />
            </div>
            <Button 
              onClick={() => {
                const nameEl = document.getElementById('var-name') as HTMLInputElement
                const valueEl = document.getElementById('var-value') as HTMLInputElement
                if (nameEl?.value && valueEl?.value) {
                  addVariable(nameEl.value, valueEl.value)
                  nameEl.value = ''
                  valueEl.value = ''
                }
              }}
              className="w-full"
            >
              Add Variable
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </ProtectedRoute>
  )
}