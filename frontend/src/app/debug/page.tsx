"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { apiClient } from "@/lib/api-client"
import { Bug, Database, Search, CheckCircle, XCircle, AlertCircle } from "lucide-react"

interface SystemStatus {
  database: string
  modules: Record<string, any>
  redis: string
  qdrant: string
  timestamp: string
}

interface ChatbotConfig {
  chatbot: {
    id: string
    name: string
    type: string
    description: string
    created_at: string
    is_active: boolean
    conversation_count: number
  }
  prompt_template: {
    type: string | null
    system_prompt: string | null
    variables: any[]
  }
  rag_collections: any[]
  configuration: {
    max_tokens: number
    temperature: number
    streaming: boolean
    memory_config: any
  }
}

interface RagTestResult {
  query: string
  results: any[]
  collections_searched: string[]
  result_count: number
  error?: string
  message?: string
}

export default function DebugPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [chatbots, setChatbots] = useState<any[]>([])
  const [selectedChatbot, setSelectedChatbot] = useState<string>("")
  const [chatbotConfig, setChatbotConfig] = useState<ChatbotConfig | null>(null)
  const [ragQuery, setRagQuery] = useState("What is security?")
  const [ragTest, setRagTest] = useState<RagTestResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadSystemStatus()
    loadChatbots()
  }, [])

  const loadSystemStatus = async () => {
    try {
      const response = await apiClient.get("/api-internal/v1/debugging/system/status")
      setSystemStatus(response)
    } catch (error) {
      console.error("Failed to load system status:", error)
    }
  }

  const loadChatbots = async () => {
    try {
      const response = await apiClient.get("/api-internal/v1/chatbot/list")
      setChatbots(response)
      if (response.length > 0) {
        setSelectedChatbot(response[0].id)
      }
    } catch (error) {
      console.error("Failed to load chatbots:", error)
    }
  }

  const loadChatbotConfig = async (chatbotId: string) => {
    setLoading(true)
    try {
      const response = await apiClient.get(`/api-internal/v1/debugging/chatbot/${chatbotId}/config`)
      setChatbotConfig(response)
    } catch (error) {
      console.error("Failed to load chatbot config:", error)
    } finally {
      setLoading(false)
    }
  }

  const testRagSearch = async () => {
    if (!selectedChatbot) return

    setLoading(true)
    try {
      const response = await apiClient.get(
        `/api-internal/v1/debugging/chatbot/${selectedChatbot}/test-rag`,
        { params: { query: ragQuery } }
      )
      setRagTest(response)
    } catch (error) {
      console.error("Failed to test RAG search:", error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    if (status.includes("healthy")) return <CheckCircle className="h-4 w-4 text-green-500" />
    if (status.includes("error")) return <XCircle className="h-4 w-4 text-red-500" />
    return <AlertCircle className="h-4 w-4 text-yellow-500" />
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Debugging Dashboard</h1>
          <p className="text-muted-foreground">
            Troubleshoot and diagnose chatbot issues
          </p>
        </div>

        <Tabs defaultValue="system" className="space-y-6">
          <TabsList>
            <TabsTrigger value="system">System Status</TabsTrigger>
            <TabsTrigger value="chatbot">Chatbot Debug</TabsTrigger>
            <TabsTrigger value="rag">RAG Testing</TabsTrigger>
          </TabsList>

          <TabsContent value="system" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  System Health Status
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {systemStatus ? (
                  <div className="grid gap-4">
                    <div className="flex items-center justify-between p-4 border rounded">
                      <span className="font-medium">Database</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(systemStatus.database)}
                        <span className="text-sm">{systemStatus.database}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-4 border rounded">
                      <span className="font-medium">Redis</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(systemStatus.redis)}
                        <span className="text-sm">{systemStatus.redis}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-4 border rounded">
                      <span className="font-medium">Qdrant</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(systemStatus.qdrant)}
                        <span className="text-sm">{systemStatus.qdrant}</span>
                      </div>
                    </div>
                    <div className="mt-6">
                      <h4 className="font-medium mb-3">Modules Status</h4>
                      <div className="grid gap-2">
                        {Object.entries(systemStatus.modules).map(([name, info]: [string, any]) => (
                          <div key={name} className="flex items-center justify-between p-3 border rounded">
                            <span className="text-sm font-medium capitalize">{name}</span>
                            <div className="flex items-center gap-2">
                              <Badge variant={info.enabled ? "default" : "secondary"}>
                                {info.enabled ? "Enabled" : "Disabled"}
                              </Badge>
                              <Badge variant={info.status === "healthy" ? "default" : "destructive"}>
                                {info.status}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p>Loading system status...</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="chatbot" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bug className="h-5 w-5" />
                  Chatbot Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="text-sm font-medium">Select Chatbot</label>
                    <select
                      value={selectedChatbot}
                      onChange={(e) => {
                        setSelectedChatbot(e.target.value)
                        if (e.target.value) {
                          loadChatbotConfig(e.target.value)
                        }
                      }}
                      className="w-full mt-1 p-2 border rounded"
                    >
                      {chatbots.map((bot) => (
                        <option key={bot.id} value={bot.id}>
                          {bot.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    onClick={() => selectedChatbot && loadChatbotConfig(selectedChatbot)}
                    disabled={loading || !selectedChatbot}
                  >
                    Load Config
                  </Button>
                </div>

                {chatbotConfig && (
                  <div className="space-y-6 mt-6">
                    <div>
                      <h4 className="font-medium mb-2">Chatbot Info</h4>
                      <div className="p-4 border rounded space-y-2 text-sm">
                        <div><strong>Name:</strong> {chatbotConfig.chatbot.name}</div>
                        <div><strong>Type:</strong> {chatbotConfig.chatbot.type}</div>
                        <div><strong>Description:</strong> {chatbotConfig.chatbot.description}</div>
                        <div><strong>Active:</strong> {chatbotConfig.chatbot.is_active ? "Yes" : "No"}</div>
                        <div><strong>Conversations:</strong> {chatbotConfig.chatbot.conversation_count}</div>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-medium mb-2">Configuration</h4>
                      <div className="p-4 border rounded space-y-2 text-sm">
                        <div><strong>Max Tokens:</strong> {chatbotConfig.configuration.max_tokens}</div>
                        <div><strong>Temperature:</strong> {chatbotConfig.configuration.temperature}</div>
                        <div><strong>Streaming:</strong> {chatbotConfig.configuration.streaming ? "Yes" : "No"}</div>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-medium mb-2">Prompt Template</h4>
                      <div className="p-4 border rounded">
                        <div className="text-sm mb-2">
                          <strong>Type:</strong> {chatbotConfig.prompt_template.type || "None"}
                        </div>
                        {chatbotConfig.prompt_template.system_prompt && (
                          <div className="mt-3">
                            <div className="text-sm font-medium mb-1">System Prompt:</div>
                            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-40">
                              {chatbotConfig.prompt_template.system_prompt}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>

                    {chatbotConfig.rag_collections.length > 0 && (
                      <div>
                        <h4 className="font-medium mb-2">RAG Collections</h4>
                        <div className="space-y-2">
                          {chatbotConfig.rag_collections.map((collection) => (
                            <div key={collection.id} className="p-3 border rounded text-sm">
                              <div><strong>Name:</strong> {collection.name}</div>
                              <div><strong>Documents:</strong> {collection.document_count}</div>
                              <div><strong>Qdrant Collection:</strong> {collection.qdrant_collection_name}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rag" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  RAG Search Test
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="text-sm font-medium">Test Query</label>
                    <Input
                      value={ragQuery}
                      onChange={(e) => setRagQuery(e.target.value)}
                      placeholder="Enter a test query..."
                      className="mt-1"
                    />
                  </div>
                  <Button onClick={testRagSearch} disabled={loading || !selectedChatbot}>
                    Test Search
                  </Button>
                </div>

                {ragTest && (
                  <div className="mt-6 space-y-4">
                    <div className="p-4 border rounded">
                      <h4 className="font-medium mb-2">Test Results</h4>
                      <div className="text-sm space-y-1">
                        <div><strong>Query:</strong> {ragTest.query}</div>
                        <div><strong>Results Found:</strong> {ragTest.result_count}</div>
                        <div><strong>Collections Searched:</strong> {ragTest.collections_searched.join(", ")}</div>
                        {ragTest.message && (
                          <div><strong>Message:</strong> {ragTest.message}</div>
                        )}
                        {ragTest.error && (
                          <div className="text-red-500"><strong>Error:</strong> {ragTest.error}</div>
                        )}
                      </div>
                    </div>

                    {ragTest.results.length > 0 && (
                      <div>
                        <h4 className="font-medium mb-2">Search Results</h4>
                        <div className="space-y-3 max-h-96 overflow-y-auto">
                          {ragTest.results.map((result, index) => (
                            <div key={index} className="p-3 border rounded text-sm">
                              <div className="flex justify-between items-start mb-2">
                                <Badge variant="outline">Score: {result.score?.toFixed(3) || "N/A"}</Badge>
                                {result.collection_name && (
                                  <Badge variant="secondary">{result.collection_name}</Badge>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground mb-1">
                                {result.metadata?.source || "Unknown source"}
                              </div>
                              <div className="text-sm">
                                {result.content?.substring(0, 200)}
                                {result.content?.length > 200 && "..."}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="mt-8 p-4 border rounded">
          <h3 className="font-medium mb-2">How to Use This Dashboard</h3>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>• <strong>System Status:</strong> Check if all services (Database, Redis, Qdrant) are healthy</li>
            <li>• <strong>Chatbot Debug:</strong> View detailed configuration for any chatbot</li>
            <li>• <strong>RAG Testing:</strong> Test if document search is working correctly</li>
            <li>• Check browser console logs for detailed request/response debugging information</li>
          </ul>
        </div>
      </div>
    </ProtectedRoute>
  )
}