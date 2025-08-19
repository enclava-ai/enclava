"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { Download, Zap, Calculator, BarChart3, AlertCircle } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'

interface EmbeddingResult {
  text: string
  embedding: number[]
  tokens: number
  cost: number
  timestamp: Date
}

interface SessionStats {
  totalEmbeddings: number
  totalTokens: number
  totalCost: number
  avgTokensPerEmbedding: number
}

export default function EmbeddingPlayground() {
  const [text, setText] = useState('')
  const [model, setModel] = useState('text-embedding-ada-002')
  const [encodingFormat, setEncodingFormat] = useState('float')
  const [isLoading, setIsLoading] = useState(false)
  const [results, setResults] = useState<EmbeddingResult[]>([])
  const [sessionStats, setSessionStats] = useState<SessionStats>({
    totalEmbeddings: 0,
    totalTokens: 0,
    totalCost: 0,
    avgTokensPerEmbedding: 0
  })
  const [selectedResult, setSelectedResult] = useState<EmbeddingResult | null>(null)
  const [comparisonMode, setComparisonMode] = useState(false)
  const { toast } = useToast()

  const handleGenerateEmbedding = async () => {
    if (!text.trim()) {
      toast({
        title: "Error",
        description: "Please enter some text to generate embeddings",
        variant: "destructive"
      })
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch('/api/v1/llm/embeddings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          input: text,
          model: model,
          encoding_format: encodingFormat
        })
      })

      if (!response.ok) {
        throw new Error('Failed to generate embedding')
      }

      const data = await response.json()
      const embedding = data.data[0].embedding
      const tokens = data.usage.total_tokens
      const cost = calculateCost(tokens, model)

      const result: EmbeddingResult = {
        text,
        embedding,
        tokens,
        cost,
        timestamp: new Date()
      }

      setResults(prev => [result, ...prev])
      updateSessionStats(result)
      setText('')
      
      toast({
        title: "Success",
        description: `Generated ${embedding.length}D embedding (${tokens} tokens, $${cost.toFixed(4)})`
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate embedding",
        variant: "destructive"
      })
    } finally {
      setIsLoading(false)
    }
  }

  const calculateCost = (tokens: number, model: string): number => {
    const rates: { [key: string]: number } = {
      'text-embedding-ada-002': 0.0001,
      'text-embedding-3-small': 0.00002,
      'text-embedding-3-large': 0.00013
    }
    return (tokens / 1000) * (rates[model] || 0.0001)
  }

  const updateSessionStats = (result: EmbeddingResult) => {
    setSessionStats(prev => ({
      totalEmbeddings: prev.totalEmbeddings + 1,
      totalTokens: prev.totalTokens + result.tokens,
      totalCost: prev.totalCost + result.cost,
      avgTokensPerEmbedding: (prev.totalTokens + result.tokens) / (prev.totalEmbeddings + 1)
    }))
  }

  const calculateCosineSimilarity = (a: number[], b: number[]): number => {
    const dotProduct = a.reduce((sum, val, i) => sum + val * b[i], 0)
    const magnitudeA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0))
    const magnitudeB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0))
    return dotProduct / (magnitudeA * magnitudeB)
  }

  const exportResults = () => {
    const dataStr = JSON.stringify(results, null, 2)
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr)
    const exportFileDefaultName = `embeddings_${new Date().toISOString().split('T')[0]}.json`
    
    const linkElement = document.createElement('a')
    linkElement.setAttribute('href', dataUri)
    linkElement.setAttribute('download', exportFileDefaultName)
    linkElement.click()
  }

  const clearResults = () => {
    setResults([])
    setSessionStats({
      totalEmbeddings: 0,
      totalTokens: 0,
      totalCost: 0,
      avgTokensPerEmbedding: 0
    })
    setSelectedResult(null)
  }

  return (
    <div className="space-y-6">
      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Generate Embeddings
          </CardTitle>
          <CardDescription>
            Convert text into vector embeddings for semantic search and similarity analysis
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Model</label>
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text-embedding-ada-002">text-embedding-ada-002</SelectItem>
                  <SelectItem value="text-embedding-3-small">text-embedding-3-small</SelectItem>
                  <SelectItem value="text-embedding-3-large">text-embedding-3-large</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Encoding Format</label>
              <Select value={encodingFormat} onValueChange={setEncodingFormat}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="float">Float</SelectItem>
                  <SelectItem value="base64">Base64</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium mb-2 block">Text Input</label>
            <Textarea
              placeholder="Enter text to generate embeddings..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="min-h-[100px]"
            />
          </div>
          
          <div className="flex gap-2">
            <Button onClick={handleGenerateEmbedding} disabled={isLoading}>
              {isLoading ? 'Generating...' : 'Generate Embedding'}
            </Button>
            <Button variant="outline" onClick={clearResults} disabled={results.length === 0}>
              Clear Results
            </Button>
            <Button variant="outline" onClick={exportResults} disabled={results.length === 0}>
              <Download className="h-4 w-4 mr-2" />
              Export JSON
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Session Stats */}
      {sessionStats.totalEmbeddings > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Session Statistics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-2xl font-bold">{sessionStats.totalEmbeddings}</div>
                <div className="text-sm text-muted-foreground">Total Embeddings</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{sessionStats.totalTokens.toLocaleString()}</div>
                <div className="text-sm text-muted-foreground">Total Tokens</div>
              </div>
              <div>
                <div className="text-2xl font-bold">${sessionStats.totalCost.toFixed(4)}</div>
                <div className="text-sm text-muted-foreground">Total Cost</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{sessionStats.avgTokensPerEmbedding.toFixed(1)}</div>
                <div className="text-sm text-muted-foreground">Avg Tokens/Embedding</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Generated Embeddings</CardTitle>
            <CardDescription>
              Click on any embedding to view details and perform similarity analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px]">
              <div className="space-y-4">
                {results.map((result, index) => (
                  <div key={index} className="border rounded-lg p-4 hover:bg-muted/50 cursor-pointer"
                       onClick={() => setSelectedResult(result)}>
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{result.embedding.length}D</Badge>
                        <Badge variant="secondary">{result.tokens} tokens</Badge>
                        <Badge variant="outline">${result.cost.toFixed(4)}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {result.timestamp.toLocaleTimeString()}
                      </div>
                    </div>
                    <div className="text-sm mb-2 line-clamp-2">{result.text}</div>
                    <div className="text-xs text-muted-foreground font-mono">
                      [{result.embedding.slice(0, 5).map(v => v.toFixed(4)).join(', ')}...]
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Embedding Details */}
      {selectedResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              Embedding Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="font-medium mb-2">Original Text</h4>
              <p className="text-sm bg-muted p-3 rounded">{selectedResult.text}</p>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Vector Details</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="font-medium">Dimensions:</span> {selectedResult.embedding.length}
                </div>
                <div>
                  <span className="font-medium">Tokens:</span> {selectedResult.tokens}
                </div>
                <div>
                  <span className="font-medium">Cost:</span> ${selectedResult.cost.toFixed(4)}
                </div>
                <div>
                  <span className="font-medium">Magnitude:</span> {Math.sqrt(selectedResult.embedding.reduce((sum, val) => sum + val * val, 0)).toFixed(4)}
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-medium mb-2">First 10 Dimensions</h4>
              <div className="grid grid-cols-5 gap-2 text-xs font-mono">
                {selectedResult.embedding.slice(0, 10).map((val, i) => (
                  <div key={i} className="bg-muted p-2 rounded text-center">
                    <div className="text-muted-foreground">[{i}]</div>
                    <div>{val.toFixed(4)}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Similarity Analysis */}
            {results.length > 1 && (
              <div>
                <h4 className="font-medium mb-2">Similarity Analysis</h4>
                <div className="space-y-2">
                  {results.filter(r => r !== selectedResult).slice(0, 5).map((result, index) => {
                    const similarity = calculateCosineSimilarity(selectedResult.embedding, result.embedding)
                    return (
                      <div key={index} className="flex items-center gap-4">
                        <div className="flex-1">
                          <div className="text-sm line-clamp-1">{result.text}</div>
                          <div className="text-xs text-muted-foreground">
                            {result.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Progress value={similarity * 100} className="w-20" />
                          <span className="text-sm font-mono w-16 text-right">
                            {similarity.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}