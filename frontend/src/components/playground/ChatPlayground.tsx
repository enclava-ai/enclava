"use client"

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Send, User, Bot, Settings, DollarSign } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { useToast } from '@/hooks/use-toast'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  tokens?: number
  cost?: number
}

interface ChatPlaygroundProps {
  selectedModel: string
  onRequestComplete?: () => void
}

export default function ChatPlayground({ selectedModel, onRequestComplete }: ChatPlaygroundProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [temperature, setTemperature] = useState([0.7])
  const [maxTokens, setMaxTokens] = useState(150)
  const [topP, setTopP] = useState([1])
  const [showSettings, setShowSettings] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful AI assistant.')
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      // Prepare messages for API
      const apiMessages = [
        { role: 'system', content: systemPrompt },
        ...messages.map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content: userMessage.content }
      ]

      const response = await fetch('/api/llm/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: selectedModel,
          messages: apiMessages,
          temperature: temperature[0],
          max_tokens: maxTokens,
          top_p: topP[0]
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to get response')
      }

      const data = await response.json()
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.choices[0].message.content,
        timestamp: new Date(),
        tokens: data.usage?.total_tokens,
        cost: data.usage?.total_tokens ? Math.round(data.usage.total_tokens * 0.002 * 100) : undefined // Rough estimate in cents
      }

      setMessages(prev => [...prev, assistantMessage])

      // Show budget warnings if any
      if (data.budget_warnings?.length > 0) {
        toast({
          title: "Budget Warning",
          description: data.budget_warnings.join(', '),
          variant: "destructive"
        })
      }

      // Refresh budget status
      onRequestComplete?.()

    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || 'Failed to send message',
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => {
    setMessages([])
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const formatCost = (cost?: number) => {
    if (!cost) return null
    return `$${(cost / 100).toFixed(4)}`
  }

  return (
    <div className="space-y-4">
      {/* Settings Panel */}
      <Collapsible open={showSettings} onOpenChange={setShowSettings}>
        <CollapsibleTrigger asChild>
          <Button variant="outline" className="w-full">
            <Settings className="mr-2 h-4 w-4" />
            {showSettings ? 'Hide' : 'Show'} Advanced Settings
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Model Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="system-prompt">System Prompt</Label>
                <Textarea
                  id="system-prompt"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Enter system prompt..."
                  rows={2}
                />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Temperature: {temperature[0]}</Label>
                  <Slider
                    value={temperature}
                    onValueChange={setTemperature}
                    max={2}
                    min={0}
                    step={0.1}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Max Tokens</Label>
                  <Input
                    type="number"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(parseInt(e.target.value) || 150)}
                    min={1}
                    max={4000}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Top P: {topP[0]}</Label>
                  <Slider
                    value={topP}
                    onValueChange={setTopP}
                    max={1}
                    min={0}
                    step={0.1}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* Chat Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Card className="h-[600px] flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Chat with {selectedModel}</CardTitle>
              <Button variant="outline" size="sm" onClick={clearChat}>
                Clear Chat
              </Button>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col">
              <ScrollArea className="flex-1 pr-4" ref={scrollAreaRef}>
                <div className="space-y-4">
                  {messages.length === 0 && (
                    <div className="text-center text-muted-foreground py-8">
                      Start a conversation with the AI model
                    </div>
                  )}
                  
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg p-3 ${
                          message.role === 'user'
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          {message.role === 'user' ? (
                            <User className="h-4 w-4" />
                          ) : (
                            <Bot className="h-4 w-4" />
                          )}
                          <span className="text-sm font-medium capitalize">
                            {message.role}
                          </span>
                          <span className="text-xs opacity-70">
                            {message.timestamp.toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="whitespace-pre-wrap text-sm">
                          {message.content}
                        </div>
                        {message.tokens && (
                          <div className="flex items-center gap-2 mt-2 text-xs opacity-70">
                            <Badge variant="secondary" className="text-xs">
                              {message.tokens} tokens
                            </Badge>
                            {message.cost && (
                              <Badge variant="outline" className="text-xs">
                                <DollarSign className="h-3 w-3 mr-1" />
                                {formatCost(message.cost)}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-muted rounded-lg p-3 max-w-[80%]">
                        <div className="flex items-center gap-2">
                          <Bot className="h-4 w-4" />
                          <span className="text-sm font-medium">Assistant</span>
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </div>
                        <div className="text-sm text-muted-foreground mt-2">
                          Thinking...
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
              
              <Separator className="my-4" />
              
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  className="flex-1"
                  rows={2}
                />
                <Button 
                  onClick={sendMessage} 
                  disabled={loading || !input.trim()}
                  size="lg"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Chat Statistics */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Session Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Messages</span>
                  <span>{messages.length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Total Tokens</span>
                  <span>{messages.reduce((sum, m) => sum + (m.tokens || 0), 0)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Session Cost</span>
                  <span>
                    {formatCost(messages.reduce((sum, m) => sum + (m.cost || 0), 0)) || '$0.0000'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Model Info</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Model</span>
                  <span>{selectedModel}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Temperature</span>
                  <span>{temperature[0]}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Max Tokens</span>
                  <span>{maxTokens}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}