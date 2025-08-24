"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Progress } from "@/components/ui/progress"
import { Plus, Database, Trash2, FileText, Calendar, AlertCircle, CheckCircle2, Clock, Settings, ExternalLink } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { apiClient } from "@/lib/api-client"

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

interface CollectionManagerProps {
  collections: Collection[]
  onCollectionCreated: (collection: Collection) => void
  onCollectionDeleted: (collectionId: string) => void
  onCollectionSelected: (collectionId: string | null) => void
  selectedCollection: string | null
  loading: boolean
}

export function CollectionManager({
  collections,
  onCollectionCreated,
  onCollectionDeleted,
  onCollectionSelected,
  selectedCollection,
  loading
}: CollectionManagerProps) {
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState("")
  const [newCollectionDescription, setNewCollectionDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const { toast } = useToast()

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'indexing':
        return <Clock className="h-4 w-4 text-yellow-500 animate-spin" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return <Database className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants = {
      active: 'bg-green-100 text-green-800',
      indexing: 'bg-yellow-100 text-yellow-800',
      error: 'bg-red-100 text-red-800'
    }
    
    return (
      <Badge variant="secondary" className={variants[status as keyof typeof variants] || ''}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    )
  }

  const getSourceBadge = (collection: Collection) => {
    if (collection.is_managed === false || collection.source === 'qdrant') {
      return (
        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
          <ExternalLink className="h-3 w-3 mr-1" />
          External
        </Badge>
      )
    }
    return null
  }

  const isExternalCollection = (collection: Collection) => {
    return collection.is_managed === false || collection.source === 'qdrant'
  }

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) {
      toast({
        title: "Error",
        description: "Collection name is required",
        variant: "destructive",
      })
      return
    }

    setCreating(true)
    
    try {
      const data = await apiClient.post('/api-internal/v1/rag/collections', {
        name: newCollectionName.trim(),
        description: newCollectionDescription.trim() || undefined,
      })
      
      onCollectionCreated(data.collection)
      setShowCreateDialog(false)
      setNewCollectionName("")
      setNewCollectionDescription("")
      toast({
        title: "Success",
        description: "Collection created successfully",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create collection",
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteCollection = async (collectionId: string) => {
    setDeleting(collectionId)
    
    try {
      await apiClient.delete(`/api-internal/v1/rag/collections/${collectionId}`)
      
      onCollectionDeleted(collectionId)
      toast({
        title: "Success",
        description: "Collection deleted successfully",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete collection",
        variant: "destructive",
      })
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Collections</h2>
          <Button disabled>
            <Plus className="h-4 w-4 mr-2" />
            Create Collection
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-4 bg-gray-300 rounded w-3/4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2"></div>
              </CardHeader>
              <CardContent>
                <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-2/3"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Collections</h2>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Collection
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Collection</DialogTitle>
              <DialogDescription>
                Create a new document collection for organizing your knowledge base.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Collection Name</Label>
                <Input
                  id="name"
                  placeholder="Enter collection name"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Enter collection description"
                  value={newCollectionDescription}
                  onChange={(e) => setNewCollectionDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateCollection} disabled={creating}>
                {creating ? "Creating..." : "Create Collection"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {collections.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-8">
            <Database className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Collections Yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first collection to start organizing your documents.
            </p>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Collection
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {collections.map((collection) => (
            <Card 
              key={collection.id} 
              className={`cursor-pointer transition-all hover:shadow-md ${
                selectedCollection === collection.id ? 'ring-2 ring-primary' : ''
              }`}
              onClick={() => onCollectionSelected(collection.id)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(collection.status)}
                    <CardTitle className="text-base">{collection.name}</CardTitle>
                  </div>
                  <div className="flex items-center space-x-1">
                    {getSourceBadge(collection)}
                    {getStatusBadge(collection.status)}
                    {!isExternalCollection(collection) && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 hover:bg-red-100"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Collection</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete "{collection.name}"? This action cannot be undone and will permanently delete all documents in this collection.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDeleteCollection(collection.id)}
                              className="bg-red-600 hover:bg-red-700"
                              disabled={deleting === collection.id}
                            >
                              {deleting === collection.id ? "Deleting..." : "Delete"}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </div>
                {collection.description && (
                  <CardDescription className="text-sm">
                    {collection.description}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Documents:</span>
                    <span className="font-medium">{collection.document_count || 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Vectors:</span>
                    <span className="font-medium">{collection.vector_count || 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Size:</span>
                    <span className="font-medium">{formatBytes(collection.size_bytes || 0)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Created:</span>
                    <span className="font-medium">{formatDate(collection.created_at)}</span>
                  </div>
                  {isExternalCollection(collection) && (
                    <div className="pt-1 border-t border-gray-100">
                      <p className="text-xs text-muted-foreground italic">
                        External collection - managed outside this system
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}