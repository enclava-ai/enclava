"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { 
  Key, 
  Plus, 
  Settings, 
  Trash2, 
  Copy,
  Calendar, 
  Lock, 
  Unlock,
  RefreshCw,
  AlertTriangle
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { useRouter } from 'next/navigation'

interface APIKey {
  id: number
  name: string
  key_prefix: string
  description?: string
  scopes: string[]
  is_active: boolean
  expires_at?: string
  created_at: string
  last_used_at?: string
  total_requests: number
  total_tokens: number
  total_cost: number
  rate_limit_per_minute?: number
  rate_limit_per_hour?: number
  rate_limit_per_day?: number
  allowed_ips: string[]
  allowed_models: string[]
  tags: string[]
}

interface Model {
  id: string
  object: string
  created?: number
  owned_by?: string
  permission?: any[]
  root?: string
  parent?: string
  provider?: string
  capabilities?: string[]
  context_window?: number
  max_output_tokens?: number
  supports_streaming?: boolean
  supports_function_calling?: boolean
}

export default function LLMPage() {
  return (
    <ProtectedRoute>
      <LLMPageContent />
    </ProtectedRoute>
  )
}

function LLMPageContent() {
  const [activeTab, setActiveTab] = useState('api-keys')
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingKey, setEditingKey] = useState<APIKey | null>(null)
  const { toast } = useToast()
  const router = useRouter()


  // Edit API Key form state
  const [editKey, setEditKey] = useState({
    name: '',
    description: '',
    is_active: true
  })

  useEffect(() => {
    fetchData()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      if (!token) {
        throw new Error('No authentication token found')
      }
      
      // Fetch API keys and models using API client
      const [keysData, modelsData] = await Promise.all([
        apiClient.get('/api-internal/v1/api-keys').catch(e => {
          return { data: [] }
        }),
        apiClient.get('/api-internal/v1/llm/models').catch(e => {
          return { data: [] }
        })
      ])

      setApiKeys(keysData.api_keys || [])
      setModels(modelsData.data || [])
      
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load data",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }


  const openEditDialog = (apiKey: APIKey) => {
    setEditingKey(apiKey)
    setEditKey({
      name: apiKey.name,
      description: apiKey.description || '',
      is_active: apiKey.is_active
    })
    setShowEditDialog(true)
  }

  const updateAPIKey = async () => {
    if (!editingKey) return
    
    try {
      await apiClient.put(`/api-internal/v1/api-keys/${editingKey.id}`, editKey)
      
      toast({
        title: "Success",
        description: "API key updated successfully"
      })
      
      setShowEditDialog(false)
      setEditingKey(null)
      fetchData()
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update API key",
        variant: "destructive"
      })
    }
  }

  const deleteAPIKey = async (keyId: number) => {
    try {
      setLoading(true)
      
      const responseData = await apiClient.delete(`/api-internal/v1/api-keys/${keyId}`)
        
      toast({
        title: "Success",
        description: "API key deleted successfully"
      })
      
      // Force refresh data and wait for it to complete
      await fetchData()
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete API key",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text: string, type: string = "API key") => {
    navigator.clipboard.writeText(text)
    toast({
      title: "Copied!",
      description: `${type} copied to clipboard`
    })
  }


  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(4)}`
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleDateString()
  }


  // Get the public API URL from the current window location
  const getPublicApiUrl = () => {
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol
      const hostname = window.location.hostname
      const port = window.location.port || (protocol === 'https:' ? '443' : '80')
      const portSuffix = (protocol === 'https:' && port === '443') || (protocol === 'http:' && port === '80') ? '' : `:${port}`
      return `${protocol}//${hostname}${portSuffix}/api/v1`
    }
    return 'http://localhost/api/v1'
  }

  const publicApiUrl = getPublicApiUrl()

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">LLM Configuration</h1>
        <p className="text-muted-foreground">
          Manage API keys and model access for your LLM integrations.
        </p>
      </div>

      {/* Public API URL Display */}
      <Card className="mb-6 border-blue-200 bg-blue-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-blue-700">
            <Settings className="h-5 w-5" />
            OpenAI-Compatible API Configuration
          </CardTitle>
          <CardDescription className="text-blue-600">
            Use this endpoint URL to configure external tools like Open WebUI, Continue.dev, or any OpenAI-compatible client.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium text-blue-700">API Base URL</Label>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 p-3 bg-white border border-blue-200 rounded-md text-sm font-mono">
                  {publicApiUrl}
                </code>
                <Button
                  onClick={() => copyToClipboard(publicApiUrl, "API URL")}
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-1 border-blue-300 text-blue-700 hover:bg-blue-100"
                >
                  <Copy className="h-4 w-4" />
                  Copy
                </Button>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="space-y-2">
                <h4 className="font-medium text-blue-700">Available Endpoints:</h4>
                <ul className="space-y-1 text-blue-600">
                  <li>• <code>GET /v1/models</code> - List available models</li>
                  <li>• <code>POST /v1/chat/completions</code> - Chat completions</li>
                  <li>• <code>POST /v1/embeddings</code> - Text embeddings</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <h4 className="font-medium text-blue-700">Configuration Example:</h4>
                <div className="bg-white border border-blue-200 rounded p-2 text-xs font-mono">
                  <div>Base URL: {publicApiUrl}</div>
                  <div>API Key: ce_your_api_key</div>
                  <div>Model: gpt-3.5-turbo</div>
                </div>
              </div>
            </div>
            
            <div className="bg-blue-100 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-blue-700">
                  <span className="font-medium">Setup Instructions:</span>
                  <br />
                  1. Copy the API Base URL above
                  <br />
                  2. Create an API key in the "API Keys" tab below
                  <br />
                  3. Use both in your OpenAI-compatible client configuration
                  <br />
                  4. Do NOT append additional paths like "/models" - clients handle this automatically
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
        </TabsList>

        <TabsContent value="api-keys" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  API Keys
                </CardTitle>
                <Button onClick={() => router.push('/api-keys?create=true')}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create API Key
                </Button>
              </div>
              <CardDescription>
                OpenAI-compatible API keys for accessing your LLM endpoints.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin mr-2" />
                  Loading...
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Key</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Usage</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeys.map((apiKey) => (
                      <TableRow key={apiKey.id}>
                        <TableCell className="font-medium">{apiKey.name}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <code className="text-sm bg-muted px-2 py-1 rounded">
                              {apiKey.key_prefix || 'N/A'}
                            </code>
                            <span className="text-xs text-muted-foreground ml-2">
                              Secret key hidden for security
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {apiKey.allowed_models && apiKey.allowed_models.length > 0 ? (
                            <Badge variant="secondary">{apiKey.allowed_models[0]}</Badge>
                          ) : (
                            <Badge variant="outline">All Models</Badge>
                          )}
                        </TableCell>
                        <TableCell>{formatDate(apiKey.expires_at)}</TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div>{apiKey.total_requests} requests</div>
                            <div className="text-muted-foreground">{formatCurrency(apiKey.total_cost)}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {apiKey.is_active ? (
                              <Badge variant="default">
                                <Unlock className="h-3 w-3 mr-1" />
                                Active
                              </Badge>
                            ) : (
                              <Badge variant="secondary">
                                <Lock className="h-3 w-3 mr-1" />
                                Inactive
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <Button variant="ghost" size="sm" onClick={() => openEditDialog(apiKey)}>
                              <Settings className="h-4 w-4" />
                            </Button>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="ghost" size="sm">
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Delete API Key</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Are you sure you want to delete this API key? This action cannot be undone.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => deleteAPIKey(apiKey.id)}>
                                    Delete
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {apiKeys.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                          No API keys created yet. Create your first API key to get started.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Available Models</CardTitle>
              <CardDescription>
                Models available through your LLM platform.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {models.map((model) => {
                  // Helper function to get provider from model ID
                  const getProviderFromModel = (modelId: string): string => {
                    if (modelId.startsWith('privatemode-')) return 'PrivateMode.ai'
                    if (modelId.startsWith('gpt-') || modelId.includes('openai')) return 'OpenAI'
                    if (modelId.startsWith('claude-') || modelId.includes('anthropic')) return 'Anthropic'
                    if (modelId.startsWith('gemini-') || modelId.includes('google')) return 'Google'
                    if (modelId.includes('cohere')) return 'Cohere'
                    if (modelId.includes('mistral')) return 'Mistral'
                    if (modelId.includes('llama') && !modelId.startsWith('privatemode-')) return 'Meta'
                    return model.owned_by || 'Unknown'
                  }
                  
                  return (
                    <div key={model.id} className="border rounded-lg p-4">
                      <h3 className="font-medium">{model.id}</h3>
                      <p className="text-sm text-muted-foreground">
                        Provider: {getProviderFromModel(model.id)}
                      </p>
                      <div className="flex gap-2 mt-2">
                        <Badge variant="outline">
                          {model.object || 'model'}
                        </Badge>
                        {model.supports_streaming && (
                          <Badge variant="secondary" className="text-xs">
                            Streaming
                          </Badge>
                        )}
                        {model.supports_function_calling && (
                          <Badge variant="secondary" className="text-xs">
                            Functions
                          </Badge>
                        )}
                        {model.capabilities?.includes('tee') && (
                          <Badge variant="outline" className="text-xs border-green-500 text-green-700">
                            TEE
                          </Badge>
                        )}
                      </div>
                      {model.context_window && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Context: {model.context_window.toLocaleString()} tokens
                        </p>
                      )}
                    </div>
                  )
                })}
                {models.length === 0 && (
                  <div className="col-span-full text-center py-8 text-muted-foreground">
                    No models available. Check your LLM platform configuration.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit API Key Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit API Key</DialogTitle>
            <DialogDescription>
              Update the name, description, and status of your API key.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={editKey.name}
                onChange={(e) => setEditKey(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., Frontend Application"
              />
            </div>
            
            <div>
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={editKey.description}
                onChange={(e) => setEditKey(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of what this key is for"
              />
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit-active"
                checked={editKey.is_active}
                onChange={(e) => setEditKey(prev => ({ ...prev, is_active: e.target.checked }))}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="edit-active" className="text-sm font-medium">
                Active (uncheck to disable this API key)
              </Label>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-blue-700">
                  <span className="font-medium">Note:</span> You cannot change the model restrictions or expiration date after creation. 
                  Create a new API key if you need different settings.
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                Cancel
              </Button>
              <Button onClick={updateAPIKey} disabled={!editKey.name.trim()}>
                Update API Key
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  )
}