"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useToast } from "@/hooks/use-toast"
import { Settings, Save, RefreshCw, Phone, Bot, Zap } from "lucide-react"

interface SignalConfig {
  enabled: boolean
  signal_service: string
  signal_phone_number: string
  model: string
  temperature: number
  max_tokens: number
  memory_length: number
  command_prefix: string
  default_role: string
  auto_register: boolean
  admin_phone_numbers: string[]
  fallback_responses: string[]
  log_conversations: boolean
  connection_timeout: number
}

interface ConfigSchema {
  title: string
  properties: Record<string, any>
  required: string[]
}

export function SignalConfig() {
  const { toast } = useToast()
  const [config, setConfig] = useState<SignalConfig | null>(null)
  const [schema, setSchema] = useState<ConfigSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newAdminPhone, setNewAdminPhone] = useState("")
  const [newFallbackResponse, setNewFallbackResponse] = useState("")

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      setLoading(true)
      const response = await fetch("/api/modules/signal/config")
      
      if (!response.ok) {
        throw new Error(`Failed to fetch config: ${response.status}`)
      }

      const data = await response.json()
      setSchema(data.schema)
      
      // Set default config if none exists
      const defaultConfig: SignalConfig = {
        enabled: false,
        signal_service: "localhost:8080",
        signal_phone_number: "",
        model: "gpt-3.5-turbo",
        temperature: 0.7,
        max_tokens: 1000,
        memory_length: 10,
        command_prefix: "!",
        default_role: "disabled",
        auto_register: false,
        admin_phone_numbers: [],
        fallback_responses: [
          "I'm not sure how to help with that. Could you please rephrase your question?",
          "I don't have enough information to answer that question accurately.",
          "That's outside my knowledge area. Is there something else I can help you with?"
        ],
        log_conversations: true,
        connection_timeout: 30
      }
      
      setConfig({ ...defaultConfig, ...data.current_config })
    } catch (error) {
      console.error("Error fetching Signal config:", error)
      toast({
        title: "Error",
        description: "Failed to load Signal bot configuration",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async () => {
    if (!config) return

    try {
      setSaving(true)
      const response = await fetch("/api/modules/signal/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || "Failed to save configuration")
      }

      toast({
        title: "Success",
        description: "Signal bot configuration saved successfully"
      })
    } catch (error) {
      console.error("Error saving config:", error)
      toast({
        title: "Error", 
        description: error instanceof Error ? error.message : "Failed to save configuration",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const updateConfig = (key: keyof SignalConfig, value: any) => {
    if (!config) return
    setConfig({ ...config, [key]: value })
  }

  const addAdminPhone = () => {
    if (!config || !newAdminPhone.trim()) return
    if (!newAdminPhone.match(/^\+[1-9]\d{1,14}$/)) {
      toast({
        title: "Invalid Format",
        description: "Phone number must be in international format (e.g., +1234567890)",
        variant: "destructive"
      })
      return
    }
    updateConfig("admin_phone_numbers", [...config.admin_phone_numbers, newAdminPhone.trim()])
    setNewAdminPhone("")
  }

  const removeAdminPhone = (index: number) => {
    if (!config) return
    const phones = [...config.admin_phone_numbers]
    phones.splice(index, 1)
    updateConfig("admin_phone_numbers", phones)
  }

  const addFallbackResponse = () => {
    if (!config || !newFallbackResponse.trim()) return
    updateConfig("fallback_responses", [...config.fallback_responses, newFallbackResponse.trim()])
    setNewFallbackResponse("")
  }

  const removeFallbackResponse = (index: number) => {
    if (!config) return
    const responses = [...config.fallback_responses]
    responses.splice(index, 1)
    updateConfig("fallback_responses", responses)
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    )
  }

  if (!config || !schema) {
    return (
      <Alert>
        <AlertDescription>
          Failed to load Signal bot configuration. Please try refreshing the page.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Signal Bot Configuration</h2>
          <p className="text-muted-foreground">Configure your AI-powered Signal messaging bot</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={fetchConfig} variant="outline" disabled={loading}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={saveConfig} disabled={saving}>
            <Save className="h-4 w-4 mr-2" />
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {/* Enable/Disable Switch */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center">
                <Bot className="h-5 w-5 mr-2" />
                Signal Bot Status
              </CardTitle>
              <CardDescription>Enable or disable the Signal bot</CardDescription>
            </div>
            <Switch
              checked={config.enabled}
              onCheckedChange={(enabled) => updateConfig("enabled", enabled)}
            />
          </div>
        </CardHeader>
      </Card>

      {/* Basic Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Settings className="h-5 w-5 mr-2" />
            Basic Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="signal_service">Signal Service URL *</Label>
              <Input
                id="signal_service"
                value={config.signal_service}
                onChange={(e) => updateConfig("signal_service", e.target.value)}
                placeholder="localhost:8080"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signal_phone_number">Bot Phone Number *</Label>
              <Input
                id="signal_phone_number"
                value={config.signal_phone_number}
                onChange={(e) => updateConfig("signal_phone_number", e.target.value)}
                placeholder="+1234567890"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Zap className="h-5 w-5 mr-2" />
            AI Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="model">AI Model</Label>
              <Select value={config.model} onValueChange={(value) => updateConfig("model", value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {schema?.properties?.model?.enum ? (
                    schema.properties.model.enum.map((modelId: string) => (
                      <SelectItem key={modelId} value={modelId}>
                        {modelId}
                      </SelectItem>
                    ))
                  ) : (
                    // Fallback if schema not loaded yet
                    <>
                      <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                      <SelectItem value="gpt-4">GPT-4</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="command_prefix">Command Prefix</Label>
              <Input
                id="command_prefix"
                value={config.command_prefix}
                onChange={(e) => updateConfig("command_prefix", e.target.value)}
                placeholder="!"
                maxLength={5}
              />
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Response Creativity: {config.temperature}</Label>
              <Slider
                value={[config.temperature]}
                onValueChange={(value) => updateConfig("temperature", value[0])}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                0.0 = focused and deterministic, 1.0 = creative and diverse
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Max Response Length: {config.max_tokens}</Label>
                <Slider
                  value={[config.max_tokens]}
                  onValueChange={(value) => updateConfig("max_tokens", value[0])}
                  max={4000}
                  min={50}
                  step={50}
                  className="w-full"
                />
              </div>
              <div className="space-y-2">
                <Label>Conversation Memory: {config.memory_length}</Label>
                <Slider
                  value={[config.memory_length]}
                  onValueChange={(value) => updateConfig("memory_length", value[0])}
                  max={50}
                  min={1}
                  step={1}
                  className="w-full"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* User Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Phone className="h-5 w-5 mr-2" />
            User Management
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>Auto-Register New Users</Label>
              <p className="text-sm text-muted-foreground">
                Automatically register new Signal contacts
              </p>
            </div>
            <Switch
              checked={config.auto_register}
              onCheckedChange={(enabled) => updateConfig("auto_register", enabled)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="default_role">Default Role for New Users</Label>
            <Select value={config.default_role} onValueChange={(value) => updateConfig("default_role", value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="disabled">Disabled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Admin Phone Numbers</Label>
            <div className="flex gap-2">
              <Input
                value={newAdminPhone}
                onChange={(e) => setNewAdminPhone(e.target.value)}
                placeholder="+1234567890"
              />
              <Button onClick={addAdminPhone} variant="outline">
                Add
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {config.admin_phone_numbers.map((phone, index) => (
                <Badge key={index} variant="secondary" className="cursor-pointer" onClick={() => removeAdminPhone(index)}>
                  {phone} ×
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advanced Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Advanced Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Fallback Responses</Label>
            <div className="flex gap-2">
              <Textarea
                value={newFallbackResponse}
                onChange={(e) => setNewFallbackResponse(e.target.value)}
                placeholder="Add a fallback response..."
                rows={2}
              />
              <Button onClick={addFallbackResponse} variant="outline">
                Add
              </Button>
            </div>
            <div className="space-y-2">
              {config.fallback_responses.map((response, index) => (
                <div key={index} className="flex items-start gap-2 p-2 bg-muted rounded">
                  <span className="flex-1 text-sm">{response}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => removeFallbackResponse(index)}
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>Log Conversations</Label>
              <p className="text-sm text-muted-foreground">
                Save conversations for debugging and analytics
              </p>
            </div>
            <Switch
              checked={config.log_conversations}
              onCheckedChange={(enabled) => updateConfig("log_conversations", enabled)}
            />
          </div>

          <div className="space-y-2">
            <Label>Connection Timeout: {config.connection_timeout}s</Label>
            <Slider
              value={[config.connection_timeout]}
              onValueChange={(value) => updateConfig("connection_timeout", value[0])}
              max={120}
              min={5}
              step={5}
              className="w-full"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}