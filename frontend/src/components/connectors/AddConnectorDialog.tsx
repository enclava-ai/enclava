"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { apiClient } from "@/lib/api-client"
import { ArrowLeft, AlertCircle, Loader2 } from "lucide-react"

interface Collection {
  id: number
  name: string
}

interface AddConnectorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  collections: Collection[]
  onSuccess: () => void
}

type ConnectorType = "notion" | "github" | "slack" | "linear"
type Step = "select" | "configure"

interface ConnectorTypeInfo {
  id: ConnectorType
  icon: string
  name: string
  description: string
  authType: "oauth" | "token"
}

const CONNECTOR_TYPES: ConnectorTypeInfo[] = [
  {
    id: "notion",
    icon: "📄",
    name: "Notion",
    description: "Connect your Notion workspace to index pages and databases",
    authType: "oauth",
  },
  {
    id: "github",
    icon: "🐙",
    name: "GitHub",
    description: "Sync repositories, issues, and pull requests",
    authType: "oauth",
  },
  {
    id: "slack",
    icon: "💬",
    name: "Slack",
    description: "Index Slack messages and conversations",
    authType: "token",
  },
  {
    id: "linear",
    icon: "📐",
    name: "Linear",
    description: "Sync issues and projects from Linear",
    authType: "token",
  },
]

const SYNC_FREQUENCY_OPTIONS = [
  { value: "PT15M", label: "Every 15 minutes" },
  { value: "PT30M", label: "Every 30 minutes" },
  { value: "PT1H", label: "Every hour" },
  { value: "PT6H", label: "Every 6 hours" },
  { value: "P1D", label: "Daily" },
]

export function AddConnectorDialog({
  open,
  onOpenChange,
  collections,
  onSuccess,
}: AddConnectorDialogProps) {
  const [step, setStep] = useState<Step>("select")
  const [selectedType, setSelectedType] = useState<ConnectorType | null>(null)
  const [name, setName] = useState("")
  const [collectionId, setCollectionId] = useState<string>("")
  const [token, setToken] = useState("")
  const [syncFrequency, setSyncFrequency] = useState("PT1H")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resetForm = () => {
    setStep("select")
    setSelectedType(null)
    setName("")
    setCollectionId("")
    setToken("")
    setSyncFrequency("PT1H")
    setError(null)
    setIsSubmitting(false)
  }

  const handleClose = () => {
    resetForm()
    onOpenChange(false)
  }

  const handleTypeSelect = (type: ConnectorType) => {
    setSelectedType(type)
    setStep("configure")
    setError(null)
  }

  const handleBack = () => {
    setStep("select")
    setSelectedType(null)
    setError(null)
  }

  const validateForm = (): boolean => {
    if (!name.trim()) {
      setError("Name is required")
      return false
    }
    if (!collectionId) {
      setError("Collection is required")
      return false
    }

    const typeInfo = CONNECTOR_TYPES.find((t) => t.id === selectedType)
    if (typeInfo?.authType === "token" && !token.trim()) {
      setError(`${selectedType === "slack" ? "Bot Token" : "API Key"} is required`)
      return false
    }

    return true
  }

  const handleOAuthAuthorize = async () => {
    if (!validateForm()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await apiClient.post<{
        oauth_url: string
        state: string
      }>("/api-internal/v1/connectors/oauth/authorize", {
        connector_type: selectedType,
        name: name.trim(),
        collection_id: parseInt(collectionId, 10),
        redirect_uri: `${window.location.origin}/admin/connectors/oauth/callback`,
      })

      // Redirect to OAuth provider
      window.location.href = response.oauth_url
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to initiate OAuth flow"
      setError(errorMessage)
      setIsSubmitting(false)
    }
  }

  const handleTokenSubmit = async () => {
    if (!validateForm()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const credentials =
        selectedType === "slack" ? { bot_token: token.trim() } : { api_key: token.trim() }

      await apiClient.post("/api-internal/v1/connectors", {
        name: name.trim(),
        connector_type: selectedType,
        collection_id: parseInt(collectionId, 10),
        credentials,
        sync_frequency: syncFrequency,
      })

      onSuccess()
      handleClose()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to create connector"
      setError(errorMessage)
      setIsSubmitting(false)
    }
  }

  const selectedTypeInfo = CONNECTOR_TYPES.find((t) => t.id === selectedType)
  const isOAuth = selectedTypeInfo?.authType === "oauth"

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {step === "select" ? "Add Connector" : `Add ${selectedTypeInfo?.name} Connector`}
          </DialogTitle>
          <DialogDescription>
            {step === "select"
              ? "Select a connector type to integrate with your data sources"
              : "Configure your connector settings"}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {step === "select" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-4">
            {CONNECTOR_TYPES.map((type) => (
              <Card
                key={type.id}
                className="cursor-pointer hover:bg-accent transition-colors"
                onClick={() => handleTypeSelect(type.id)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{type.icon}</span>
                    <CardTitle className="text-lg">{type.name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription>{type.description}</CardDescription>
                  <div className="mt-2">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        type.authType === "oauth"
                          ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                          : "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
                      }`}
                    >
                      {type.authType === "oauth" ? "OAuth" : "Token"}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {step === "configure" && selectedTypeInfo && (
          <div className="space-y-4 py-4">
            <Button variant="ghost" size="sm" onClick={handleBack} className="mb-2">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">{selectedTypeInfo.icon}</span>
              <span className="font-semibold">{selectedTypeInfo.name}</span>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My Connector"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="collection">Collection</Label>
              <Select value={collectionId} onValueChange={setCollectionId}>
                <SelectTrigger id="collection">
                  <SelectValue placeholder="Select a collection" />
                </SelectTrigger>
                <SelectContent>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={String(collection.id)}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isOAuth ? (
              <div className="pt-4">
                <p className="text-sm text-muted-foreground mb-4">
                  You will be redirected to {selectedTypeInfo.name} to authorize access to your
                  data.
                </p>
                <Button
                  onClick={handleOAuthAuthorize}
                  disabled={isSubmitting}
                  className="w-full"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>Authorize with {selectedTypeInfo.name}</>
                  )}
                </Button>
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="token">
                    {selectedType === "slack" ? "Bot Token" : "API Key"}
                  </Label>
                  <Input
                    id="token"
                    type="password"
                    placeholder={
                      selectedType === "slack" ? "xoxb-..." : "lin_api_..."
                    }
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {selectedType === "slack"
                      ? "Your Slack bot token starting with xoxb-"
                      : "Your Linear API key starting with lin_api_"}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="sync-frequency">Sync Frequency</Label>
                  <Select value={syncFrequency} onValueChange={setSyncFrequency}>
                    <SelectTrigger id="sync-frequency">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYNC_FREQUENCY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  onClick={handleTokenSubmit}
                  disabled={isSubmitting}
                  className="w-full mt-4"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create Connector"
                  )}
                </Button>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
