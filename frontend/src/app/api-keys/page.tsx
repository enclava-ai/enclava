"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogFooter
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Key, 
  Plus, 
  Copy, 
  Trash2, 
  Edit, 
  Eye, 
  EyeOff,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Clock,
  MoreHorizontal,
  Bot
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api-client";

interface ApiKey {
  id: string;
  name: string;
  description: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  total_requests: number;
  total_tokens: number;
  total_cost_cents: number;
  created_at: string;
  budget_id?: number;
  budget_limit?: number;
  budget_type?: "total" | "monthly";
  is_unlimited: boolean;
  allowed_models: string[];
  allowed_chatbots: string[];
}

interface Model {
  id: string;
  object: string;
  created?: number;
  owned_by?: string;
  permission?: any[];
  root?: string;
  parent?: string;
  provider?: string;
  capabilities?: string[];
  context_window?: number;
  max_output_tokens?: number;
  supports_streaming?: boolean;
  supports_function_calling?: boolean;
}

interface NewApiKeyData {
  name: string;
  description: string;
  scopes: string[];
  expires_at: string | null;
  is_unlimited: boolean;
  budget_limit_cents?: number;
  budget_type?: "total" | "monthly";
  allowed_models: string[];
  allowed_chatbots: string[];
}

const PERMISSION_OPTIONS = [
  { value: "llm:chat", label: "LLM Chat Completions" },
  { value: "llm:embeddings", label: "LLM Embeddings" },
];

export default function ApiKeysPage() {
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState<string | null>(null);
  const [showRegenerateDialog, setShowRegenerateDialog] = useState<string | null>(null);
  const [newKeyVisible, setNewKeyVisible] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [editKeyData, setEditKeyData] = useState<Partial<ApiKey>>({});
  const [availableModels, setAvailableModels] = useState<Model[]>([]);
  const [availableChatbots, setAvailableChatbots] = useState<any[]>([]);

  const [newKeyData, setNewKeyData] = useState<NewApiKeyData>({
    name: "",
    description: "",
    scopes: [],
    expires_at: null,
    is_unlimited: false,
    budget_limit_cents: 1000, // $10.00 default
    budget_type: "monthly",
    allowed_models: [],
    allowed_chatbots: [],
  });

  useEffect(() => {
    fetchApiKeys();
    fetchAvailableModels();
    fetchAvailableChatbots();
    
    // Check URL parameters for auto-opening create dialog
    const chatbotId = searchParams.get('chatbot');
    const chatbotName = searchParams.get('chatbot_name');
    const createParam = searchParams.get('create');
    
    if (chatbotId && chatbotName) {
      // Pre-populate the form with the chatbot selected and required permissions
      setNewKeyData(prev => ({
        ...prev,
        name: `${decodeURIComponent(chatbotName)} API Key`,
        allowed_chatbots: [chatbotId],
        scopes: ["llm:chat"] // Chatbots need chat completion permission
      }));
      
      // Automatically open the create dialog
      setShowCreateDialog(true);
      
      toast({
        title: "Chatbot Selected",
        description: `Creating API key for ${decodeURIComponent(chatbotName)}`
      });
    } else if (createParam === 'true') {
      // Automatically open the create dialog for general API key creation
      setShowCreateDialog(true);
    }
  }, [searchParams, toast]);

  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const result = await apiClient.get("/api-internal/v1/api-keys") as any;
      setApiKeys(result.api_keys || result.data || []);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch API keys",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableModels = async () => {
    try {
      const result = await apiClient.get("/api-internal/v1/llm/models") as any;
      setAvailableModels(result.data || []);
    } catch (error) {
      setAvailableModels([]);
    }
  };

  const fetchAvailableChatbots = async () => {
    try {
      const result = await apiClient.get("/api-internal/v1/chatbot/list") as any;
      setAvailableChatbots(result || []);
    } catch (error) {
      setAvailableChatbots([]);
    }
  };

  const handleCreateApiKey = async () => {
    try {
      setActionLoading("create");
      const data = await apiClient.post("/api-internal/v1/api-keys", newKeyData) as any;
      
      toast({
        title: "API Key Created",
        description: "Your new API key has been created successfully",
      });

      setNewKeyVisible(data.secret_key);
      setShowCreateDialog(false);
      setNewKeyData({
        name: "",
        description: "",
        scopes: [],
        expires_at: null,
        is_unlimited: false,
        budget_limit_cents: 1000, // $10.00 default
        budget_type: "monthly",
        allowed_models: [],
        allowed_chatbots: [],
      });

      await fetchApiKeys();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create API key",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleApiKey = async (keyId: string, active: boolean) => {
    try {
      setActionLoading(`toggle-${keyId}`);
      await apiClient.put(`/api-internal/v1/api-keys/${keyId}`, { is_active: active });

      toast({
        title: "API Key Updated",
        description: `API key has been ${active ? "enabled" : "disabled"}`,
      });

      await fetchApiKeys();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to update API key",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRegenerateApiKey = async (keyId: string) => {
    try {
      setActionLoading(`regenerate-${keyId}`);
      const data = await apiClient.post(`/api-internal/v1/api-keys/${keyId}/regenerate`) as any;
      
      toast({
        title: "API Key Regenerated",
        description: "Your API key has been regenerated successfully",
      });

      setNewKeyVisible(data.secret_key);
      setShowRegenerateDialog(null);
      await fetchApiKeys();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to regenerate API key",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteApiKey = async (keyId: string) => {
    if (!confirm("Are you sure you want to delete this API key? This action cannot be undone.")) {
      return;
    }

    try {
      setActionLoading(`delete-${keyId}`);
      await apiClient.delete(`/api-internal/v1/api-keys/${keyId}`);

      toast({
        title: "API Key Deleted",
        description: "API key has been deleted successfully",
      });

      await fetchApiKeys();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete API key",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleEditApiKey = async (keyId: string) => {
    try {
      setActionLoading(`edit-${keyId}`);
      await apiClient.put(`/api-internal/v1/api-keys/${keyId}`, {
        name: editKeyData.name,
        description: editKeyData.description,
        is_unlimited: editKeyData.is_unlimited,
        budget_limit_cents: editKeyData.is_unlimited ? null : editKeyData.budget_limit,
        budget_type: editKeyData.is_unlimited ? null : editKeyData.budget_type,
        expires_at: editKeyData.expires_at,
      });

      toast({
        title: "API Key Updated",
        description: "API key has been updated successfully",
      });

      setShowEditDialog(null);
      setEditKeyData({});
      await fetchApiKeys();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to update API key",
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const openEditDialog = (apiKey: ApiKey) => {
    setEditKeyData({
      name: apiKey.name,
      description: apiKey.description,
      is_unlimited: apiKey.is_unlimited,
      budget_limit: apiKey.budget_limit,
      budget_type: apiKey.budget_type || "monthly",
      expires_at: apiKey.expires_at,
    });
    setShowEditDialog(apiKey.id);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied",
      description: "API key copied to clipboard",
    });
  };

  const toggleKeyVisibility = (keyId: string) => {
    setVisibleKeys(prev => ({
      ...prev,
      [keyId]: !prev[keyId]
    }));
  };

  const getStatusBadge = (apiKey: ApiKey) => {
    if (!apiKey.is_active) {
      return <Badge variant="secondary">Disabled</Badge>;
    }
    
    if (apiKey.expires_at && new Date(apiKey.expires_at) < new Date()) {
      return <Badge variant="destructive">Expired</Badge>;
    }
    
    return <Badge variant="default">Active</Badge>;
  };

  const formatLastUsed = (lastUsed: string | null) => {
    if (!lastUsed) return "Never";
    return new Date(lastUsed).toLocaleString();
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage your API keys and access permissions
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create API Key
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New API Key</DialogTitle>
              <DialogDescription>
                Create a new API key with specific permissions and rate limits
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={newKeyData.name}
                    onChange={(e) => setNewKeyData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="API Key Name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="expires">Expires At (Optional)</Label>
                  <Input
                    id="expires"
                    type="datetime-local"
                    value={newKeyData.expires_at || ""}
                    onChange={(e) => setNewKeyData(prev => ({ ...prev, expires_at: e.target.value || null }))}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={newKeyData.description}
                  onChange={(e) => setNewKeyData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="API Key Description"
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Permissions</Label>
                <div className="grid grid-cols-2 gap-2">
                  {PERMISSION_OPTIONS.map((permission) => (
                    <div key={permission.value} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id={permission.value}
                        checked={newKeyData.scopes.includes(permission.value)}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setNewKeyData(prev => ({
                            ...prev,
                            scopes: checked
                              ? [...prev.scopes, permission.value]
                              : prev.scopes.filter(p => p !== permission.value)
                          }));
                        }}
                        className="rounded"
                      />
                      <Label htmlFor={permission.value} className="text-sm">
                        {permission.label}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Model Restrictions - Hidden for chatbot API keys since model is already selected by chatbot */}
              {newKeyData.allowed_chatbots.length === 0 && (
                <div className="space-y-2">
                  <Label>Model Restrictions (Optional)</Label>
                  <p className="text-sm text-muted-foreground mb-2">
                    Leave empty to allow all models, or select specific models to restrict access.
                  </p>
                  <div className="grid grid-cols-1 gap-2 max-h-32 overflow-y-auto border rounded-md p-2">
                    {availableModels.map((model) => (
                      <div key={model.id} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id={`model-${model.id}`}
                          checked={newKeyData.allowed_models.includes(model.id)}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setNewKeyData(prev => ({
                              ...prev,
                              allowed_models: checked
                                ? [...prev.allowed_models, model.id]
                                : prev.allowed_models.filter(m => m !== model.id)
                            }));
                          }}
                          className="rounded"
                        />
                        <Label htmlFor={`model-${model.id}`} className="text-sm">
                          {model.id}
                        </Label>
                      </div>
                    ))}
                    {availableModels.length === 0 && (
                      <p className="text-sm text-muted-foreground">No models available</p>
                    )}
                  </div>
                </div>
              )}
              

              {/* Chatbot Restrictions */}
              <div className="space-y-2">
                <Label>Chatbot Restrictions (Optional)</Label>
                <p className="text-sm text-muted-foreground mb-2">
                  Leave empty to allow all chatbots, or select specific chatbots to restrict access.
                </p>
                <div className="grid grid-cols-1 gap-2 max-h-32 overflow-y-auto border rounded-md p-2">
                  {availableChatbots.map((chatbot) => (
                    <div key={chatbot.id} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id={`chatbot-${chatbot.id}`}
                        checked={newKeyData.allowed_chatbots.includes(chatbot.id)}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setNewKeyData(prev => ({
                            ...prev,
                            allowed_chatbots: checked
                              ? [...prev.allowed_chatbots, chatbot.id]
                              : prev.allowed_chatbots.filter(c => c !== chatbot.id)
                          }));
                        }}
                        className="rounded"
                      />
                      <Label htmlFor={`chatbot-${chatbot.id}`} className="text-sm">
                        {chatbot.name}
                      </Label>
                    </div>
                  ))}
                  {availableChatbots.length === 0 && (
                    <p className="text-sm text-muted-foreground">No chatbots available</p>
                  )}
                </div>
              </div>

              {/* Budget Configuration */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="unlimited-budget"
                    checked={newKeyData.is_unlimited}
                    onChange={(e) => setNewKeyData(prev => ({ ...prev, is_unlimited: e.target.checked }))}
                    className="rounded"
                  />
                  <Label htmlFor="unlimited-budget">Set budget</Label>
                </div>

                {newKeyData.is_unlimited && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="budget-type">Budget Type</Label>
                      <Select
                        value={newKeyData.budget_type}
                        onValueChange={(value: "total" | "monthly") => setNewKeyData(prev => ({ ...prev, budget_type: value }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select budget type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="total">Total Budget</SelectItem>
                          <SelectItem value="monthly">Monthly Budget</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="budget-limit">Budget Limit ($)</Label>
                      <Input
                        id="budget-limit"
                        type="number"
                        step="0.01"
                        min="0"
                        value={(newKeyData.budget_limit_cents || 0) / 100}
                        onChange={(e) => setNewKeyData(prev => ({ 
                          ...prev, 
                          budget_limit_cents: Math.round(parseFloat(e.target.value || "0") * 100)
                        }))}
                        placeholder="0.00"
                      />
                    </div>
                  </div>
                )}
              </div>

            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowCreateDialog(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateApiKey}
                disabled={!newKeyData.name || actionLoading === "create"}
              >
                {actionLoading === "create" ? "Creating..." : "Create API Key"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* New Key Display */}
      {newKeyVisible && (
        <Alert className="mb-6">
          <Key className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <p className="font-medium">Your new API key has been created:</p>
              <div className="flex items-center space-x-2 p-2 bg-muted rounded">
                <code className="flex-1 text-sm">{newKeyVisible}</code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => copyToClipboard(newKeyVisible)}
                >
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                Make sure to copy this key now. You won't be able to see it again.
              </p>
              <Button size="sm" onClick={() => setNewKeyVisible(null)}>
                I've saved the key
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* API Keys List */}
      <div className="space-y-4">
        {apiKeys.length === 0 ? (
          <Card>
            <CardContent className="py-8">
              <div className="text-center">
                <Key className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No API keys found</h3>
                <p className="text-muted-foreground mb-4">
                  Create your first API key to start using the platform
                </p>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Create API Key
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          apiKeys.map((apiKey) => (
            <Card key={apiKey.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <Key className="h-5 w-5" />
                      <span>{apiKey.name}</span>
                      {getStatusBadge(apiKey)}
                    </CardTitle>
                    <CardDescription>{apiKey.description}</CardDescription>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={apiKey.is_active}
                      onCheckedChange={(checked) => handleToggleApiKey(apiKey.id, checked)}
                      disabled={actionLoading === `toggle-${apiKey.id}`}
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
                  <div>
                    <span className="text-sm font-medium">Key Prefix:</span>
                    <p className="text-sm text-muted-foreground font-mono">{apiKey.key_prefix}...</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium">Requests:</span>
                    <p className="text-sm text-muted-foreground">{apiKey.total_requests}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium">Tokens:</span>
                    <p className="text-sm text-muted-foreground">{apiKey.total_tokens}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium">Cost:</span>
                    <p className="text-sm text-muted-foreground">${(apiKey.total_cost_cents / 100).toFixed(2)}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium">Last Used:</span>
                    <p className="text-sm text-muted-foreground">{formatLastUsed(apiKey.last_used_at)}</p>
                  </div>
                </div>

                {/* Budget Information */}
                <div className="space-y-2 mb-4">
                  <span className="text-sm font-medium">Budget:</span>
                  <div className="flex items-center gap-2">
                    {apiKey.is_unlimited ? (
                      <Badge variant="secondary">Unlimited</Badge>
                    ) : apiKey.budget_limit ? (
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">
                          {apiKey.budget_type === "monthly" ? "Monthly" : "Total"}: ${(apiKey.budget_limit / 100).toFixed(2)}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          (${((apiKey.budget_limit - apiKey.total_cost_cents) / 100).toFixed(2)} remaining)
                        </span>
                      </div>
                    ) : (
                      <Badge variant="outline">No budget set</Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  <span className="text-sm font-medium">Scopes:</span>
                  <div className="flex flex-wrap gap-1">
                    {apiKey.scopes.map((scope) => (
                      <Badge key={scope} variant="outline" className="text-xs">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                </div>


                <div className="flex items-center space-x-2">
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => openEditDialog(apiKey)}
                    disabled={actionLoading === `edit-${apiKey.id}`}
                  >
                    <Edit className="mr-2 h-3 w-3" />
                    Edit
                  </Button>

                  <Dialog 
                    open={showRegenerateDialog === apiKey.id} 
                    onOpenChange={(open) => setShowRegenerateDialog(open ? apiKey.id : null)}
                  >
                    <DialogTrigger asChild>
                      <Button size="sm" variant="outline">
                        <RefreshCw className="mr-2 h-3 w-3" />
                        Regenerate
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Regenerate API Key</DialogTitle>
                        <DialogDescription>
                          This will generate a new API key and invalidate the current one. This action cannot be undone.
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button
                          variant="outline"
                          onClick={() => setShowRegenerateDialog(null)}
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={() => handleRegenerateApiKey(apiKey.id)}
                          disabled={actionLoading === `regenerate-${apiKey.id}`}
                        >
                          {actionLoading === `regenerate-${apiKey.id}` ? "Regenerating..." : "Regenerate"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeleteApiKey(apiKey.id)}
                    disabled={actionLoading === `delete-${apiKey.id}`}
                  >
                    <Trash2 className="mr-2 h-3 w-3" />
                    {actionLoading === `delete-${apiKey.id}` ? "Deleting..." : "Delete"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Edit API Key Dialog */}
      <Dialog open={!!showEditDialog} onOpenChange={(open) => !open && setShowEditDialog(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit API Key</DialogTitle>
            <DialogDescription>
              Update your API key settings and budget configuration
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">Name</Label>
                <Input
                  id="edit-name"
                  value={editKeyData.name || ""}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="API Key Name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-description">Description</Label>
                <Input
                  id="edit-description"
                  value={editKeyData.description || ""}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="API Key Description"
                />
              </div>
            </div>

            {/* Budget Configuration */}
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="edit-unlimited-budget"
                  checked={editKeyData.is_unlimited || false}
                  onChange={(e) => setEditKeyData(prev => ({ ...prev, is_unlimited: e.target.checked }))}
                  className="rounded"
                />
                <Label htmlFor="edit-unlimited-budget">Set budget</Label>
              </div>

              {editKeyData.is_unlimited && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="edit-budget-type">Budget Type</Label>
                    <Select
                      value={editKeyData.budget_type}
                      onValueChange={(value: "total" | "monthly") => setEditKeyData(prev => ({ ...prev, budget_type: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select budget type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="total">Total Budget</SelectItem>
                        <SelectItem value="monthly">Monthly Budget</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="edit-budget-limit">Budget Limit ($)</Label>
                    <Input
                      id="edit-budget-limit"
                      type="number"
                      step="0.01"
                      min="0"
                      value={(editKeyData.budget_limit || 0) / 100}
                      onChange={(e) => setEditKeyData(prev => ({ 
                        ...prev, 
                        budget_limit: Math.round(parseFloat(e.target.value || "0") * 100)
                      }))}
                      placeholder="0.00"
                    />
                  </div>
                </div>
              )}
            </div>


            {/* Expiration */}
            <div className="space-y-2">
              <Label htmlFor="edit-expires-at">Expiration Date (Optional)</Label>
              <Input
                id="edit-expires-at"
                type="date"
                value={editKeyData.expires_at?.split('T')[0] || ""}
                onChange={(e) => setEditKeyData(prev => ({ ...prev, expires_at: e.target.value ? `${e.target.value}T23:59:59Z` : null }))}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEditDialog(null)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => showEditDialog && handleEditApiKey(showEditDialog)}
              disabled={!editKeyData.name || actionLoading === `edit-${showEditDialog}`}
            >
              {actionLoading === `edit-${showEditDialog}` ? "Updating..." : "Update API Key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}