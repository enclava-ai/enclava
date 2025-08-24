/**
 * Plugin Configuration Dialog - Configuration interface for plugins
 */
"use client"

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter 
} from '@/components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Settings, 
  Save, 
  RotateCw, 
  AlertCircle, 
  CheckCircle,
  Info,
  Eye,
  EyeOff
} from 'lucide-react';
import { usePlugin, type PluginInfo, type PluginConfiguration } from '../../contexts/PluginContext';
import { apiClient } from '@/lib/api-client';

interface PluginConfigurationDialogProps {
  plugin: PluginInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface FormField {
  key: string;
  type: string;
  label: string;
  description?: string;
  required?: boolean;
  default?: any;
  options?: string[] | { value: string; label: string }[];
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}

export const PluginConfigurationDialog: React.FC<PluginConfigurationDialogProps> = ({
  plugin,
  open,
  onOpenChange
}) => {
  const { 
    getPluginConfiguration, 
    savePluginConfiguration, 
    getPluginSchema,
    pluginConfigurations 
  } = usePlugin();

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [schema, setSchema] = useState<any>(null);
  const [config, setConfig] = useState<Record<string, any>>({});
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [testingConnection, setTestingConnection] = useState(false);
  const [testingCredentials, setTestingCredentials] = useState(false);
  const [credentialsTestResult, setCredentialsTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [showApiToken, setShowApiToken] = useState(false);

  // Load configuration and schema when dialog opens
  useEffect(() => {
    if (open && plugin.id) {
      loadPluginData();
    }
  }, [open, plugin.id]);

  // Reset success message after 5 seconds (extended for better visibility)
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const loadPluginData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Load schema and current configuration
      const [schemaData, configData] = await Promise.all([
        getPluginSchema(plugin.id),
        getPluginConfiguration(plugin.id)
      ]);

      setSchema(schemaData);
      setConfig(configData?.configuration || {});

      // Initialize form values with current config or defaults
      const initialValues: Record<string, any> = {};
      if (schemaData?.properties) {
        Object.entries(schemaData.properties).forEach(([key, field]: [string, any]) => {
          initialValues[key] = configData?.configuration?.[key] ?? field.default ?? '';
        });
      }
      setFormValues(initialValues);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      // Prepare config data - if API token is empty and we have existing config, preserve existing token
      const configToSave = { ...formValues };
      
      // If api_token is empty/missing and we have existing config with a token, preserve it
      if ((!configToSave.api_token || configToSave.api_token.trim() === '') && config.api_token) {
        configToSave.api_token = config.api_token; // Keep existing token
      }
      
      const success = await savePluginConfiguration(plugin.id, configToSave);
      
      if (success) {
        setConfig(configToSave);
        setSuccess(true);
        
        // Auto-close dialog after successful save (after a brief delay to show success message)
        setTimeout(() => {
          onOpenChange(false);
        }, 2000);
      } else {
        setError('Failed to save configuration');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to save configuration';
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleFieldChange = (key: string, value: any) => {
    setFormValues(prev => ({ ...prev, [key]: value }));
    setSuccess(false); // Clear success message when editing
  };

  const shouldShowField = (key: string, field: any) => {
    // Check if field has conditional visibility
    if (field.depends_on) {
      const dependsOnField = field.depends_on.field;
      const dependsOnValue = field.depends_on.value;
      const currentValue = formValues[dependsOnField];
      
      return currentValue === dependsOnValue;
    }
    return true;
  };

  const handleTestConnection = async () => {
    if (!schema?.validation?.connection_test) return;
    
    const testConfig = schema.validation.connection_test;
    const testData: Record<string, any> = {};
    
    // Collect required fields for testing
    testConfig.fields.forEach((fieldKey: string) => {
      testData[fieldKey] = formValues[fieldKey];
    });
    
    setTestingConnection(true);
    setError(null);
    
    try {
      let result;
      if (testConfig.method === 'GET') {
        result = await apiClient.get(testConfig.endpoint);
      } else if (testConfig.method === 'POST') {
        result = await apiClient.post(testConfig.endpoint, testData);
      } else if (testConfig.method === 'PUT') {
        result = await apiClient.put(testConfig.endpoint, testData);
      } else {
        throw new Error(`Unsupported method: ${testConfig.method}`);
      }
      
      if (result.status === 'success') {
        setSuccess(true);
        setError(null);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        setError(result.message || testConfig.error_field || 'Connection test failed');
      }
    } catch (err) {
      setError(`Connection test error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setTestingConnection(false);
    }
  };

  const handleTestCredentials = async () => {
    if (!formValues.zammad_url || !formValues.api_token) {
      setCredentialsTestResult({
        success: false,
        message: 'Please provide both Zammad URL and API Token'
      });
      return;
    }

    setTestingCredentials(true);
    setCredentialsTestResult(null);

    try {
      // Test credentials using Zammad API test endpoint
      const result = await apiClient.post(`/api-internal/v1/plugins/${plugin.id}/test-credentials`, {
        zammad_url: formValues.zammad_url,
        api_token: formValues.api_token
      });

      if (result.success) {
        setCredentialsTestResult({
          success: true,
          message: result.message || 'Credentials verified successfully!'
        });
        // Auto-hide success message after 3 seconds
        setTimeout(() => setCredentialsTestResult(null), 3000);
      } else {
        setCredentialsTestResult({
          success: false,
          message: result.message || result.error || 'Credential test failed'
        });
      }
    } catch (err) {
      setCredentialsTestResult({
        success: false,
        message: `Test failed: ${err instanceof Error ? err.message : 'Network error'}`
      });
    } finally {
      setTestingCredentials(false);
    }
  };

  const renderNestedField = (fieldId: string, key: string, field: any, value: any, onChange: (value: any) => void) => {
    const fieldType = field.type || 'string';
    
    switch (fieldType) {
      case 'boolean':
        return (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <Switch
                id={fieldId}
                checked={Boolean(value)}
                onCheckedChange={onChange}
              />
              <Label htmlFor={fieldId} className="text-sm font-medium">
                {field.title || field.label || key}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
            </div>
            {field.description && (
              <p className="text-xs text-muted-foreground ml-6">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'select':
      case 'enum':
        return (
          <div className="space-y-2">
            <Label htmlFor={fieldId} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Select value={String(value || '')} onValueChange={onChange}>
              <SelectTrigger>
                <SelectValue placeholder={field.placeholder || `Select ${field.title || key}`} />
              </SelectTrigger>
              <SelectContent>
                {(field.enum || field.options || []).map((option: any) => {
                  const optionValue = typeof option === 'object' ? option.value : option;
                  const optionLabel = typeof option === 'object' ? option.label : option;
                  return (
                    <SelectItem key={optionValue} value={String(optionValue)}>
                      {optionLabel}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'number':
      case 'integer':
        return (
          <div className="space-y-2">
            <Label htmlFor={fieldId} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={fieldId}
              type="number"
              step={fieldType === 'integer' ? "1" : "0.1"}
              value={String(value || '')}
              onChange={(e) => onChange(fieldType === 'integer' ? parseInt(e.target.value) || field.default || 0 : parseFloat(e.target.value) || field.default || 0)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              min={field.minimum}
              max={field.maximum}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      default:
        return (
          <div className="space-y-2">
            <Label htmlFor={fieldId} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={fieldId}
              type={fieldType === 'email' ? 'email' : fieldType === 'password' ? 'password' : fieldType === 'url' ? 'url' : 'text'}
              value={String(value || '')}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              pattern={field.pattern}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );
    }
  };

  const renderField = (key: string, field: any) => {
    // Check if field should be shown based on dependencies
    if (!shouldShowField(key, field)) {
      return null;
    }

    const value = formValues[key] ?? field.default ?? '';
    const fieldType = field.type || 'string';
    
    switch (fieldType) {
      case 'boolean':
        return (
          <div key={key} className="space-y-2">
            <div className="flex items-center space-x-2">
              <Switch
                id={key}
                checked={Boolean(value)}
                onCheckedChange={(checked) => handleFieldChange(key, checked)}
              />
              <Label htmlFor={key} className="text-sm font-medium">
                {field.title || field.label || key}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
            </div>
            {field.description && (
              <p className="text-xs text-muted-foreground ml-6">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'select':
      case 'enum':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Select value={String(value)} onValueChange={(val) => handleFieldChange(key, val)}>
              <SelectTrigger>
                <SelectValue placeholder={field.placeholder || `Select ${field.title || key}`} />
              </SelectTrigger>
              <SelectContent>
                {(field.enum || field.options || []).map((option: any) => {
                  const optionValue = typeof option === 'object' ? option.value : option;
                  const optionLabel = typeof option === 'object' ? option.label : option;
                  return (
                    <SelectItem key={optionValue} value={String(optionValue)}>
                      {optionLabel}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'textarea':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Textarea
              id={key}
              value={String(value)}
              onChange={(e) => handleFieldChange(key, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              rows={field.rows || 3}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'number':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={key}
              type="number"
              step="0.1"
              value={String(value)}
              onChange={(e) => handleFieldChange(key, parseFloat(e.target.value) || field.default || 0)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              min={field.minimum}
              max={field.maximum}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'integer':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={key}
              type="number"
              step="1"
              value={String(value)}
              onChange={(e) => handleFieldChange(key, parseInt(e.target.value) || field.default || 0)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              min={field.minimum}
              max={field.maximum}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'password':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={key}
              type="password"
              value={String(value)}
              onChange={(e) => handleFieldChange(key, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'url':
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={key}
              type="url"
              value={String(value)}
              onChange={(e) => handleFieldChange(key, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              pattern={field.pattern}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );

      case 'object':
        // Initialize object with defaults if not already set
        if (!formValues[key] || typeof formValues[key] !== 'object') {
          const defaultObj: Record<string, any> = {};
          if (field.properties) {
            Object.entries(field.properties).forEach(([k, f]: [string, any]) => {
              defaultObj[k] = f.default;
            });
          }
          handleFieldChange(key, defaultObj);
        }

        return (
          <div key={key} className="space-y-4 p-4 border rounded-lg bg-gray-50">
            <div>
              <Label className="text-sm font-semibold">
                {field.title || field.label || key}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
              {field.description && (
                <p className="text-xs text-muted-foreground mt-1">
                  {field.description}
                </p>
              )}
            </div>
            <div className="space-y-3 ml-4">
              {field.properties && Object.entries(field.properties).map(([nestedKey, nestedField]: [string, any]) => {
                const nestedValue = (formValues[key] && typeof formValues[key] === 'object') 
                  ? formValues[key][nestedKey] 
                  : nestedField.default;

                const handleNestedChange = (nestedValue: any) => {
                  const currentObject = (formValues[key] && typeof formValues[key] === 'object') ? formValues[key] : {};
                  handleFieldChange(key, {
                    ...currentObject,
                    [nestedKey]: nestedValue
                  });
                };

                return (
                  <div key={`${key}.${nestedKey}`}>
                    {renderNestedField(`${key}.${nestedKey}`, nestedKey, nestedField, nestedValue, handleNestedChange)}
                  </div>
                );
              })}
            </div>
          </div>
        );

      default: // string, email, etc.
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key} className="text-sm font-medium">
              {field.title || field.label || key}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={key}
              type={fieldType === 'email' ? 'email' : 'text'}
              value={String(value)}
              onChange={(e) => handleFieldChange(key, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.title || key}`}
              pattern={field.pattern}
            />
            {field.description && (
              <p className="text-xs text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        );
    }
  };

  const renderFieldGroup = (group: any, fields: Record<string, any>) => {
    const groupFields = group.fields.map((fieldKey: string) => {
      const field = fields[fieldKey];
      if (!field) return null;
      return renderField(fieldKey, field);
    }).filter(Boolean);

    if (groupFields.length === 0) return null;

    return (
      <div key={group.title} className="space-y-4">
        <h4 className="font-medium text-sm text-muted-foreground border-b pb-2">
          {group.title}
        </h4>
        <div className="space-y-4 pl-4">
          {groupFields}
        </div>
      </div>
    );
  };

  const hasChanges = JSON.stringify(formValues) !== JSON.stringify(config);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configure {plugin.name}
          </DialogTitle>
          <DialogDescription>
            Configure the settings and behavior for the {plugin.name} plugin.
            {plugin.version && ` (version ${plugin.version})`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Success Message */}
          {success && (
            <Alert className="border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-900/20 dark:text-green-200">
              <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
              <AlertDescription className="font-medium">
                ✅ Configuration saved successfully! All settings have been saved and encrypted.
              </AlertDescription>
            </Alert>
          )}

          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Loading State */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RotateCw className="h-6 w-6 animate-spin mr-2" />
              Loading configuration...
            </div>
          ) : schema?.properties ? (
            <div className="space-y-6">
              {/* Render grouped fields if field_groups are defined */}
              {schema.field_groups ? (
                schema.field_groups.map((group: any) =>
                  renderFieldGroup(group, schema.properties)
                )
              ) : (
                /* Custom rendering for Zammad plugin */
                plugin.name?.toLowerCase() === 'zammad' ? (
                  <div className="space-y-6">
                    {/* Zammad Credentials Section with Test Button */}
                    <div className="space-y-4 p-4 border rounded-lg bg-blue-50 dark:bg-blue-950">
                      <div>
                        <h4 className="font-medium text-sm text-blue-800 dark:text-blue-200 border-b border-blue-200 dark:border-blue-800 pb-2">
                          Zammad Connection Settings
                        </h4>
                      </div>
                      <div className="space-y-4 ml-2">
                        {/* Zammad URL Field */}
                        {schema.properties.zammad_url && renderField('zammad_url', schema.properties.zammad_url)}
                        
                        {/* API Token Field with Show/Hide Toggle */}
                        {schema.properties.api_token && (
                          <div className="space-y-2">
                            <Label htmlFor="api_token" className="text-sm font-medium">
                              {schema.properties.api_token.title || 'API Token'}
                              <span className="text-red-500 ml-1">*</span>
                            </Label>
                            <div className="relative">
                              <Input
                                id="api_token"
                                type={showApiToken ? "text" : "password"}
                                value={String(formValues.api_token || '')}
                                onChange={(e) => handleFieldChange('api_token', e.target.value)}
                                placeholder={config.api_token ? "••••••••••••••••••••••••••••••••••••••• (saved)" : "Enter API Token"}
                                className="pr-10"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                                onClick={() => setShowApiToken(!showApiToken)}
                              >
                                {showApiToken ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </Button>
                            </div>
                            {schema.properties.api_token.description && (
                              <p className="text-xs text-muted-foreground">
                                {schema.properties.api_token.description}
                              </p>
                            )}
                            {config.api_token && (
                              <p className="text-xs text-blue-600 dark:text-blue-400">
                                💡 Leave empty to keep your existing saved token
                              </p>
                            )}
                          </div>
                        )}
                        
                        {/* Test Credentials Button and Result */}
                        {formValues.zammad_url && formValues.api_token && (
                          <div className="space-y-2">
                            <Button 
                              onClick={handleTestCredentials}
                              variant="outline"
                              disabled={testingCredentials}
                              className="flex items-center gap-2"
                              size="sm"
                            >
                              {testingCredentials ? (
                                <>
                                  <RotateCw className="h-4 w-4 animate-spin" />
                                  Testing Credentials...
                                </>
                              ) : (
                                <>
                                  <CheckCircle className="h-4 w-4" />
                                  Test Credentials
                                </>
                              )}
                            </Button>
                            
                            {/* Credentials test result */}
                            {credentialsTestResult && (
                              <Alert variant={credentialsTestResult.success ? "default" : "destructive"} className="mt-2">
                                {credentialsTestResult.success ? (
                                  <CheckCircle className="h-4 w-4" />
                                ) : (
                                  <AlertCircle className="h-4 w-4" />
                                )}
                                <AlertDescription>
                                  {credentialsTestResult.message}
                                </AlertDescription>
                              </Alert>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Chatbot Selection */}
                    {schema.properties.chatbot_id && (
                      <div className="space-y-4">
                        <h4 className="font-medium text-sm text-muted-foreground border-b pb-2">
                          AI Integration
                        </h4>
                        <div className="ml-2">
                          {renderField('chatbot_id', schema.properties.chatbot_id)}
                        </div>
                      </div>
                    )}

                    {/* Render other object fields */}
                    {Object.entries(schema.properties).map(([key, field]: [string, any]) => {
                      if (['zammad_url', 'api_token', 'chatbot_id'].includes(key)) {
                        return null; // Already rendered above
                      }
                      return renderField(key, field);
                    })}
                  </div>
                ) : (
                  /* Fallback to rendering all fields without groups */
                  <div className="space-y-4">
                    {Object.entries(schema.properties).map(([key, field]: [string, any]) =>
                      renderField(key, field)
                    )}
                  </div>
                )
              )}
              
              {/* Connection test button if validation is configured */}
              {schema.validation?.connection_test && (
                <div className="pt-4 border-t">
                  <Button 
                    onClick={handleTestConnection}
                    variant="outline"
                    disabled={testingConnection || !formValues[schema.validation.connection_test.fields[0]] || !formValues[schema.validation.connection_test.fields[1]]}
                    className="flex items-center gap-2"
                  >
                    {testingConnection ? (
                      <>
                        <RotateCw className="h-4 w-4 animate-spin" />
                        Testing Connection...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4" />
                        Test Connection
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                This plugin does not have any configurable settings, or the configuration schema is not available.
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button 
            variant="outline" 
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          {schema?.properties && (
            <Button 
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="flex items-center gap-2"
            >
              {saving ? (
                <>
                  <RotateCw className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Save Configuration
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};