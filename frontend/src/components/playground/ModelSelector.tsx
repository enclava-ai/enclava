"use client"

import { useState, useEffect } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RefreshCw, Zap, Info, AlertCircle, CheckCircle, XCircle, Clock } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

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
  tasks?: string[]  // Added tasks field from PrivateMode API
}

interface ProviderStatus {
  provider: string
  status: 'healthy' | 'degraded' | 'unavailable'
  latency_ms?: number
  success_rate?: number
  last_check: string
  error_message?: string
  models_available: string[]
}

interface ModelSelectorProps {
  value: string
  onValueChange: (value: string) => void
  filter?: 'chat' | 'embedding' | 'all'
  className?: string
}

export default function ModelSelector({ value, onValueChange, filter = 'all', className }: ModelSelectorProps) {
  const [models, setModels] = useState<Model[]>([])
  const [providerStatus, setProviderStatus] = useState<Record<string, ProviderStatus>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  const fetchModels = async () => {
    try {
      setLoading(true)
      
      // Fetch models and provider status in parallel using API client
      const [modelsResponse, statusResponse] = await Promise.allSettled([
        apiClient.get('/api-internal/v1/llm/models'),
        apiClient.get('/api-internal/v1/llm/providers/status')
      ])
      
      // Handle models response
      if (modelsResponse.status === 'fulfilled') {
        setModels(modelsResponse.value.data || [])
      } else {
        throw new Error('Failed to fetch models')
      }
      
      // Handle provider status response (optional)
      if (statusResponse.status === 'fulfilled') {
        setProviderStatus(statusResponse.value.data || {})
      }
      
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchModels()
  }, [])

  const getProviderFromModel = (modelId: string): string => {
    // PrivateMode models have specific prefixes
    if (modelId.startsWith('privatemode-')) return 'PrivateMode.ai'
    
    // Legacy detection for other providers
    if (modelId.startsWith('gpt-') || modelId.includes('openai')) return 'OpenAI'
    if (modelId.startsWith('claude-') || modelId.includes('anthropic')) return 'Anthropic'
    if (modelId.startsWith('gemini-') || modelId.includes('google')) return 'Google'
    if (modelId.includes('cohere')) return 'Cohere'
    if (modelId.includes('mistral')) return 'Mistral'
    if (modelId.includes('llama') && !modelId.startsWith('privatemode-')) return 'Meta'
    return 'Unknown'
  }

  const getModelType = (model: Model): 'chat' | 'embedding' | 'other' => {
    // Check if model has tasks field from PrivateMode or other providers
    if (model.tasks && Array.isArray(model.tasks)) {
      // Models with "generate" task are chat models
      if (model.tasks.includes('generate')) return 'chat'
      // Models with "embed" task are embedding models  
      if (model.tasks.includes('embed') || model.tasks.includes('embedding')) return 'embedding'
    }
    
    // Fallback to ID-based detection for models without tasks field
    const modelId = model.id
    if (modelId.includes('embedding') || modelId.includes('embed')) return 'embedding'
    if (modelId.includes('whisper') || modelId.includes('speech')) return 'other'  // Audio models
    
    // PrivateMode and other chat models by ID pattern
    if (
      modelId.startsWith('privatemode-llama') ||
      modelId.startsWith('privatemode-claude') ||
      modelId.startsWith('privatemode-gpt') ||
      modelId.startsWith('privatemode-gemini') ||
      modelId.includes('text-') || 
      modelId.includes('gpt-') || 
      modelId.includes('claude-') || 
      modelId.includes('gemini-') ||
      modelId.includes('llama') ||
      modelId.includes('gemma') ||
      modelId.includes('qwen') ||
      modelId.includes('mistral') ||
      modelId.includes('command') ||
      modelId.includes('latest')
    ) return 'chat'
    
    return 'other'
  }

  const getModelCategory = (model: Model): string => {
    const type = getModelType(model)
    switch (type) {
      case 'chat': return 'Chat Completion'
      case 'embedding': return 'Text Embedding'
      case 'other': return 'Other'
      default: return 'Unknown'
    }
  }

  const filteredModels = models.filter(model => {
    if (filter === 'all') return true
    return getModelType(model) === filter
  })

  const groupedModels = filteredModels.reduce((acc, model) => {
    const provider = getProviderFromModel(model.id)
    if (!acc[provider]) acc[provider] = []
    acc[provider].push(model)
    return acc
  }, {} as Record<string, Model[]>)
  
  const getProviderStatusIcon = (provider: string) => {
    const status = providerStatus[provider.toLowerCase()]?.status || 'unknown'
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-3 w-3 text-green-500" />
      case 'degraded':
        return <Clock className="h-3 w-3 text-yellow-500" />
      case 'unavailable':
        return <XCircle className="h-3 w-3 text-red-500" />
      default:
        return <AlertCircle className="h-3 w-3 text-gray-400" />
    }
  }
  
  const getProviderStatusText = (provider: string) => {
    const status = providerStatus[provider.toLowerCase()]
    if (!status) return 'Status unknown'
    
    const latencyText = status.latency_ms ? ` (${Math.round(status.latency_ms)}ms)` : ''
    return `${status.status.charAt(0).toUpperCase() + status.status.slice(1)}${latencyText}`
  }

  const selectedModel = models.find(m => m.id === value)

  if (loading) {
    return (
      <div className={`space-y-2 ${className}`}>
        <label className="text-sm font-medium">Model</label>
        <Select disabled>
          <SelectTrigger>
            <SelectValue placeholder="Loading models..." />
          </SelectTrigger>
        </Select>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`space-y-2 ${className}`}>
        <label className="text-sm font-medium">Model</label>
        <div className="space-y-2">
          <Select disabled>
            <SelectTrigger>
              <SelectValue placeholder="Error loading models" />
            </SelectTrigger>
          </Select>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between">
              <span>{error}</span>
              <Button size="sm" variant="outline" onClick={fetchModels}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      </div>
    )
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">Model</label>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetails(!showDetails)}
          >
            <Info className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchModels}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <Select value={value || ''} onValueChange={onValueChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select a model">
            {selectedModel && (
              <div className="flex items-center gap-2">
                <span>{selectedModel.id}</span>
                <Badge variant="secondary" className="text-xs">
                  {getProviderFromModel(selectedModel.id)}
                </Badge>
              </div>
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {Object.entries(groupedModels).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="px-2 py-1.5 text-sm font-semibold text-muted-foreground flex items-center gap-2">
                {getProviderStatusIcon(provider)}
                <span>{provider}</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {getProviderStatusText(provider)}
                </span>
              </div>
              {providerModels.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  <div className="flex items-center gap-2">
                    <span>{model.id}</span>
                    <div className="flex gap-1">
                      <Badge variant="outline" className="text-xs">
                        {getModelCategory(model)}
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
                    </div>
                  </div>
                </SelectItem>
              ))}
            </div>
          ))}
        </SelectContent>
      </Select>

      {showDetails && selectedModel && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Zap className="h-4 w-4" />
              Model Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="font-medium">ID:</span>
                <div className="text-muted-foreground font-mono text-xs">{selectedModel.id}</div>
              </div>
              <div>
                <span className="font-medium">Provider:</span>
                <div className="text-muted-foreground flex items-center gap-1">
                  {getProviderStatusIcon(getProviderFromModel(selectedModel.id))}
                  {getProviderFromModel(selectedModel.id)}
                </div>
              </div>
              <div>
                <span className="font-medium">Type:</span>
                <div className="text-muted-foreground">{getModelCategory(selectedModel)}</div>
              </div>
              <div>
                <span className="font-medium">Object:</span>
                <div className="text-muted-foreground">{selectedModel.object}</div>
              </div>
            </div>
            
            {(selectedModel.context_window || selectedModel.max_output_tokens) && (
              <div className="grid grid-cols-2 gap-4">
                {selectedModel.context_window && (
                  <div>
                    <span className="font-medium">Context Window:</span>
                    <div className="text-muted-foreground">{selectedModel.context_window.toLocaleString()} tokens</div>
                  </div>
                )}
                {selectedModel.max_output_tokens && (
                  <div>
                    <span className="font-medium">Max Output:</span>
                    <div className="text-muted-foreground">{selectedModel.max_output_tokens.toLocaleString()} tokens</div>
                  </div>
                )}
              </div>
            )}
            
            {(selectedModel.supports_streaming || selectedModel.supports_function_calling) && (
              <div>
                <span className="font-medium">Capabilities:</span>
                <div className="flex gap-1 mt-1">
                  {selectedModel.supports_streaming && (
                    <Badge variant="secondary" className="text-xs">Streaming</Badge>
                  )}
                  {selectedModel.supports_function_calling && (
                    <Badge variant="secondary" className="text-xs">Function Calling</Badge>
                  )}
                  {selectedModel.capabilities?.includes('tee') && (
                    <Badge variant="outline" className="text-xs border-green-500 text-green-700">TEE Protected</Badge>
                  )}
                </div>
              </div>
            )}
            
            {selectedModel.created && (
              <div>
                <span className="font-medium">Created:</span>
                <div className="text-muted-foreground">
                  {new Date(selectedModel.created * 1000).toLocaleDateString()}
                </div>
              </div>
            )}
            
            {selectedModel.owned_by && (
              <div>
                <span className="font-medium">Owned by:</span>
                <div className="text-muted-foreground">{selectedModel.owned_by}</div>
              </div>
            )}
            
            {/* Provider Status Details */}
            {providerStatus[getProviderFromModel(selectedModel.id).toLowerCase()] && (
              <div className="border-t pt-3">
                <span className="font-medium">Provider Status:</span>
                <div className="mt-1 text-xs space-y-1">
                  {(() => {
                    const status = providerStatus[getProviderFromModel(selectedModel.id).toLowerCase()]
                    return (
                      <>
                        <div className="flex justify-between">
                          <span>Status:</span>
                          <span className={`font-medium ${
                            status.status === 'healthy' ? 'text-green-600' :
                            status.status === 'degraded' ? 'text-yellow-600' :
                            'text-red-600'
                          }`}>{status.status}</span>
                        </div>
                        {status.latency_ms && (
                          <div className="flex justify-between">
                            <span>Latency:</span>
                            <span>{Math.round(status.latency_ms)}ms</span>
                          </div>
                        )}
                        {status.success_rate && (
                          <div className="flex justify-between">
                            <span>Success Rate:</span>
                            <span>{Math.round(status.success_rate * 100)}%</span>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <span>Last Check:</span>
                          <span>{new Date(status.last_check).toLocaleTimeString()}</span>
                        </div>
                      </>
                    )
                  })()} 
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{filteredModels.length} models available</span>
        {filter !== 'all' && (
          <Badge variant="outline" className="text-xs">
            {filter} models
          </Badge>
        )}
      </div>
    </div>
  )
}