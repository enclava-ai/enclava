"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Zap } from 'lucide-react'
import ChatPlayground from '@/components/playground/ChatPlayground'
import EmbeddingPlayground from '@/components/playground/EmbeddingPlayground'
import ModelSelector from '@/components/playground/ModelSelector'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

export default function PlaygroundPage() {
  return (
    <ProtectedRoute>
      <PlaygroundContent />
    </ProtectedRoute>
  )
}

function PlaygroundContent() {
  const [selectedModel, setSelectedModel] = useState('')
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">LLM Playground</h1>
        <p className="text-muted-foreground">
          Test and experiment with AI models in a simple interface.
        </p>
      </div>

      {/* Main Playground Interface */}
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
          {/* Model Selector moved inside */}
          <div className="mb-6">
            <label className="text-sm font-medium mb-2 block">Select Model</label>
            <ModelSelector 
              value={selectedModel}
              onValueChange={setSelectedModel}
              className="w-full max-w-md"
            />
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
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
    </div>
  )
}