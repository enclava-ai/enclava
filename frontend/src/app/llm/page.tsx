"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
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
  DollarSign, 
  Calendar, 
  Lock, 
  Unlock,
  RefreshCw,
  AlertTriangle
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

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
  budget_limit_cents?: number
  budget_type?: string
  is_unlimited: boolean
  tags: string[]
}

interface Budget {
  id: string
  name: string
  limit_cents: number
  used_cents: number
  is_active: boolean
}

interface Model {
  id: string
  name: string
  provider: string
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
  const [budgets, setBudgets] = useState<Budget[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showSecretKeyDialog, setShowSecretKeyDialog] = useState(false)
  const [newSecretKey, setNewSecretKey] = useState('')
  const { toast } = useToast()

  // New API Key form state
  const [newKey, setNewKey] = useState({
    name: '',
    model: '',
    is_unlimited: true,
    budget_limit_cents: 1000, // $10.00 default
    budget_type: 'monthly',
    expires_at: '',
    description: ''
  })

  useEffect(() => {
    fetchData()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async () => {
    try {
      console.log('Fetching data...')
      setLoading(true)
      const token = localStorage.getItem('token')
      if (!token) {
        throw new Error('No authentication token found')
      }
      
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      }
      
      // Fetch API keys, budgets, and models
      const [keysRes, budgetsRes, modelsRes] = await Promise.all([
        fetch('/api/v1/api-keys', { headers }),
        fetch('/api/v1/llm/budget/status', { headers }),
        fetch('/api/v1/llm/models', { headers })
      ])

      console.log('API keys response status:', keysRes.status)
      if (keysRes.ok) {
        const keysData = await keysRes.json()
        console.log('API keys data:', keysData)
        setApiKeys(keysData.data || [])
        console.log('API keys state updated, count:', keysData.data?.length || 0)
      } else {
        console.error('Failed to fetch API keys:', keysRes.status)
      }

      if (budgetsRes.ok) {
        const budgetsData = await budgetsRes.json()
        setBudgets(budgetsData.data || [])
      } else {
        console.error('Failed to fetch budgets:', budgetsRes.status)
      }

      if (modelsRes.ok) {
        const modelsData = await modelsRes.json()
        setModels(modelsData.data || [])
      } else {
        console.error('Failed to fetch models:', modelsRes.status)
      }
      
      console.log('Data fetch completed successfully')
    } catch (error) {
      console.error('Error fetching data:', error)
      toast({
        title: "Error",
        description: "Failed to load data",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const createAPIKey = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/v1/api-keys', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newKey)
      })

      if (response.ok) {
        const result = await response.json()
        setNewSecretKey(result.secret_key)
        setShowCreateDialog(false)
        setShowSecretKeyDialog(true)
        setNewKey({
          name: '',
          model: '',
          is_unlimited: true,
          budget_limit_cents: 1000, // $10.00 default
          budget_type: 'monthly',
          expires_at: '',
          description: ''
        })
        fetchData()
      } else {
        throw new Error('Failed to create API key')
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create API key",
        variant: "destructive"
      })
    }
  }

  const deleteAPIKey = async (keyId: number) => {
    try {
      console.log('Deleting API key with ID:', keyId)
      setLoading(true)
      
      const token = localStorage.getItem('token')
      if (!token) {
        throw new Error('No authentication token found')
      }

      const response = await fetch(`/api/v1/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      console.log('Delete response status:', response.status)
      
      if (response.ok) {
        const responseData = await response.json()
        console.log('Delete response data:', responseData)
        
        toast({
          title: "Success",
          description: "API key deleted successfully"
        })
        
        // Force refresh data and wait for it to complete
        await fetchData()
        console.log('Data refreshed after deletion')
      } else {
        const errorData = await response.text()
        console.error('Delete failed:', response.status, errorData)
        throw new Error(`Failed to delete API key: ${response.status}`)
      }
    } catch (error) {
      console.error('Error deleting API key:', error)
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

  const handleSecretKeyAcknowledged = () => {
    setShowSecretKeyDialog(false)
    setNewSecretKey('')
    toast({
      title: "API Key Created",
      description: "Your API key has been created successfully"
    })
  }

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(4)}`
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleDateString()
  }

  const getBudgetUsagePercentage = (budget: Budget) => {
    return budget.limit_cents > 0 ? (budget.used_cents / budget.limit_cents) * 100 : 0
  }

  // Get the public API URL from the current window location
  const getPublicApiUrl = () => {
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol
      const hostname = window.location.hostname
      const port = window.location.hostname === 'localhost' ? '58000' : window.location.port || (protocol === 'https:' ? '443' : '80')
      const portSuffix = (protocol === 'https:' && port === '443') || (protocol === 'http:' && port === '80') ? '' : `:${port}`
      return `${protocol}//${hostname}${portSuffix}/v1`
    }
    return 'http://localhost:58000/v1'
  }

  const publicApiUrl = getPublicApiUrl()

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">LLM Configuration</h1>
        <p className="text-muted-foreground">
          Manage API keys, budgets, and model access for your LLM integrations.
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="budgets">Budgets</TabsTrigger>
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
                <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      Create API Key
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl">
                    <DialogHeader>
                      <DialogTitle>Create New API Key</DialogTitle>
                      <DialogDescription>
                        Create a new API key with optional model and budget restrictions.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div>
                        <Label htmlFor="name">Name</Label>
                        <Input
                          id="name"
                          value={newKey.name}
                          onChange={(e) => setNewKey(prev => ({ ...prev, name: e.target.value }))}
                          placeholder="e.g., Frontend Application"
                        />
                      </div>
                      
                      <div>
                        <Label htmlFor="description">Description (Optional)</Label>
                        <Textarea
                          id="description"
                          value={newKey.description}
                          onChange={(e) => setNewKey(prev => ({ ...prev, description: e.target.value }))}
                          placeholder="Brief description of what this key is for"
                        />
                      </div>

                      <div>
                        <Label htmlFor="model">Model Restriction (Optional)</Label>
                        <Select value={newKey.model || "all"} onValueChange={(value) => setNewKey(prev => ({ ...prev, model: value === "all" ? "" : value }))}>
                          <SelectTrigger>
                            <SelectValue placeholder="Allow all models" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All Models</SelectItem>
                            {models.map(model => (
                              <SelectItem key={model.id} value={model.id}>
                                {model.name} ({model.provider})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Switch
                          id="unlimited"
                          checked={newKey.is_unlimited}
                          onCheckedChange={(checked) => setNewKey(prev => ({ ...prev, is_unlimited: checked }))}
                        />
                        <Label htmlFor="unlimited">Unlimited budget</Label>
                      </div>

                      {!newKey.is_unlimited && (
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label htmlFor="budget-type">Budget Type</Label>
                            <Select value={newKey.budget_type} onValueChange={(value) => setNewKey(prev => ({ ...prev, budget_type: value }))}>
                              <SelectTrigger>
                                <SelectValue placeholder="Select budget type" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="total">Total Budget</SelectItem>
                                <SelectItem value="monthly">Monthly Budget</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label htmlFor="budget-limit">Budget Limit ($)</Label>
                            <Input
                              id="budget-limit"
                              type="number"
                              step="0.01"
                              min="0"
                              value={(newKey.budget_limit_cents || 0) / 100}
                              onChange={(e) => setNewKey(prev => ({ 
                                ...prev, 
                                budget_limit_cents: Math.round(parseFloat(e.target.value || "0") * 100)
                              }))}
                              placeholder="0.00"
                            />
                          </div>
                        </div>
                      )}

                      <div>
                        <Label htmlFor="expires">Expiration Date (Optional)</Label>
                        <Input
                          id="expires"
                          type="date"
                          value={newKey.expires_at}
                          onChange={(e) => setNewKey(prev => ({ ...prev, expires_at: e.target.value }))}
                        />
                      </div>

                      <div className="flex justify-end space-x-2">
                        <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                          Cancel
                        </Button>
                        <Button onClick={createAPIKey} disabled={!newKey.name}>
                          Create API Key
                        </Button>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
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
                      <TableHead>Budget</TableHead>
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
                        <TableCell>
                          {apiKey.is_unlimited ? (
                            <Badge variant="outline">Unlimited</Badge>
                          ) : (
                            <Badge variant="secondary">
                              {formatCurrency(apiKey.budget_limit_cents || 0)}
                            </Badge>
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
                            <Button variant="ghost" size="sm">
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

        <TabsContent value="budgets" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Budget Management
              </CardTitle>
              <CardDescription>
                Monitor and manage spending limits for your API keys.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {budgets.map((budget) => (
                  <div key={budget.id} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">{budget.name}</h3>
                      <Badge variant={budget.is_active ? "default" : "secondary"}>
                        {budget.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Used: {formatCurrency(budget.used_cents)}</span>
                        <span>Limit: {formatCurrency(budget.limit_cents)}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full" 
                          style={{ width: `${Math.min(getBudgetUsagePercentage(budget), 100)}%` }}
                        ></div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {getBudgetUsagePercentage(budget).toFixed(1)}% used
                      </div>
                    </div>
                  </div>
                ))}
                {budgets.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    No budgets configured. Configure budgets in the Analytics section.
                  </div>
                )}
              </div>
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
                {models.map((model) => (
                  <div key={model.id} className="border rounded-lg p-4">
                    <h3 className="font-medium">{model.name}</h3>
                    <p className="text-sm text-muted-foreground">{model.provider}</p>
                    <Badge variant="outline" className="mt-2">
                      {model.id}
                    </Badge>
                  </div>
                ))}
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

      {/* Secret Key Display Dialog */}
      <Dialog open={showSecretKeyDialog} onOpenChange={() => {}}>
        <DialogContent className="max-w-2xl" onPointerDownOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              Your API Key - Copy It Now!
            </DialogTitle>
            <DialogDescription className="text-orange-600 font-medium">
              This is the only time you'll see your complete API key. Make sure to copy it and store it securely.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-orange-500" />
                <span className="text-sm font-medium text-orange-800">Important Security Notice</span>
              </div>
              <p className="text-sm text-orange-700">
                • This API key will never be shown again after you close this dialog
                <br />
                • Store it in a secure location (password manager, secure notes, etc.)
                <br />
                • Anyone with this key can access your API - keep it confidential
                <br />
                • If you lose it, you'll need to regenerate a new one
              </p>
            </div>

            <div>
              <Label className="text-sm font-medium text-gray-700">Your API Key</Label>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 p-3 bg-gray-100 border rounded-md text-sm font-mono break-all">
                  {newSecretKey}
                </code>
                <Button
                  onClick={() => copyToClipboard(newSecretKey, "API key")}
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-1"
                >
                  <Copy className="h-4 w-4" />
                  Copy
                </Button>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-4">
              <Button 
                onClick={handleSecretKeyAcknowledged}
                className="bg-orange-600 hover:bg-orange-700"
              >
                I've Copied My API Key
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}