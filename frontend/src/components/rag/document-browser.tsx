"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Search, FileText, Trash2, Eye, Download, Calendar, Hash, FileIcon, Filter, RefreshCw } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { apiClient } from "@/lib/api-client"
import { config } from "@/lib/config"
import { downloadFile } from "@/lib/file-download"

interface Collection {
  id: string
  name: string
}

interface Document {
  id: string
  filename: string
  original_filename: string
  file_type: string
  size: number
  created_at: string
  processed_at: string
  word_count: number
  status: 'processed' | 'processing' | 'error'
  collection_id: string
  collection_name: string
  converted_content?: string
  metadata?: {
    language?: string
    entities?: Array<{ text: string; label: string }>
    keywords?: string[]
  }
}

interface DocumentBrowserProps {
  collections: Collection[]
  selectedCollection: string | null
  onCollectionSelected: (collectionId: string | null) => void
}

export function DocumentBrowser({ collections, selectedCollection, onCollectionSelected }: DocumentBrowserProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [filterCollection, setFilterCollection] = useState(selectedCollection || "all")
  const [filterType, setFilterType] = useState("all")
  const [filterStatus, setFilterStatus] = useState("all")
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [reprocessing, setReprocessing] = useState<string | null>(null)
  const { toast } = useToast()

  useEffect(() => {
    loadDocuments()
  }, [filterCollection])

  useEffect(() => {
    // Apply client-side filters for search, type, and status
    filterDocuments()
  }, [documents, searchTerm, filterType, filterStatus])

  useEffect(() => {
    if (selectedCollection !== filterCollection) {
      setFilterCollection(selectedCollection || "all")
    }
  }, [selectedCollection])

  const loadDocuments = async () => {
    setLoading(true)
    try {
      // Build query parameters based on current filter
      const params = new URLSearchParams()
      if (filterCollection && filterCollection !== "all") {
        params.append('collection_id', filterCollection)
      }
      
      const queryString = params.toString()
      const url = queryString ? `/api-internal/v1/rag/documents?${queryString}` : '/api-internal/v1/rag/documents'
      
      const data = await apiClient.get(url)
      setDocuments(data.documents || [])
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const filterDocuments = () => {
    let filtered = [...documents]

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(doc => 
        doc.original_filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.metadata?.keywords?.some(keyword => 
          keyword.toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    }

    // Collection filter is now handled server-side
    // Type filter
    if (filterType !== "all") {
      filtered = filtered.filter(doc => doc.file_type === filterType)
    }

    // Status filter
    if (filterStatus !== "all") {
      filtered = filtered.filter(doc => doc.status === filterStatus)
    }

    setFilteredDocuments(filtered)
  }

  const handleDeleteDocument = async (documentId: string) => {
    setDeleting(documentId)
    
    try {
      await apiClient.delete(`/api-internal/v1/rag/documents/${documentId}`)
      
      setDocuments(prev => prev.filter(doc => doc.id !== documentId))
      toast({
        title: "Success",
        description: "Document deleted successfully",
      })
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete document",
        variant: "destructive",
      })
    } finally {
      setDeleting(null)
    }
  }

  const handleDownloadDocument = async (document: Document) => {
    try {
      await downloadFile(
        `/api-internal/v1/rag/documents/${document.id}/download`,
        document.original_filename
      )
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to download document",
        variant: "destructive",
      })
    }
  }

  const handleReprocessDocument = async (documentId: string) => {
    setReprocessing(documentId)

    try {
      await apiClient.post(`/api-internal/v1/rag/documents/${documentId}/reprocess`)

      // Update the document status to processing in the UI
      setDocuments(prev => prev.map(doc =>
        doc.id === documentId
          ? { ...doc, status: 'processing' as const, processed_at: new Date().toISOString() }
          : doc
      ))

      toast({
        title: "Success",
        description: "Document reprocessing started",
      })

      // Reload documents after a short delay to see status updates
      setTimeout(() => {
        loadDocuments()
      }, 2000)

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to reprocess document"
      toast({
        title: "Error",
        description: errorMessage.includes("Cannot reprocess document with status 'processed'")
          ? "Cannot reprocess documents that are already processed"
          : errorMessage,
        variant: "destructive",
      })
    } finally {
      setReprocessing(null)
    }
  }

  const formatFileSize = (bytes: number) => {
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

  const getFileTypeIcon = (fileType: string) => {
    const iconClass = "h-4 w-4"
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return <FileText className={`${iconClass} text-red-500`} />
      case 'docx':
      case 'doc':
        return <FileText className={`${iconClass} text-blue-500`} />
      case 'xlsx':
      case 'xls':
        return <FileText className={`${iconClass} text-green-500`} />
      default:
        return <FileIcon className={`${iconClass} text-gray-500`} />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants = {
      processed: 'bg-green-100 text-green-800',
      processing: 'bg-yellow-100 text-yellow-800',
      error: 'bg-red-100 text-red-800'
    }
    
    return (
      <Badge variant="secondary" className={variants[status as keyof typeof variants] || ''}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    )
  }

  // Get unique file types for filter
  const uniqueFileTypes = Array.from(new Set(documents.map(doc => doc.file_type)))

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Search & Filter Documents
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Search</label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Collection</label>
              <Select value={filterCollection} onValueChange={setFilterCollection}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Collections</SelectItem>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={collection.id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">File Type</label>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {uniqueFileTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="processed">Processed</SelectItem>
                  <SelectItem value="processing">Processing</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing {filteredDocuments.length} of {documents.length} documents
        </p>
        <Button variant="outline" size="sm" onClick={loadDocuments} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      {/* Documents List */}
      <div className="grid gap-4">
        {filteredDocuments.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-8">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Documents Found</h3>
              <p className="text-muted-foreground text-center">
                {searchTerm || filterCollection !== "all" || filterType !== "all" || filterStatus !== "all"
                  ? "Try adjusting your search criteria or filters."
                  : "Upload some documents to get started."}
              </p>
            </CardContent>
          </Card>
        ) : (
          filteredDocuments.map((document) => (
            <Card key={document.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    {getFileTypeIcon(document.file_type)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <h3 className="text-sm font-medium truncate">{document.original_filename}</h3>
                        {getStatusBadge(document.status)}
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground mb-2">
                        <span className="flex items-center gap-1">
                          <Hash className="h-3 w-3" />
                          {document.collection_name}
                        </span>
                        <span>{formatFileSize(document.size)}</span>
                        <span>{document.word_count} words</span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(document.created_at)}
                        </span>
                      </div>
                      {document.metadata?.keywords && document.metadata.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {document.metadata.keywords.slice(0, 5).map((keyword, index) => (
                            <Badge key={index} variant="outline" className="text-xs">
                              {keyword}
                            </Badge>
                          ))}
                          {document.metadata.keywords.length > 5 && (
                            <Badge variant="outline" className="text-xs">
                              +{document.metadata.keywords.length - 5} more
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-1 ml-4">
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => setSelectedDocument(document)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle>{document.original_filename}</DialogTitle>
                          <DialogDescription>
                            Document details and converted content
                          </DialogDescription>
                        </DialogHeader>
                        {selectedDocument && (
                          <div className="space-y-4">
                            <div className="grid gap-4 md:grid-cols-2">
                              <div>
                                <h4 className="font-medium mb-2">File Information</h4>
                                <div className="text-sm space-y-1">
                                  <p><span className="font-medium">Type:</span> {selectedDocument.file_type.toUpperCase()}</p>
                                  <p><span className="font-medium">Size:</span> {formatFileSize(selectedDocument.size)}</p>
                                  <p><span className="font-medium">Words:</span> {selectedDocument.word_count}</p>
                                  <p><span className="font-medium">Collection:</span> {selectedDocument.collection_name}</p>
                                </div>
                              </div>
                              <div>
                                <h4 className="font-medium mb-2">Processing Info</h4>
                                <div className="text-sm space-y-1">
                                  <div><span className="font-medium">Status:</span> {getStatusBadge(selectedDocument.status)}</div>
                                  <p><span className="font-medium">Uploaded:</span> {formatDate(selectedDocument.created_at)}</p>
                                  <p><span className="font-medium">Processed:</span> {formatDate(selectedDocument.processed_at)}</p>
                                  {selectedDocument.metadata?.language && (
                                    <p><span className="font-medium">Language:</span> {selectedDocument.metadata.language}</p>
                                  )}
                                </div>
                              </div>
                            </div>
                            
                            {selectedDocument.metadata?.entities && selectedDocument.metadata.entities.length > 0 && (
                              <div>
                                <h4 className="font-medium mb-2">Entities</h4>
                                <div className="flex flex-wrap gap-1">
                                  {selectedDocument.metadata.entities.slice(0, 10).map((entity, index) => (
                                    <Badge key={index} variant="outline" className="text-xs">
                                      {entity.text} ({entity.label})
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                            
                            {selectedDocument.converted_content && (
                              <div>
                                <h4 className="font-medium mb-2">Converted Content</h4>
                                <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-y-auto">
                                  <pre className="text-sm whitespace-pre-wrap">
                                    {selectedDocument.converted_content.substring(0, 2000)}
                                    {selectedDocument.converted_content.length > 2000 && "..."}
                                  </pre>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </DialogContent>
                    </Dialog>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => handleDownloadDocument(document)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 hover:bg-blue-100"
                      onClick={() => handleReprocessDocument(document.id)}
                      disabled={reprocessing === document.id || document.status === 'processed'}
                      title={document.status === 'processed' ? "Document already processed" : "Reprocess document"}
                    >
                      {reprocessing === document.id ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className={`h-4 w-4 ${document.status === 'processed' ? 'text-gray-400' : ''}`} />
                      )}
                    </Button>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 hover:bg-red-100"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Document</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{document.original_filename}"? This action cannot be undone and will remove the document from the collection and search index.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleDeleteDocument(document.id)}
                            className="bg-red-600 hover:bg-red-700"
                            disabled={deleting === document.id}
                          >
                            {deleting === document.id ? "Deleting..." : "Delete"}
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}