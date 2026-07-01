"use client"

import { useState, useEffect, useCallback } from "react"
import { apiClient } from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { Settings, Loader2 } from "lucide-react"
import { getErrorMessage } from "@/lib/extract-utils"

interface ExtractSettings {
  id: number
  default_model: string | null
  created_at: string
  updated_at: string | null
}

interface ModelInfo {
  id: string
  name: string
  provider: string
  supports_vision: boolean
}

export function ExtractSettings() {
  const { toast } = useToast()
  const [settings, setSettings] = useState<ExtractSettings | null>(null)
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [selectedModel, setSelectedModel] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const loadSettings = useCallback(async () => {
    try {
      const data = await apiClient.get<ExtractSettings>("/api-internal/v1/extract/settings")
      setSettings(data)
      // If default_model was auto-populated, use it; otherwise select first available
      if (data.default_model) {
        setSelectedModel(data.default_model)
      } else {
        // Will be set after models load
        setSelectedModel("")
      }
    } catch (error: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(error, "Failed to load settings"),
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }, [toast])

  const loadModels = useCallback(async () => {
    try {
      // Get available vision-capable models from Extract endpoint
      const response = await apiClient.get<{ models: ModelInfo[] }>("/api/v1/extract/models")
      setAvailableModels(response.models)
    } catch (error) {
      toast({
        title: "Warning",
        description: "Failed to load available models. Using platform defaults.",
        variant: "default",
      })
    }
  }, [toast])

  useEffect(() => {
    loadSettings()
    loadModels()
  }, [loadSettings, loadModels])

  const saveSettings = async () => {
    setSaving(true)
    try {
      const updated = await apiClient.put<ExtractSettings>(
        "/api-internal/v1/extract/settings",
        { default_model: selectedModel }
      )
      setSettings(updated)
      toast({
        title: "Settings Saved",
        description: "Extract settings have been updated successfully.",
      })
    } catch (error: unknown) {
      toast({
        title: "Error",
        description: getErrorMessage(error, "Failed to save settings"),
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            <CardTitle>Extract Settings</CardTitle>
          </div>
          <CardDescription>
            Configure default settings for Extract. These can be overridden per-template.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3">
            <Label htmlFor="default-model">Default Vision Model</Label>
            <p className="text-sm text-muted-foreground">
              This model will be used for all templates that don't have a specific model configured.
              Models are loaded from your configured Enclava platform providers.
            </p>
            {settings && !settings.default_model && availableModels.length > 0 && (
              <div className="text-sm text-amber-600 dark:text-amber-500">
                ⓘ Auto-selecting first available vision model: <strong>{availableModels[0].id}</strong>
              </div>
            )}
            <Select value={selectedModel} onValueChange={setSelectedModel}>
              <SelectTrigger id="default-model" className="w-full" disabled={availableModels.length === 0}>
                <SelectValue placeholder={availableModels.length === 0 ? "No vision models available - configure providers first" : "Select a vision-capable model"} />
              </SelectTrigger>
              <SelectContent>
                {availableModels.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {settings && (
            <div className="text-sm text-muted-foreground">
              <p>Last updated: {settings.updated_at ? new Date(settings.updated_at).toLocaleString() : "Never"}</p>
            </div>
          )}

          <div className="flex justify-end">
            <Button
              onClick={saveSettings}
              disabled={
                saving || !selectedModel || selectedModel === settings?.default_model
              }
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Settings
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Per-Template Model Override</CardTitle>
          <CardDescription>
            You can override the default model for specific templates in the "Manage Templates" tab.
            When editing a template, select a model to use only for that template.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Model selection priority:
          </p>
          <ol className="text-sm text-muted-foreground list-decimal list-inside mt-2 space-y-1">
            <li>Template-specific model (if set)</li>
            <li>Module default model (configured above)</li>
            <li>System fallback model</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}
