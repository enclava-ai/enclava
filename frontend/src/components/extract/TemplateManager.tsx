"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Plus, Edit, Trash2, RefreshCw, FileText, Wand2, Upload, Loader2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { extractApi } from "@/lib/api-client"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  type JsonValue,
  type WizardResult,
  type WizardField,
  type ModelResponse,
  getErrorMessage,
  MAX_FILE_SIZE,
} from "@/lib/extract-utils"

interface Template {
  id: string
  description: string
  system_prompt: string
  user_prompt: string
  is_default: boolean
  is_active: boolean
  output_schema?: Record<string, JsonValue>
  model?: string | null
}

interface TemplateFormData {
  id: string
  description: string
  system_prompt: string
  user_prompt: string
  model: string
}

interface ModelOption {
  id: string
  name: string
  provider: string
  capabilities: string[]
}

export function TemplateManager() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [isWizardDialogOpen, setIsWizardDialogOpen] = useState(false)
  const [wizardFile, setWizardFile] = useState<File | null>(null)
  const [wizardModel, setWizardModel] = useState<string>("")
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [wizardAnalyzing, setWizardAnalyzing] = useState(false)
  const [wizardResult, setWizardResult] = useState<WizardResult | null>(null)
  const wizardFileInputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  const [formData, setFormData] = useState<TemplateFormData>({
    id: "",
    description: "",
    system_prompt: "",
    user_prompt: "",
    model: "",
  })

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const response = await extractApi.listTemplates()
      setTemplates(response.templates || [])
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to load templates",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }, [toast])

  const loadModels = useCallback(async () => {
    setLoadingModels(true)
    try {
      const response = await extractApi.getModels()
      const models: ModelResponse[] = response.data || []

      // Filter for vision-capable models only
      const visionModels = models
        .filter((model) => model.capabilities?.includes('vision'))
        .map((model) => ({
          id: model.id,
          name: model.name || model.id,
          provider: model.provider || model.owned_by || 'unknown',
          capabilities: model.capabilities || [],
        }))

      setAvailableModels(visionModels)

      // Set default model to first available vision model
      if (visionModels.length > 0 && !wizardModel) {
        setWizardModel(visionModels[0].id)
      }
    } catch (error) {
      toast({
        title: "Warning",
        description: "Failed to load available models. Using defaults.",
        variant: "destructive",
      })
    } finally {
      setLoadingModels(false)
    }
  }, [toast, wizardModel])

  useEffect(() => {
    loadTemplates()
    loadModels()
  }, [loadTemplates, loadModels])

  const handleCreateTemplate = async () => {
    if (!formData.id || !formData.system_prompt || !formData.user_prompt) {
      toast({
        title: "Error",
        description: "Please fill in all required fields",
        variant: "destructive",
      })
      return
    }

    try {
      await extractApi.createTemplate({
        id: formData.id,
        description: formData.description || undefined,
        system_prompt: formData.system_prompt,
        user_prompt: formData.user_prompt,
        model: formData.model || undefined,
      })
      toast({
        title: "Success",
        description: "Template created successfully",
      })
      setIsCreateDialogOpen(false)
      resetForm()
      loadTemplates()
    } catch (err: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(err, "Failed to create template"),
        variant: "destructive",
      })
    }
  }

  const handleUpdateTemplate = async () => {
    if (!editingTemplate) return

    if (!formData.system_prompt || !formData.user_prompt) {
      toast({
        title: "Error",
        description: "Please fill in all required fields",
        variant: "destructive",
      })
      return
    }

    try {
      await extractApi.updateTemplate(editingTemplate.id, {
        description: formData.description,
        system_prompt: formData.system_prompt,
        user_prompt: formData.user_prompt,
        model: formData.model || null,
      })
      toast({
        title: "Success",
        description: "Template updated successfully",
      })
      setIsEditDialogOpen(false)
      setEditingTemplate(null)
      resetForm()
      loadTemplates()
    } catch (err: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(err, "Failed to update template"),
        variant: "destructive",
      })
    }
  }

  const handleDeleteTemplate = async (templateId: string) => {
    try {
      await extractApi.deleteTemplate(templateId)
      toast({
        title: "Success",
        description: "Template deleted successfully",
      })
      loadTemplates()
    } catch (err: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(err, "Failed to delete template"),
        variant: "destructive",
      })
    }
  }

  const handleResetDefaults = async () => {
    try {
      await extractApi.resetDefaults()
      toast({
        title: "Success",
        description: "Default templates have been restored",
      })
      loadTemplates()
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to reset default templates",
        variant: "destructive",
      })
    }
  }

  const openCreateDialog = () => {
    resetForm()
    setIsCreateDialogOpen(true)
  }

  const openEditDialog = (template: Template) => {
    setEditingTemplate(template)
    setFormData({
      id: template.id,
      description: template.description || "",
      system_prompt: template.system_prompt,
      user_prompt: template.user_prompt,
      model: template.model || "",
    })
    setIsEditDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      id: "",
      description: "",
      system_prompt: "",
      user_prompt: "",
      model: "",
    })
  }

  const handleWizardFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0]
    if (selectedFile) {
      // Validate file size on client side
      if (selectedFile.size > MAX_FILE_SIZE) {
        toast({
          title: "File Too Large",
          description: "Maximum file size is 10MB",
          variant: "destructive",
        })
        // Clear the input
        if (wizardFileInputRef.current) {
          wizardFileInputRef.current.value = ""
        }
        return
      }
      setWizardFile(selectedFile)
    }
  }

  const analyzeWizardDocument = async () => {
    if (!wizardFile) {
      toast({
        title: "Error",
        description: "Please select a file first",
        variant: "destructive",
      })
      return
    }

    setWizardAnalyzing(true)
    try {
      const result = await extractApi.analyzeDocumentForTemplate(wizardFile, wizardModel)
      setWizardResult(result)

      // Pre-fill form with wizard results
      if (result.template) {
        setFormData({
          id: result.template.id || "",
          description: result.template.description || "",
          system_prompt: result.template.system_prompt || "",
          user_prompt: result.template.user_prompt || "",
          model: "",
        })
      }

      toast({
        title: "Analysis Complete",
        description: `Detected ${result.analysis?.document_type || 'document'}. Review and save the template.`,
      })
    } catch (err: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(err, "Failed to analyze document"),
        variant: "destructive",
      })
    } finally {
      setWizardAnalyzing(false)
    }
  }

  const saveWizardTemplate = async () => {
    if (!formData.id || !formData.system_prompt || !formData.user_prompt) {
      toast({
        title: "Error",
        description: "Please fill in all required fields",
        variant: "destructive",
      })
      return
    }

    try {
      await extractApi.createTemplate({
        id: formData.id,
        description: formData.description || undefined,
        system_prompt: formData.system_prompt,
        user_prompt: formData.user_prompt,
        model: formData.model || undefined,
      })
      toast({
        title: "Success",
        description: "Template created successfully",
      })
      setIsWizardDialogOpen(false)
      resetWizard()
      loadTemplates()
    } catch (err: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(err, "Failed to create template"),
        variant: "destructive",
      })
    }
  }

  const resetWizard = () => {
    setWizardFile(null)
    // Reset to first available vision model
    if (availableModels.length > 0) {
      setWizardModel(availableModels[0].id)
    }
    setWizardAnalyzing(false)
    setWizardResult(null)
    resetForm()
    if (wizardFileInputRef.current) {
      wizardFileInputRef.current.value = ""
    }
  }

  const openWizardDialog = () => {
    resetWizard()
    setIsWizardDialogOpen(true)
  }

  const handleWizardFileKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      wizardFileInputRef.current?.click()
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Extraction Templates</h2>
          <p className="text-muted-foreground">
            Manage templates that define how documents are processed
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={openWizardDialog}>
            <Wand2 className="mr-2 h-4 w-4" />
            Template Wizard
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" />
                Reset Defaults
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Reset Default Templates?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will restore all default templates to their original state.
                  Any modifications to default templates will be lost.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleResetDefaults}>
                  Reset
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                New Template
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New Template</DialogTitle>
                <DialogDescription>
                  Define a new extraction template for document processing
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="create-id">Template ID *</Label>
                  <Input
                    id="create-id"
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    placeholder="e.g., custom_invoice"
                  />
                  <p className="text-xs text-muted-foreground">
                    This ID will be used as the template identifier and display name
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="create-description">Description</Label>
                  <Input
                    id="create-description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Brief description of what this template extracts"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="create-model">Vision Model Override</Label>
                  <Select
                    value={formData.model}
                    onValueChange={(value) => setFormData({ ...formData, model: value === "__default__" ? "" : value })}
                    disabled={loadingModels}
                  >
                    <SelectTrigger id="create-model">
                      <SelectValue placeholder={loadingModels ? "Loading models..." : "Use default model"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">Use default model</SelectItem>
                      {availableModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name} ({model.provider})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Override the default vision model for this template. Leave empty to use the module default.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="create-system">System Prompt *</Label>
                  <Textarea
                    id="create-system"
                    value={formData.system_prompt}
                    onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                    placeholder="System instructions for the vision model..."
                    rows={6}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="create-user">User Prompt *</Label>
                  <Textarea
                    id="create-user"
                    value={formData.user_prompt}
                    onChange={(e) => setFormData({ ...formData, user_prompt: e.target.value })}
                    placeholder="User prompt template (can use {company_name}, {currency}, etc.)..."
                    rows={6}
                  />
                  <p className="text-xs text-muted-foreground">
                    Use placeholders like {'{company_name}'}, {'{currency}'} to inject context variables
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreateTemplate}>Create Template</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Templates List */}
      {loading ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading templates...</p>
        </div>
      ) : templates.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No templates found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <Card key={template.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1">
                    <CardTitle className="text-lg">{template.id}</CardTitle>
                    <CardDescription className="text-xs">
                      {template.description}
                    </CardDescription>
                  </div>
                  {template.is_default && (
                    <Badge variant="secondary" className="ml-2">
                      Default
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditDialog(template)}
                      className="flex-1"
                    >
                      <Edit className="mr-2 h-3 w-3" />
                      Edit
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" size="sm" className="flex-1">
                          <Trash2 className="mr-2 h-3 w-3" />
                          Delete
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Template?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{template.id}"? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDeleteTemplate(template.id)}>
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Template</DialogTitle>
            <DialogDescription>
              Modify the template prompts and settings
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Template ID</Label>
              <Input value={formData.id} disabled className="bg-muted" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Description</Label>
              <Input
                id="edit-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-model">Vision Model Override</Label>
              <Select
                value={formData.model || "__default__"}
                onValueChange={(value) => setFormData({ ...formData, model: value === "__default__" ? "" : value })}
                disabled={loadingModels}
              >
                <SelectTrigger id="edit-model">
                  <SelectValue placeholder={loadingModels ? "Loading models..." : "Use default model"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">Use default model</SelectItem>
                  {availableModels.map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.name} ({model.provider})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Override the default vision model for this template. Leave empty to use the module default.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-system">System Prompt *</Label>
              <Textarea
                id="edit-system"
                value={formData.system_prompt}
                onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                rows={6}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-user">User Prompt *</Label>
              <Textarea
                id="edit-user"
                value={formData.user_prompt}
                onChange={(e) => setFormData({ ...formData, user_prompt: e.target.value })}
                rows={6}
              />
              <p className="text-xs text-muted-foreground">
                Use placeholders like {'{company_name}'}, {'{currency}'} to inject context variables
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateTemplate}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Template Wizard Dialog */}
      <Dialog open={isWizardDialogOpen} onOpenChange={setIsWizardDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Template Wizard</DialogTitle>
            <DialogDescription>
              Upload a sample document and we'll automatically generate a template for you
            </DialogDescription>
          </DialogHeader>

          {!wizardResult ? (
            <div className="space-y-4">
              <Alert>
                <Wand2 className="h-4 w-4" />
                <AlertDescription>
                  Upload an invoice, receipt, contract, or any document. Our AI will analyze it and create an extraction template tailored to your document type.
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label htmlFor="wizard-file">Sample Document</Label>
                <div
                  role="button"
                  tabIndex={0}
                  aria-label="Upload a sample document. Supported formats: PDF, JPG, PNG. Maximum size: 10MB"
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 hover:border-primary"
                  onClick={() => wizardFileInputRef.current?.click()}
                  onKeyDown={handleWizardFileKeyDown}
                >
                  <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <div className="space-y-2">
                    <p className="text-lg font-medium">
                      Upload a sample document
                    </p>
                    <p className="text-sm text-muted-foreground">
                      PDF, JPG, or PNG (max 10MB)
                    </p>
                  </div>
                  <input
                    ref={wizardFileInputRef}
                    type="file"
                    accept=".jpg,.jpeg,.png,.pdf"
                    onChange={handleWizardFileChange}
                    className="hidden"
                  />
                  <Button
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation()
                      wizardFileInputRef.current?.click()
                    }}
                    className="mt-4"
                  >
                    Select File
                  </Button>
                </div>
                {wizardFile && (
                  <p className="text-sm text-muted-foreground">
                    Selected: {wizardFile.name} ({(wizardFile.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="wizard-model">Vision Model</Label>
                <Select value={wizardModel} onValueChange={setWizardModel} disabled={loadingModels || availableModels.length === 0}>
                  <SelectTrigger id="wizard-model">
                    <SelectValue placeholder={loadingModels ? "Loading models..." : availableModels.length === 0 ? "No vision models available" : "Select a model"} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {loadingModels ? (
                    "Loading available vision models from configured providers..."
                  ) : availableModels.length === 0 ? (
                    "No vision-capable models found. Please check your provider configuration."
                  ) : (
                    "Choose the AI model to analyze your document. Models are loaded from your configured inference providers."
                  )}
                </p>
              </div>

              <Button
                onClick={analyzeWizardDocument}
                disabled={!wizardFile || wizardAnalyzing}
                className="w-full"
              >
                {wizardAnalyzing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing Document...
                  </>
                ) : (
                  <>
                    <Wand2 className="mr-2 h-4 w-4" />
                    Generate Template
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <Alert>
                <FileText className="h-4 w-4" />
                <AlertDescription>
                  <div className="font-semibold">Analysis Complete!</div>
                  Detected: {wizardResult.analysis?.document_type || 'Unknown'} document
                  {wizardResult.analysis?.fields && wizardResult.analysis.fields.length > 0 && (
                    <div className="mt-2 text-xs">
                      Identified {wizardResult.analysis.fields.length} fields to extract
                    </div>
                  )}
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label htmlFor="wizard-id">Template ID *</Label>
                <Input
                  id="wizard-id"
                  value={formData.id}
                  onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                  placeholder="e.g., custom_invoice"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="wizard-description">Description</Label>
                <Input
                  id="wizard-description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="wizard-model-override">Vision Model Override</Label>
                <Select
                  value={formData.model || "__default__"}
                  onValueChange={(value) => setFormData({ ...formData, model: value === "__default__" ? "" : value })}
                  disabled={loadingModels}
                >
                  <SelectTrigger id="wizard-model-override">
                    <SelectValue placeholder={loadingModels ? "Loading models..." : "Use default model"} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">Use default model</SelectItem>
                    {availableModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name} ({model.provider})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Override the default vision model for this template. Leave empty to use the module default.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="wizard-system">System Prompt *</Label>
                <Textarea
                  id="wizard-system"
                  value={formData.system_prompt}
                  onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                  rows={6}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="wizard-user">User Prompt *</Label>
                <Textarea
                  id="wizard-user"
                  value={formData.user_prompt}
                  onChange={(e) => setFormData({ ...formData, user_prompt: e.target.value })}
                  rows={8}
                />
              </div>

              {wizardResult.analysis?.fields && wizardResult.analysis.fields.length > 0 && (
                <details className="cursor-pointer">
                  <summary className="text-sm font-medium text-primary hover:underline">
                    View Detected Fields ({wizardResult.analysis.fields.length})
                  </summary>
                  <div className="mt-2 space-y-1 text-xs">
                    {wizardResult.analysis.fields.map((field: WizardField, idx: number) => (
                      <div key={idx} className="p-2 bg-muted rounded">
                        <span className="font-semibold">{field.name}</span> ({field.type})
                        {field.description && ` - ${field.description}`}
                      </div>
                    ))}
                  </div>
                </details>
              )}

              <div className="flex gap-2">
                <Button variant="outline" onClick={resetWizard} className="flex-1">
                  Start Over
                </Button>
                <Button onClick={saveWizardTemplate} className="flex-1">
                  Save Template
                </Button>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsWizardDialogOpen(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
