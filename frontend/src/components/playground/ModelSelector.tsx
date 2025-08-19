"use client"

import { useState, useEffect } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RefreshCw, Zap, Info, AlertCircle } from 'lucide-react'

interface Model {
  id: string
  object: string
  created?: number
  owned_by?: string
  permission?: any[]
  root?: string
  parent?: string
}

interface ModelSelectorProps {
  value: string
  onValueChange: (value: string) => void
  filter?: 'chat' | 'embedding' | 'all'
  className?: string
}

export default function ModelSelector({ value, onValueChange, filter = 'all', className }: ModelSelectorProps) {
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  const fetchModels = async () => {
    try {
      setLoading(true)
      
      // Get the auth token from localStorage
      const token = localStorage.getItem('token')
      
      const response = await fetch('/api/llm/models', {
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch models')
      }

      const data = await response.json()
      setModels(data.data || [])
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
    if (modelId.startsWith('gpt-') || modelId.includes('openai')) return 'OpenAI'
    if (modelId.startsWith('claude-') || modelId.includes('anthropic')) return 'Anthropic'
    if (modelId.startsWith('gemini-') || modelId.includes('google')) return 'Google'
    if (modelId.includes('privatemode')) return 'Privatemode.ai'
    if (modelId.includes('cohere')) return 'Cohere'
    if (modelId.includes('mistral')) return 'Mistral'
    if (modelId.includes('llama')) return 'Meta'
    return 'Unknown'
  }

  const getModelType = (modelId: string): 'chat' | 'embedding' | 'other' => {
    if (modelId.includes('embedding')) return 'embedding'
    if (modelId.includes('whisper')) return 'other'  // Audio transcription models
    if (
      modelId.includes('text-') || 
      modelId.includes('gpt-') || 
      modelId.includes('claude-') || 
      modelId.includes('gemini-') ||
      modelId.includes('privatemode-') ||
      modelId.includes('llama') ||
      modelId.includes('gemma') ||
      modelId.includes('qwen') ||
      modelId.includes('latest')
    ) return 'chat'
    return 'other'
  }

  const getModelCategory = (modelId: string): string => {
    const type = getModelType(modelId)
    switch (type) {
      case 'chat': return 'Chat Completion'
      case 'embedding': return 'Text Embedding'
      case 'other': return 'Other'
      default: return 'Unknown'
    }
  }

  const filteredModels = models.filter(model => {
    if (filter === 'all') return true
    return getModelType(model.id) === filter
  })

  const groupedModels = filteredModels.reduce((acc, model) => {
    const provider = getProviderFromModel(model.id)
    if (!acc[provider]) acc[provider] = []
    acc[provider].push(model)
    return acc
  }, {} as Record<string, Model[]>)

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

      <Select value={value ?? ''} onValueChange={onValueChange}>
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
              <div className="px-2 py-1.5 text-sm font-semibold text-muted-foreground">
                {provider}
              </div>
              {providerModels.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  <div className="flex items-center gap-2">
                    <span>{model.id}</span>
                    <Badge variant="outline" className="text-xs">
                      {getModelCategory(model.id)}
                    </Badge>
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
          <CardContent className="space-y-2 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="font-medium">ID:</span>
                <div className="text-muted-foreground font-mono text-xs">{selectedModel.id}</div>
              </div>
              <div>
                <span className="font-medium">Provider:</span>
                <div className="text-muted-foreground">{getProviderFromModel(selectedModel.id)}</div>
              </div>
              <div>
                <span className="font-medium">Type:</span>
                <div className="text-muted-foreground">{getModelCategory(selectedModel.id)}</div>
              </div>
              <div>
                <span className="font-medium">Object:</span>
                <div className="text-muted-foreground">{selectedModel.object}</div>
              </div>
            </div>
            
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