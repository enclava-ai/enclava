"use client"

import { useEffect, useState } from "react"
import { AlertCircle, CheckCircle, Database, Search, XCircle } from "lucide-react"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiClient } from "@/lib/api-client"

interface SystemStatus {
  database: string
  modules: Record<string, any>
  redis: string
  qdrant: string
  timestamp: string
}

interface RagDebugResult {
  results?: any[]
  debug_info?: Record<string, any>
  search_time_ms?: number
}

export default function DebugPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [ragQuery, setRagQuery] = useState("What is security?")
  const [ragTest, setRagTest] = useState<RagDebugResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadSystemStatus()
  }, [])

  const loadSystemStatus = async () => {
    try {
      const response = await apiClient.get("/api-internal/v1/debugging/system/status")
      setSystemStatus(response)
    } catch (error) {
      console.error("Failed to load system status:", error)
    }
  }

  const testRagSearch = async () => {
    const query = ragQuery.trim()
    if (!query) return

    setLoading(true)
    try {
      const response = await apiClient.post(
        `/api-internal/v1/rag/debug/search?query=${encodeURIComponent(query)}&max_results=10`
      )
      setRagTest(response)
    } catch (error) {
      console.error("Failed to test RAG search:", error)
      setRagTest({
        results: [],
        debug_info: { error: error instanceof Error ? error.message : "Search failed" },
        search_time_ms: 0,
      })
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    const normalized = status.toLowerCase()
    if (normalized.includes("healthy")) return <CheckCircle className="h-4 w-4 text-green-500" />
    if (normalized.includes("error")) return <XCircle className="h-4 w-4 text-red-500" />
    return <AlertCircle className="h-4 w-4 text-yellow-500" />
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Debugging Dashboard</h1>
          <p className="text-muted-foreground">Troubleshoot platform services and RAG retrieval.</p>
        </div>

        <Tabs defaultValue="system" className="space-y-6">
          <TabsList>
            <TabsTrigger value="system">System Status</TabsTrigger>
            <TabsTrigger value="rag">RAG Testing</TabsTrigger>
          </TabsList>

          <TabsContent value="system" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  System Health
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {systemStatus ? (
                  <div className="grid gap-4">
                    {[
                      ["Database", systemStatus.database],
                      ["Redis", systemStatus.redis],
                      ["Qdrant", systemStatus.qdrant],
                    ].map(([label, status]) => (
                      <div key={label} className="flex items-center justify-between rounded border p-4">
                        <span className="font-medium">{label}</span>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(status)}
                          <span className="text-sm">{status}</span>
                        </div>
                      </div>
                    ))}

                    <div className="mt-6">
                      <h4 className="font-medium mb-3">Modules</h4>
                      <div className="grid gap-2">
                        {Object.entries(systemStatus.modules).map(([name, info]: [string, any]) => (
                          <div key={name} className="flex items-center justify-between rounded border p-3">
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

          <TabsContent value="rag" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  RAG Search
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="text-sm font-medium">Query</label>
                    <Input
                      value={ragQuery}
                      onChange={(event) => setRagQuery(event.target.value)}
                      placeholder="Enter a test query..."
                      className="mt-1"
                    />
                  </div>
                  <Button onClick={testRagSearch} disabled={loading || !ragQuery.trim()}>
                    {loading ? "Searching..." : "Search"}
                  </Button>
                </div>

                {ragTest && (
                  <div className="mt-6 space-y-4">
                    <div className="rounded border p-4">
                      <h4 className="font-medium mb-2">Result Summary</h4>
                      <div className="text-sm space-y-1">
                        <div><strong>Results:</strong> {ragTest.results?.length ?? 0}</div>
                        <div><strong>Search time:</strong> {ragTest.search_time_ms ?? 0} ms</div>
                        {ragTest.debug_info?.error && (
                          <div className="text-red-500"><strong>Error:</strong> {ragTest.debug_info.error}</div>
                        )}
                      </div>
                    </div>

                    {!!ragTest.results?.length && (
                      <div>
                        <h4 className="font-medium mb-2">Matches</h4>
                        <div className="space-y-3 max-h-96 overflow-y-auto">
                          {ragTest.results.map((result, index) => (
                            <div key={index} className="rounded border p-3 text-sm">
                              <div className="flex justify-between items-start mb-2">
                                <Badge variant="outline">Score: {result.score?.toFixed?.(3) ?? "N/A"}</Badge>
                                {result.collection_name && (
                                  <Badge variant="secondary">{result.collection_name}</Badge>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground mb-1">
                                {result.metadata?.source || "Unknown source"}
                              </div>
                              <div>{result.content?.substring?.(0, 240) || result.text?.substring?.(0, 240)}</div>
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
      </div>
    </ProtectedRoute>
  )
}
