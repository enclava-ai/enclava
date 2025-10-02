"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Upload, FileText, X, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { config } from "@/lib/config"
import { uploadFile } from "@/lib/file-download"

interface Collection {
  id: string
  name: string
}

interface DocumentUploadProps {
  collections: Collection[]
  selectedCollection: string | null
  onDocumentUploaded: () => void
}

interface UploadingFile {
  file: File
  progress: number
  status: 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
  id: string
}

export function DocumentUpload({ collections, selectedCollection, onDocumentUploaded }: DocumentUploadProps) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([])
  const [targetCollection, setTargetCollection] = useState(selectedCollection || "")
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  const supportedTypes = [
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md", ".html", ".json", ".csv"
  ]

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return
    
    if (!targetCollection) {
      toast({
        title: "Error",
        description: "Please select a collection first",
        variant: "destructive",
      })
      return
    }

    const newFiles: UploadingFile[] = Array.from(files).map(file => ({
      file,
      progress: 0,
      status: 'uploading',
      id: Math.random().toString(36).substr(2, 9)
    }))

    setUploadingFiles(prev => [...prev, ...newFiles])

    // Process each file
    newFiles.forEach(uploadFile => {
      uploadDocument(uploadFile)
    })
  }

  const uploadDocument = async (uploadingFile: UploadingFile) => {
    try {
      const formData = new FormData()
      formData.append('file', uploadingFile.file)
      formData.append('collection_id', targetCollection)

      // Simulate upload progress
      const updateProgress = (progress: number) => {
        setUploadingFiles(prev => 
          prev.map(f => f.id === uploadingFile.id ? { ...f, progress } : f)
        )
      }

      // Simulate progress updates
      updateProgress(10)
      await new Promise(resolve => setTimeout(resolve, 200))
      updateProgress(30)
      await new Promise(resolve => setTimeout(resolve, 200))
      updateProgress(60)

      await uploadFile(
        uploadingFile.file,
        '/api-internal/v1/rag/documents',
        (progress) => updateProgress(progress),
        { collection_id: targetCollection }
      )

      updateProgress(80)
      updateProgress(90)
      
      // Set processing status
      setUploadingFiles(prev => 
        prev.map(f => f.id === uploadingFile.id ? { ...f, status: 'processing', progress: 95 } : f)
      )

      // Simulate processing time
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Complete
      setUploadingFiles(prev => 
        prev.map(f => f.id === uploadingFile.id ? { ...f, status: 'completed', progress: 100 } : f)
      )

      toast({
        title: "Success",
        description: `${uploadingFile.file.name} uploaded successfully`,
      })

      onDocumentUploaded()

      // Remove completed file after 3 seconds
      setTimeout(() => {
        setUploadingFiles(prev => prev.filter(f => f.id !== uploadingFile.id))
      }, 3000)
    } catch (error) {
      setUploadingFiles(prev => 
        prev.map(f => f.id === uploadingFile.id ? { 
          ...f, 
          status: 'error', 
          error: error instanceof Error ? error.message : 'Upload failed' 
        } : f)
      )

      toast({
        title: "Error",
        description: `Failed to upload ${uploadingFile.file.name}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      })
    }
  }

  const removeFile = (fileId: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== fileId))
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return <FileText className="h-4 w-4" />
    }
  }

  const getStatusBadge = (status: string) => {
    const variants = {
      uploading: 'bg-blue-100 text-blue-800',
      processing: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-green-100 text-green-800',
      error: 'bg-red-100 text-red-800'
    }
    
    return (
      <Badge variant="secondary" className={variants[status as keyof typeof variants] || ''}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Upload Documents</CardTitle>
          <CardDescription>
            Add documents to your RAG collections. Supported formats: {supportedTypes.join(", ")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Collection Selection */}
          <div className="space-y-2">
            <Label htmlFor="collection">Target Collection</Label>
            <Select value={targetCollection} onValueChange={setTargetCollection}>
              <SelectTrigger>
                <SelectValue placeholder="Select a collection" />
              </SelectTrigger>
              <SelectContent>
                {collections.map((collection) => (
                  <SelectItem key={collection.id} value={collection.id}>
                    {collection.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Upload Area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragOver 
                ? 'border-primary bg-primary/5' 
                : 'border-gray-300 hover:border-gray-400'
            } ${!targetCollection ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => targetCollection && fileInputRef.current?.click()}
          >
            <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <div className="space-y-2">
              <p className="text-lg font-medium">
                {dragOver ? 'Drop files here' : 'Drop files here or click to browse'}
              </p>
              <p className="text-sm text-gray-500">
                Supports: PDF, Word, Excel, Text, Markdown, HTML, JSON, CSV
              </p>
              <p className="text-xs text-gray-400">
                Maximum file size: 10MB per file
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={supportedTypes.join(",")}
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />
          </div>

          {!targetCollection && (
            <div className="text-center text-sm text-amber-600 bg-amber-50 p-3 rounded-lg">
              <AlertCircle className="h-4 w-4 inline mr-2" />
              Please select a collection before uploading documents
            </div>
          )}
        </CardContent>
      </Card>

      {/* Upload Progress */}
      {uploadingFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Upload Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {uploadingFiles.map((file) => (
                <div key={file.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(file.status)}
                      <div>
                        <p className="text-sm font-medium">{file.file.name}</p>
                        <p className="text-xs text-gray-500">
                          {(file.file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusBadge(file.status)}
                      {file.status !== 'completed' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(file.id)}
                          className="h-8 w-8 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                  
                  {file.status !== 'error' && (
                    <Progress value={file.progress} className="mb-2" />
                  )}
                  
                  {file.error && (
                    <p className="text-sm text-red-600 mt-2">{file.error}</p>
                  )}
                  
                  {file.status === 'processing' && (
                    <p className="text-sm text-blue-600 mt-2">
                      Converting document and extracting content...
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}