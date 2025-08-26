"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Plus, Database, Upload, Search, Trash2, FileText, AlertCircle } from "lucide-react"
import { CollectionManager } from "@/components/rag/collection-manager"
import { DocumentUpload } from "@/components/rag/document-upload"
import { DocumentBrowser } from "@/components/rag/document-browser"
import { useAuth } from "@/contexts/AuthContext"
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { apiClient } from '@/lib/api-client'

interface Collection {
  id: string
  name: string
  description: string
  document_count: number
  size_bytes: number
  vector_count: number
  created_at: string
  status: 'active' | 'indexing' | 'error'
  is_managed?: boolean
  source?: 'database' | 'qdrant'
  is_active?: boolean
  updated_at?: string
}

interface CollectionStats {
  collections: {
    total: number
    active: number
  }
  documents: {
    total: number
    processing: number
    processed: number
  }
  storage: {
    total_size_bytes: number
    total_size_mb: number
  }
  vectors: {
    total: number
  }
}

export default function RAGPage() {
  return (
    <ProtectedRoute>
      <RAGPageContent />
    </ProtectedRoute>
  )
}

function RAGPageContent() {
  const { user } = useAuth()
  const [collections, setCollections] = useState<Collection[]>([])
  const [stats, setStats] = useState<CollectionStats | null>(null)
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("collections")

  useEffect(() => {
    if (user) {
      loadCollections()
      loadStats()
    }
  }, [user])

  const loadCollections = async () => {
    try {
      const data = await apiClient.get('/api-internal/v1/rag/collections')
      setCollections(data.collections || [])
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const data = await apiClient.get('/api-internal/v1/rag/stats')
      setStats(data.stats)
    } catch (error) {
    }
  }

  const handleCollectionCreated = (newCollection: Collection) => {
    setCollections(prev => [...prev, newCollection])
    loadStats()
  }

  const handleCollectionDeleted = (collectionId: string) => {
    setCollections(prev => prev.filter(c => c.id !== collectionId))
    if (selectedCollection === collectionId) {
      setSelectedCollection(null)
    }
    loadStats()
  }

  const handleDocumentUploaded = () => {
    loadCollections()
    loadStats()
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center justify-center py-8">
            <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Authentication Required</h3>
            <p className="text-muted-foreground text-center mb-4">
              Please log in to access the RAG document management system.
            </p>
            <Button asChild>
              <a href="/login">Login</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const formatBytes = (bytes: number | null | undefined) => {
    if (!bytes || bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RAG Document Management</h1>
          <p className="text-muted-foreground">
            Manage collections, upload documents, and organize your knowledge base.
          </p>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Collections</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.collections.total}</div>
              <p className="text-xs text-muted-foreground">
                {stats.collections.active} active
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Documents</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.documents.total}</div>
              <p className="text-xs text-muted-foreground">
                Across all collections
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
              <Upload className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatBytes(stats.storage.total_size_bytes)}</div>
              <p className="text-xs text-muted-foreground">
                Total indexed content
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Status</CardTitle>
              <Search className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">Healthy</div>
              <p className="text-xs text-muted-foreground">
                All systems operational
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="collections">Collections</TabsTrigger>
          <TabsTrigger value="upload">Upload Documents</TabsTrigger>
          <TabsTrigger value="browse">Browse Documents</TabsTrigger>
        </TabsList>

        <TabsContent value="collections" className="space-y-4">
          <CollectionManager 
            collections={collections}
            onCollectionCreated={handleCollectionCreated}
            onCollectionDeleted={handleCollectionDeleted}
            onCollectionSelected={setSelectedCollection}
            selectedCollection={selectedCollection}
            loading={loading}
          />
        </TabsContent>

        <TabsContent value="upload" className="space-y-4">
          <DocumentUpload 
            collections={collections}
            selectedCollection={selectedCollection}
            onDocumentUploaded={handleDocumentUploaded}
          />
        </TabsContent>

        <TabsContent value="browse" className="space-y-4">
          <DocumentBrowser 
            collections={collections}
            selectedCollection={selectedCollection}
            onCollectionSelected={setSelectedCollection}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}