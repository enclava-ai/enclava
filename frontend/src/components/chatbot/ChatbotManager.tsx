"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { 
  MessageCircle, 
  Plus, 
  Settings, 
  Trash2, 
  Copy, 
  Play,
  Bot,
  Brain,
  Users,
  BookOpen,
  Palette,
  Key,
  Globe
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { ChatInterface } from "./ChatInterface"
import ModelSelector from "@/components/playground/ModelSelector"

interface ChatbotConfig {
  name: string
  chatbot_type: string
  model: string
  system_prompt: string
  use_rag: boolean
  rag_collection?: string
  rag_top_k: number
  temperature: number
  max_tokens: number
  memory_length: number
  fallback_responses: string[]
}

interface ChatbotInstance {
  id: string
  name: string
  config: ChatbotConfig
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

interface RagCollection {
  id: string
  name: string
  description: string
  document_count: number
}

const CHATBOT_TYPES = [
  { 
    value: "assistant", 
    label: "General Assistant", 
    description: "Helpful AI assistant for general questions",
    icon: Bot,
    color: "bg-blue-500"
  },
  { 
    value: "customer_support", 
    label: "Customer Support", 
    description: "Professional customer service chatbot",
    icon: Users,
    color: "bg-green-500"
  },
  { 
    value: "teacher", 
    label: "Teacher", 
    description: "Educational tutor and learning assistant",
    icon: BookOpen,
    color: "bg-purple-500"
  },
  { 
    value: "researcher", 
    label: "Researcher", 
    description: "Research assistant with fact-checking focus",
    icon: Brain,
    color: "bg-indigo-500"
  },
  { 
    value: "creative_writer", 
    label: "Creative Writer", 
    description: "Creative writing and storytelling assistant",
    icon: Palette,
    color: "bg-pink-500"
  },
  { 
    value: "custom", 
    label: "Custom", 
    description: "Custom chatbot with user-defined personality",
    icon: Settings,
    color: "bg-gray-500"
  }
]


interface PromptTemplate {
  id: string
  name: string
  type_key: string
  description?: string
  system_prompt: string
  is_default: boolean
  is_active: boolean
  version: number
}

export function ChatbotManager() {
  const [chatbots, setChatbots] = useState<ChatbotInstance[]>([])
  const [ragCollections, setRagCollections] = useState<RagCollection[]>([])
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deletingChatbot, setDeletingChatbot] = useState<ChatbotInstance | null>(null)
  const [selectedChatbot, setSelectedChatbot] = useState<ChatbotInstance | null>(null)
  const [editingChatbot, setEditingChatbot] = useState<ChatbotInstance | null>(null)
  const [showChatInterface, setShowChatInterface] = useState(false)
  const [testingChatbot, setTestingChatbot] = useState<ChatbotInstance | null>(null)
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false)
  const [apiKeyChatbot, setApiKeyChatbot] = useState<ChatbotInstance | null>(null)
  const [apiKeys, setApiKeys] = useState<any[]>([])
  const [loadingApiKeys, setLoadingApiKeys] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const { toast } = useToast()

  // New chatbot form state
  const [newChatbot, setNewChatbot] = useState<ChatbotConfig>({
    name: "",
    chatbot_type: "assistant",
    model: "",
    system_prompt: "",
    use_rag: false,
    rag_collection: "",
    rag_top_k: 5,
    temperature: 0.7,
    max_tokens: 1000,
    memory_length: 10,
    fallback_responses: [
      "I'm not sure how to help with that. Could you please rephrase your question?",
      "I don't have enough information to answer that question accurately.",
      "That's outside my knowledge area. Is there something else I can help you with?"
    ]
  })

  // Edit chatbot form state
  const [editChatbot, setEditChatbot] = useState<ChatbotConfig>({
    name: "",
    chatbot_type: "assistant",
    model: "",
    system_prompt: "",
    use_rag: false,
    rag_collection: "",
    rag_top_k: 5,
    temperature: 0.7,
    max_tokens: 1000,
    memory_length: 10,
    fallback_responses: []
  })

  useEffect(() => {
    loadChatbots()
    loadRagCollections()
    loadPromptTemplates()
  }, [])

  // Auto-populate system prompt when templates are loaded
  useEffect(() => {
    if (promptTemplates.length > 0 && !newChatbot.system_prompt) {
      const defaultTemplate = loadTemplateForType('assistant')
      setNewChatbot(prev => ({ ...prev, system_prompt: defaultTemplate }))
    }
  }, [promptTemplates])

  const handleTestChat = (chatbot: ChatbotInstance) => {
    setTestingChatbot(chatbot)
    setShowChatInterface(true)
  }

  const handleEditChat = (chatbot: ChatbotInstance) => {
    setEditingChatbot(chatbot)
    setEditChatbot({
      name: chatbot.config.name,
      chatbot_type: chatbot.config.chatbot_type,
      model: chatbot.config.model,
      system_prompt: chatbot.config.system_prompt,
      use_rag: chatbot.config.use_rag,
      rag_collection: chatbot.config.rag_collection ? String(chatbot.config.rag_collection) : "",
      rag_top_k: chatbot.config.rag_top_k,
      temperature: chatbot.config.temperature,
      max_tokens: chatbot.config.max_tokens,
      memory_length: chatbot.config.memory_length,
      fallback_responses: chatbot.config.fallback_responses || []
    })
    setShowEditDialog(true)
  }

  const loadChatbots = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/chatbot/list', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setChatbots(data)
      }
    } catch (error) {
      console.error('Failed to load chatbots:', error)
      toast({
        title: "Error",
        description: "Failed to load chatbots",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const loadRagCollections = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/rag/collections', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setRagCollections(data.collections || [])
      }
    } catch (error) {
      console.error('Failed to load RAG collections:', error)
    }
  }

  const loadPromptTemplates = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/prompt-templates/templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const templates = await response.json()
        setPromptTemplates(templates)
      }
    } catch (error) {
      console.error('Failed to load prompt templates:', error)
    }
  }

  const loadTemplateForType = (chatbotType: string) => {
    const template = promptTemplates.find(t => t.type_key === chatbotType)
    return template?.system_prompt || ""
  }

  const createChatbot = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/chatbot/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newChatbot)
      })

      if (response.ok) {
        const chatbot = await response.json()
        setChatbots(prev => [...prev, chatbot])
        setShowCreateDialog(false)
        resetForm()
        toast({
          title: "Success",
          description: "Chatbot created successfully"
        })
      } else {
        throw new Error('Failed to create chatbot')
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create chatbot",
        variant: "destructive"
      })
    }
  }

  const updateChatbot = async () => {
    if (!editingChatbot) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/chatbot/update/${editingChatbot.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editChatbot)
      })

      if (response.ok) {
        const updatedChatbot = await response.json()
        setChatbots(prev => prev.map(cb => cb.id === updatedChatbot.id ? updatedChatbot : cb))
        setShowEditDialog(false)
        setEditingChatbot(null)
        resetEditForm()
        toast({
          title: "Success",
          description: "Chatbot updated successfully"
        })
      } else {
        throw new Error('Failed to update chatbot')
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update chatbot",
        variant: "destructive"
      })
    }
  }

  const resetForm = () => {
    setNewChatbot({
      name: "",
      chatbot_type: "assistant",
      model: "",
      system_prompt: "",
      use_rag: false,
      rag_collection: "",
      rag_top_k: 5,
      temperature: 0.7,
      max_tokens: 1000,
      memory_length: 10,
      fallback_responses: [
        "I'm not sure how to help with that. Could you please rephrase your question?",
        "I don't have enough information to answer that question accurately.",
        "That's outside my knowledge area. Is there something else I can help you with?"
      ]
    })
  }

  const resetEditForm = () => {
    setEditChatbot({
      name: "",
      chatbot_type: "assistant",
      model: "",
      system_prompt: "",
      use_rag: false,
      rag_collection: "",
      rag_top_k: 5,
      temperature: 0.7,
      max_tokens: 1000,
      memory_length: 10,
      fallback_responses: []
    })
  }

  const handleDeleteChat = (chatbot: ChatbotInstance) => {
    setDeletingChatbot(chatbot)
    setShowDeleteDialog(true)
  }

  const deleteChatbot = async () => {
    if (!deletingChatbot) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/chatbot/delete/${deletingChatbot.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        setChatbots(prev => prev.filter(c => c.id !== deletingChatbot.id))
        setShowDeleteDialog(false)
        setDeletingChatbot(null)
        toast({
          title: "Success",
          description: `${deletingChatbot.name} has been deleted`
        })
      } else {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to delete chatbot')
      }
    } catch (error) {
      console.error('Failed to delete chatbot:', error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete chatbot",
        variant: "destructive"
      })
    }
  }

  const handleManageApiKeys = async (chatbot: ChatbotInstance) => {
    setApiKeyChatbot(chatbot)
    setShowApiKeyDialog(true)
    await loadApiKeys(chatbot.id)
  }

  const loadApiKeys = async (chatbotId: string) => {
    setLoadingApiKeys(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/chatbot/${chatbotId}/api-key`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setApiKeys(data.api_keys || [])
      } else {
        console.error('Failed to load API keys')
        setApiKeys([])
      }
    } catch (error) {
      console.error('Failed to load API keys:', error)
      setApiKeys([])
    } finally {
      setLoadingApiKeys(false)
    }
  }

  const createApiKey = async () => {
    if (!apiKeyChatbot) return

    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/chatbot/${apiKeyChatbot.id}/api-key`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setNewApiKey(data.secret_key)
        await loadApiKeys(apiKeyChatbot.id)
        toast({
          title: "Success",
          description: "API key created successfully"
        })
      } else {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create API key')
      }
    } catch (error) {
      console.error('Failed to create API key:', error)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create API key",
        variant: "destructive"
      })
    }
  }

  const getChatbotTypeInfo = (type: string) => {
    const dynamicTypes = getDynamicChatbotTypes()
    return dynamicTypes.find(t => t.value === type) || dynamicTypes[0] || CHATBOT_TYPES[0]
  }

  // Convert prompt templates to chatbot type UI format
  const getDynamicChatbotTypes = () => {
    if (promptTemplates.length === 0) {
      return CHATBOT_TYPES // Fallback to static types while loading
    }

    return promptTemplates.map(template => {
      // Try to find existing type info for known types
      const existingType = CHATBOT_TYPES.find(t => t.value === template.type_key)
      
      if (existingType) {
        // Use existing icon and color for known types
        return {
          ...existingType,
          name: template.name, // Use the template name which might be customized
          description: template.description || existingType.description
        }
      } else {
        // Create new type for custom templates
        return {
          value: template.type_key,
          label: template.name,
          description: template.description || `Custom ${template.name} chatbot`,
          icon: Bot, // Default icon for custom types
          color: "bg-slate-500" // Default color for custom types
        }
      }
    })
  }


  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Chatbot Manager</h1>
          <p className="text-muted-foreground">
            Create and manage AI chatbots with custom personalities and knowledge bases.
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Chatbot
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create New Chatbot</DialogTitle>
              <DialogDescription>
                Configure your AI chatbot with custom personality, knowledge base, and behavior.
              </DialogDescription>
            </DialogHeader>
            
            <Tabs defaultValue="basic" className="mt-6">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic</TabsTrigger>
                <TabsTrigger value="personality">Personality</TabsTrigger>
                <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4 mt-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="name">Chatbot Name</Label>
                    <Input
                      id="name"
                      value={newChatbot.name}
                      onChange={(e) => setNewChatbot(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., Customer Support Bot"
                    />
                  </div>

                  <div>
                    <Label htmlFor="type">Chatbot Type</Label>
                    <div className="grid grid-cols-2 gap-3 mt-2">
                      {getDynamicChatbotTypes().map((type) => {
                        const Icon = type.icon
                        return (
                          <Card 
                            key={type.value}
                            className={`cursor-pointer transition-all ${
                              newChatbot.chatbot_type === type.value 
                                ? 'ring-2 ring-primary' 
                                : 'hover:bg-muted/50'
                            }`}
                            onClick={() => {
                              const templatePrompt = loadTemplateForType(type.value)
                              setNewChatbot(prev => ({ 
                                ...prev, 
                                chatbot_type: type.value,
                                system_prompt: templatePrompt
                              }))
                            }}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-start space-x-3">
                                <div className={`p-2 rounded-lg ${type.color}`}>
                                  <Icon className="h-4 w-4 text-white" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-sm">{type.label}</p>
                                  <p className="text-xs text-muted-foreground">{type.description}</p>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        )
                      })}
                    </div>
                  </div>

                  <div>
                    <ModelSelector
                      value={newChatbot.model}
                      onValueChange={(value) => setNewChatbot(prev => ({ ...prev, model: value }))}
                      filter="chat"
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="personality" className="space-y-4 mt-6">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <Label htmlFor="prompt">System Prompt</Label>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const templatePrompt = loadTemplateForType(newChatbot.chatbot_type)
                        setNewChatbot(prev => ({ ...prev, system_prompt: templatePrompt }))
                        toast({
                          title: "Template Loaded",
                          description: "System prompt updated from template"
                        })
                      }}
                    >
                      Load Template
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Define your chatbot's personality, expertise, and response style. This prompt shapes how your chatbot behaves and responds to users.
                  </p>
                  <Textarea
                    id="prompt"
                    value={newChatbot.system_prompt}
                    onChange={(e) => setNewChatbot(prev => ({ ...prev, system_prompt: e.target.value }))}
                    placeholder="You are a helpful AI assistant. Provide accurate, concise, and friendly responses..."
                    className="min-h-[200px] font-mono text-sm"
                  />
                  <div className="flex justify-between items-center mt-1">
                    <p className="text-xs text-muted-foreground">
                      💡 Tip: Be specific about tone, expertise, and response format preferences
                    </p>
                    <span className="text-xs text-muted-foreground">
                      {newChatbot.system_prompt.length} characters
                    </span>
                  </div>
                </div>

                <div>
                  <Label>Response Creativity: {newChatbot.temperature}</Label>
                  <Slider
                    value={[newChatbot.temperature]}
                    onValueChange={([value]) => setNewChatbot(prev => ({ ...prev, temperature: value }))}
                    min={0}
                    max={1}
                    step={0.1}
                    className="mt-2"
                  />
                  <div className="flex justify-between text-sm text-muted-foreground mt-1">
                    <span>Focused</span>
                    <span>Creative</span>
                  </div>
                </div>

                <div>
                  <Label>Fallback Responses</Label>
                  <div className="space-y-2 mt-2">
                    {newChatbot.fallback_responses.map((response, index) => (
                      <div key={index} className="flex items-center space-x-2">
                        <Input
                          value={response}
                          onChange={(e) => {
                            const newResponses = [...newChatbot.fallback_responses]
                            newResponses[index] = e.target.value
                            setNewChatbot(prev => ({ ...prev, fallback_responses: newResponses }))
                          }}
                          placeholder="Fallback response..."
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            const newResponses = newChatbot.fallback_responses.filter((_, i) => i !== index)
                            setNewChatbot(prev => ({ ...prev, fallback_responses: newResponses }))
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setNewChatbot(prev => ({
                          ...prev,
                          fallback_responses: [...prev.fallback_responses, ""]
                        }))
                      }}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Response
                    </Button>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="knowledge" className="space-y-4 mt-6">
                <div className="flex items-center space-x-2">
                  <Switch
                    checked={newChatbot.use_rag}
                    onCheckedChange={(checked) => setNewChatbot(prev => ({ ...prev, use_rag: checked }))}
                  />
                  <Label>Enable Knowledge Base</Label>
                </div>

                {newChatbot.use_rag && (
                  <>
                    <div>
                      <Label htmlFor="collection">Knowledge Base Collection</Label>
                      <Select 
                        value={newChatbot.rag_collection ?? ''} 
                        onValueChange={(value) => setNewChatbot(prev => ({ ...prev, rag_collection: String(value) }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a collection" />
                        </SelectTrigger>
                        <SelectContent>
                          {ragCollections.map((collection) => (
                            <SelectItem key={collection.id} value={collection.id}>
                              <div>
                                <div className="font-medium">{collection.name}</div>
                                <div className="text-sm text-muted-foreground">
                                  {collection.document_count} documents
                                </div>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>Knowledge Base Results: {newChatbot.rag_top_k}</Label>
                      <Slider
                        value={[newChatbot.rag_top_k]}
                        onValueChange={([value]) => setNewChatbot(prev => ({ ...prev, rag_top_k: value }))}
                        min={1}
                        max={10}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="advanced" className="space-y-4 mt-6">
                <div>
                  <Label>Maximum Response Length: {newChatbot.max_tokens}</Label>
                  <Slider
                    value={[newChatbot.max_tokens]}
                    onValueChange={([value]) => setNewChatbot(prev => ({ ...prev, max_tokens: value }))}
                    min={50}
                    max={4000}
                    step={50}
                    className="mt-2"
                  />
                </div>

                <div>
                  <Label>Conversation Memory: {newChatbot.memory_length} message pairs</Label>
                  <Slider
                    value={[newChatbot.memory_length]}
                    onValueChange={([value]) => setNewChatbot(prev => ({ ...prev, memory_length: value }))}
                    min={1}
                    max={50}
                    step={1}
                    className="mt-2"
                  />
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={createChatbot} disabled={!newChatbot.name}>
                Create Chatbot
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Edit Chatbot Dialog */}
        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Chatbot</DialogTitle>
              <DialogDescription>
                Update your chatbot configuration and behavior settings.
              </DialogDescription>
            </DialogHeader>
            
            <Tabs defaultValue="basic" className="mt-6">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic</TabsTrigger>
                <TabsTrigger value="personality">Personality</TabsTrigger>
                <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4 mt-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="edit-name">Chatbot Name</Label>
                    <Input
                      id="edit-name"
                      value={editChatbot.name}
                      onChange={(e) => setEditChatbot(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., Customer Support Bot"
                    />
                  </div>

                  <div>
                    <Label htmlFor="edit-type">Chatbot Type</Label>
                    <div className="grid grid-cols-2 gap-3 mt-2">
                      {getDynamicChatbotTypes().map((type) => {
                        const Icon = type.icon
                        return (
                          <Card 
                            key={type.value}
                            className={`cursor-pointer transition-all ${
                              editChatbot.chatbot_type === type.value 
                                ? 'ring-2 ring-primary' 
                                : 'hover:bg-muted/50'
                            }`}
                            onClick={() => {
                              const templatePrompt = loadTemplateForType(type.value)
                              setEditChatbot(prev => ({ 
                                ...prev, 
                                chatbot_type: type.value,
                                system_prompt: templatePrompt
                              }))
                            }}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-start space-x-3">
                                <div className={`p-2 rounded-lg ${type.color}`}>
                                  <Icon className="h-4 w-4 text-white" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-sm">{type.label}</p>
                                  <p className="text-xs text-muted-foreground">{type.description}</p>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        )
                      })}
                    </div>
                  </div>

                  <div>
                    <ModelSelector
                      value={editChatbot.model}
                      onValueChange={(value) => setEditChatbot(prev => ({ ...prev, model: value }))}
                      filter="chat"
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="personality" className="space-y-4 mt-6">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <Label htmlFor="edit-prompt">System Prompt</Label>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const templatePrompt = loadTemplateForType(editChatbot.chatbot_type)
                        setEditChatbot(prev => ({ ...prev, system_prompt: templatePrompt }))
                        toast({
                          title: "Template Loaded",
                          description: "System prompt updated from template"
                        })
                      }}
                    >
                      Load Template
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    Define your chatbot's personality, expertise, and response style. This prompt shapes how your chatbot behaves and responds to users.
                  </p>
                  <Textarea
                    id="edit-prompt"
                    value={editChatbot.system_prompt}
                    onChange={(e) => setEditChatbot(prev => ({ ...prev, system_prompt: e.target.value }))}
                    placeholder="You are a helpful AI assistant. Provide accurate, concise, and friendly responses..."
                    className="min-h-[200px] font-mono text-sm"
                  />
                  <div className="flex justify-between items-center mt-1">
                    <p className="text-xs text-muted-foreground">
                      💡 Tip: Be specific about tone, expertise, and response format preferences
                    </p>
                    <span className="text-xs text-muted-foreground">
                      {editChatbot.system_prompt.length} characters
                    </span>
                  </div>
                </div>

                <div>
                  <Label>Response Creativity: {editChatbot.temperature}</Label>
                  <Slider
                    value={[editChatbot.temperature]}
                    onValueChange={([value]) => setEditChatbot(prev => ({ ...prev, temperature: value }))}
                    min={0}
                    max={1}
                    step={0.1}
                    className="mt-2"
                  />
                  <div className="flex justify-between text-sm text-muted-foreground mt-1">
                    <span>Focused</span>
                    <span>Creative</span>
                  </div>
                </div>

                <div>
                  <Label>Fallback Responses</Label>
                  <div className="space-y-2 mt-2">
                    {editChatbot.fallback_responses.map((response, index) => (
                      <div key={index} className="flex items-center space-x-2">
                        <Input
                          value={response}
                          onChange={(e) => {
                            const newResponses = [...editChatbot.fallback_responses]
                            newResponses[index] = e.target.value
                            setEditChatbot(prev => ({ ...prev, fallback_responses: newResponses }))
                          }}
                          placeholder="Fallback response..."
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            const newResponses = editChatbot.fallback_responses.filter((_, i) => i !== index)
                            setEditChatbot(prev => ({ ...prev, fallback_responses: newResponses }))
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditChatbot(prev => ({
                          ...prev,
                          fallback_responses: [...prev.fallback_responses, ""]
                        }))
                      }}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Response
                    </Button>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="knowledge" className="space-y-4 mt-6">
                <div className="flex items-center space-x-2">
                  <Switch
                    checked={editChatbot.use_rag}
                    onCheckedChange={(checked) => setEditChatbot(prev => ({ ...prev, use_rag: checked }))}
                  />
                  <Label>Enable Knowledge Base</Label>
                </div>

                {editChatbot.use_rag && (
                  <>
                    <div>
                      <Label htmlFor="edit-collection">Knowledge Base Collection</Label>
                      <Select 
                        value={editChatbot.rag_collection ?? ''} 
                        onValueChange={(value) => setEditChatbot(prev => ({ ...prev, rag_collection: String(value) }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a collection" />
                        </SelectTrigger>
                        <SelectContent>
                          {ragCollections.map((collection) => (
                            <SelectItem key={collection.id} value={collection.id}>
                              <div>
                                <div className="font-medium">{collection.name}</div>
                                <div className="text-sm text-muted-foreground">
                                  {collection.document_count} documents
                                </div>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>Knowledge Base Results: {editChatbot.rag_top_k}</Label>
                      <Slider
                        value={[editChatbot.rag_top_k]}
                        onValueChange={([value]) => setEditChatbot(prev => ({ ...prev, rag_top_k: value }))}
                        min={1}
                        max={10}
                        step={1}
                        className="mt-2"
                      />
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="advanced" className="space-y-4 mt-6">
                <div>
                  <Label>Maximum Response Length: {editChatbot.max_tokens}</Label>
                  <Slider
                    value={[editChatbot.max_tokens]}
                    onValueChange={([value]) => setEditChatbot(prev => ({ ...prev, max_tokens: value }))}
                    min={50}
                    max={4000}
                    step={50}
                    className="mt-2"
                  />
                </div>

                <div>
                  <Label>Conversation Memory: {editChatbot.memory_length} message pairs</Label>
                  <Slider
                    value={[editChatbot.memory_length]}
                    onValueChange={([value]) => setEditChatbot(prev => ({ ...prev, memory_length: value }))}
                    min={1}
                    max={50}
                    step={1}
                    className="mt-2"
                  />
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end space-x-2 mt-6 pt-6 border-t">
              <Button variant="outline" onClick={() => {
                setShowEditDialog(false)
                setEditingChatbot(null)
                resetEditForm()
              }}>
                Cancel
              </Button>
              <Button onClick={updateChatbot} disabled={!editChatbot.name}>
                Update Chatbot
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Chatbots List */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {chatbots.map((chatbot) => {
          const typeInfo = getChatbotTypeInfo(chatbot.config.chatbot_type)
          const Icon = typeInfo.icon

          return (
            <Card key={chatbot.id} className="group hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className={`p-3 rounded-lg ${typeInfo.color}`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{chatbot.name}</CardTitle>
                      <CardDescription>{typeInfo.label}</CardDescription>
                    </div>
                  </div>
                  <Badge variant={chatbot.is_active ? "default" : "secondary"}>
                    {chatbot.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Model</span>
                    <Badge variant="outline" className="text-xs">{chatbot.config.model}</Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Knowledge Base</span>
                    <Badge variant={chatbot.config.use_rag ? "default" : "secondary"}>
                      {chatbot.config.use_rag ? "Enabled" : "Disabled"}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Memory</span>
                    <span>{chatbot.config.memory_length} messages</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 mt-4 pt-4 border-t">
                  <Button size="sm" className="flex-1" onClick={() => handleTestChat(chatbot)}>
                    <Play className="h-4 w-4 mr-2" />
                    Test Chat
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleEditChat(chatbot)}>
                    <Settings className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleManageApiKeys(chatbot)}>
                    <Key className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline">
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDeleteChat(chatbot)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}

        {chatbots.length === 0 && !loading && (
          <Card className="col-span-full">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <MessageCircle className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No chatbots yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first AI chatbot to get started with automated conversations.
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Chatbot
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Chat Interface Modal */}
      {showChatInterface && testingChatbot && (
        <Dialog open={showChatInterface} onOpenChange={setShowChatInterface}>
          <DialogContent className="max-w-4xl max-h-[90vh] p-0">
            <DialogHeader className="sr-only">
              <DialogTitle>Chat with {testingChatbot.name}</DialogTitle>
              <DialogDescription>
                Test your chatbot by having a conversation
              </DialogDescription>
            </DialogHeader>
            <ChatInterface
              chatbotId={testingChatbot.id}
              chatbotName={testingChatbot.name}
              onClose={() => setShowChatInterface(false)}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* API Key Management Dialog */}
      <Dialog open={showApiKeyDialog} onOpenChange={(open) => {
        setShowApiKeyDialog(open)
        if (!open) {
          setApiKeyChatbot(null)
          setApiKeys([])
          setNewApiKey(null)
        }
      }}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              API Access - {apiKeyChatbot?.name}
            </DialogTitle>
            <DialogDescription>
              Generate API keys to integrate this chatbot into external applications.
              Each API key is restricted to this specific chatbot only.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-6">
            {/* API Endpoint Info */}
            <div className="bg-muted/50 p-4 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="h-4 w-4" />
                <span className="font-medium">API Endpoint</span>
              </div>
              <div className="bg-background p-3 rounded border overflow-x-auto">
                <code className="text-sm whitespace-nowrap">
                  POST http://localhost:58000/api/v1/chatbot/external/{apiKeyChatbot?.id}/chat
                </code>
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                Send POST requests with your API key in the Authorization header: Bearer YOUR_API_KEY
              </p>
              <div className="mt-3 p-2 bg-blue-50 border border-blue-200 rounded">
                <p className="text-xs text-blue-700">
                  🔗 Backend API runs on port <strong>58000</strong> • Frontend runs on port 53000
                </p>
              </div>
            </div>

            {/* Create API Key Section */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium">API Keys</h3>
                <p className="text-sm text-muted-foreground">
                  Create and manage API keys for external access
                </p>
              </div>
              <Button onClick={createApiKey} disabled={loadingApiKeys}>
                <Plus className="h-4 w-4 mr-2" />
                Create API Key
              </Button>
            </div>

            {/* New API Key Display */}
            {newApiKey && (
              <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Key className="h-4 w-4 text-green-600" />
                  <span className="font-medium text-green-800">New API Key Created</span>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    value={newApiKey}
                    readOnly
                    className="font-mono text-sm flex-1 min-w-0"
                  />
                  <Button
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(newApiKey)
                      toast({
                        title: "Copied",
                        description: "API key copied to clipboard"
                      })
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-sm text-green-700 mt-2">
                  ⚠️ Save this API key now - it won't be shown again!
                </p>
                <Button
                  variant="outline" 
                  size="sm"
                  className="mt-2"
                  onClick={() => setNewApiKey(null)}
                >
                  Dismiss
                </Button>
              </div>
            )}

            {/* API Keys List */}
            {loadingApiKeys ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                <p className="mt-2 text-muted-foreground">Loading API keys...</p>
              </div>
            ) : apiKeys.length > 0 ? (
              <div className="space-y-3">
                {apiKeys.map((apiKey) => (
                  <Card key={apiKey.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{apiKey.name}</span>
                            <Badge variant={apiKey.is_active ? "default" : "secondary"}>
                              {apiKey.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </div>
                          <div className="text-sm text-muted-foreground mt-1 space-y-1">
                            <div className="font-mono text-xs bg-muted px-2 py-1 rounded w-fit">
                              {apiKey.key_prefix}
                            </div>
                            <div>
                              Created {new Date(apiKey.created_at).toLocaleDateString()} • 
                              {apiKey.total_requests} requests • 
                              Limit: {apiKey.rate_limit_per_minute}/min
                            </div>
                          </div>
                          {apiKey.last_used_at && (
                            <div className="text-xs text-muted-foreground">
                              Last used: {new Date(apiKey.last_used_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled
                          >
                            <Settings className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Key className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No API Keys</h3>
                <p className="text-muted-foreground mb-4">
                  Create your first API key to enable external access to this chatbot.
                </p>
                <Button onClick={createApiKey}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create API Key
                </Button>
              </div>
            )}

            {/* Usage Example */}
            <div className="bg-muted/50 p-4 rounded-lg">
              <h4 className="font-medium mb-2">Usage Example</h4>
              <div className="bg-background p-4 rounded border overflow-x-auto">
                <pre className="text-sm whitespace-pre-wrap break-all">
{`curl -X POST "http://localhost:58000/api/v1/chatbot/external/${apiKeyChatbot?.id}/chat" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Hello, how can you help me?",
    "conversation_id": null
  }'`}
                </pre>
              </div>
              <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded">
                <p className="text-sm text-yellow-800">
                  <strong>📌 Important:</strong> Use the backend port <code className="bg-yellow-100 px-1 rounded">:58000</code> for API calls, 
                  not the frontend port <code className="bg-yellow-100 px-1 rounded">:53000</code>
                </p>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chatbot</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingChatbot?.name}"? This will permanently 
              remove the chatbot and all its conversations. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setShowDeleteDialog(false)
              setDeletingChatbot(null)
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={deleteChatbot}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete Chatbot
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}