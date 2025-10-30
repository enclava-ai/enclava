"use client"

/**
 * Plugin Context - Manages plugin state and UI integration
 */
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useAuth } from '@/components/providers/auth-provider';
import { apiClient } from '@/lib/api-client';
import { useToast } from "@/hooks/use-toast";

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  status: 'enabled' | 'disabled' | 'installed' | 'uninstalled';
  loaded: boolean;
  manifest?: any;
  health?: any;
  resource_usage?: any;
  pages?: PluginPage[];
}

export interface PluginPage {
  name: string;
  path: string;
  component: string;
  title?: string;
  icon?: string;
  requiresAuth?: boolean;
}

export interface PluginConfiguration {
  plugin_id: string;
  configuration: Record<string, any>;
  schema?: any;
  last_updated?: string;
}

export interface AvailablePlugin {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  tags: string[];
  category: string;
  local_status: {
    installed: boolean;
    version?: string;
    status?: string;
    update_available?: boolean;
  };
}

interface PluginContextType {
  // State
  installedPlugins: PluginInfo[];
  availablePlugins: AvailablePlugin[];
  pluginConfigurations: Record<string, PluginConfiguration>;
  loading: boolean;
  error: string | null;
  
  // Actions
  refreshInstalledPlugins: () => Promise<void>;
  searchAvailablePlugins: (query?: string, tags?: string[], category?: string) => Promise<void>;
  installPlugin: (pluginId: string, version: string) => Promise<boolean>;
  uninstallPlugin: (pluginId: string, keepData?: boolean) => Promise<boolean>;
  enablePlugin: (pluginId: string) => Promise<boolean>;
  disablePlugin: (pluginId: string) => Promise<boolean>;
  loadPlugin: (pluginId: string) => Promise<boolean>;
  unloadPlugin: (pluginId: string) => Promise<boolean>;
  
  // Configuration
  getPluginConfiguration: (pluginId: string) => Promise<PluginConfiguration | null>;
  savePluginConfiguration: (pluginId: string, config: Record<string, any>) => Promise<boolean>;
  getPluginSchema: (pluginId: string) => Promise<any>;
  
  // UI Integration
  getPluginPages: (pluginId: string) => PluginPage[];
  isPluginPageAuthorized: (pluginId: string, pagePath: string) => boolean;
  getPluginComponent: (pluginId: string, componentName: string) => React.ComponentType | null;
}

const PluginContext = createContext<PluginContextType | undefined>(undefined);

export const usePlugin = () => {
  const context = useContext(PluginContext);
  if (context === undefined) {
    // During SSR/SSG, return default values instead of throwing
    if (typeof window === "undefined") {
      return {
        installedPlugins: [],
        availablePlugins: [],
        pluginConfigurations: {},
        loading: false,
        error: null,
        refreshInstalledPlugins: async () => {},
        searchAvailablePlugins: async () => {},
        installPlugin: async () => false,
        uninstallPlugin: async () => false,
        enablePlugin: async () => false,
        disablePlugin: async () => false,
        loadPlugin: async () => false,
        unloadPlugin: async () => false,
        getPluginConfiguration: async () => null,
        savePluginConfiguration: async () => false,
        getPluginSchema: async () => null,
        getPluginPages: () => [],
        isPluginPageAuthorized: () => false,
        getPluginComponent: () => null,
      };
    }
    throw new Error('usePlugin must be used within a PluginProvider');
  }
  return context;
};

interface PluginProviderProps {
  children: ReactNode;
}

export const PluginProvider: React.FC<PluginProviderProps> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const { toast } = useToast();
  const [installedPlugins, setInstalledPlugins] = useState<PluginInfo[]>([]);
  const [availablePlugins, setAvailablePlugins] = useState<AvailablePlugin[]>([]);
  const [pluginConfigurations, setPluginConfigurations] = useState<Record<string, PluginConfiguration>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Plugin component registry
  const [pluginComponents, setPluginComponents] = useState<Record<string, Record<string, React.ComponentType>>>({});

  const userPermissions = user?.permissions ?? [];

  const hasPermission = useCallback((required: string) => {
    if (!required) {
      return true;
    }
    return userPermissions.some(granted => {
      if (granted === "*" || granted === required) {
        return true;
      }
      if (granted.endsWith(":*")) {
        const prefix = granted.slice(0, -1);
        return required.startsWith(prefix);
      }
      return false;
    });
  }, [userPermissions]);
  
  const apiRequest = async (endpoint: string, options: RequestInit = {}) => {
    if (!isAuthenticated) {
      throw new Error('Authentication required');
    }
    
    const method = (options.method || 'GET').toLowerCase() as 'get' | 'post' | 'put' | 'delete';
    const body = options.body ? JSON.parse(options.body as string) : undefined;
    
    if (method === 'get') {
      return await apiClient.get(`/api-internal/v1/plugins${endpoint}`);
    } else if (method === 'post') {
      return await apiClient.post(`/api-internal/v1/plugins${endpoint}`, body);
    } else if (method === 'put') {
      return await apiClient.put(`/api-internal/v1/plugins${endpoint}`, body);
    } else if (method === 'delete') {
      return await apiClient.delete(`/api-internal/v1/plugins${endpoint}`);
    }
    
    throw new Error(`Unsupported method: ${method}`);
  };
  
  const refreshInstalledPlugins = useCallback(async () => {
    if (!user || !isAuthenticated) {
      setError('Authentication required');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      const data = await apiRequest('/installed');
      setInstalledPlugins(data.plugins);
      
      // Load configurations for installed plugins
      for (const plugin of data.plugins) {
        try {
          const config = await getPluginConfiguration(plugin.id);
          if (config) {
            setPluginConfigurations(prev => ({
              ...prev,
              [plugin.id]: config
            }));
          }
        } catch (configError) {
          console.warn(`Failed to load configuration for plugin ${plugin.id}`, configError);
        }
      }
      
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load installed plugins';
      setError(message);
      toast({
        title: "Plugin load failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [user, isAuthenticated, toast]);
  
  const searchAvailablePlugins = useCallback(async (query = '', tags: string[] = [], category = '') => {
    if (!user || !isAuthenticated) {
      setError('Authentication required');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (query) params.append('query', query);
      if (tags.length > 0) params.append('tags', tags.join(','));
      if (category) params.append('category', category);
      
      const data = await apiRequest(`/discover?${params.toString()}`);
      setAvailablePlugins(data.plugins);
      
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to search plugins';
      setError(message);
      toast({
        title: "Plugin search failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [user, isAuthenticated, toast]);
  
  const installPlugin = useCallback(async (pluginId: string, version: string): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      
      await apiRequest('/install', {
        method: 'POST',
        body: JSON.stringify({
          plugin_id: pluginId,
          version: version,
          source: 'repository'
        }),
      });
      
      // Refresh plugins after installation
      await refreshInstalledPlugins();
      await searchAvailablePlugins(); // Refresh to update local status
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Installation failed';
      setError(message);
      toast({
        title: "Plugin installation failed",
        description: message,
        variant: "destructive",
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [refreshInstalledPlugins, searchAvailablePlugins, toast]);
  
  const uninstallPlugin = async (pluginId: string, keepData = true): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      
      await apiRequest(`/${pluginId}`, {
        method: 'DELETE',
        body: JSON.stringify({ keep_data: keepData }),
      });
      
      // Remove from state
      setInstalledPlugins(prev => prev.filter(p => p.id !== pluginId));
      setPluginConfigurations(prev => {
        const { [pluginId]: removed, ...rest } = prev;
        return rest;
      });
      
      // Unregister components
      setPluginComponents(prev => {
        const { [pluginId]: removed, ...rest } = prev;
        return rest;
      });
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Uninstallation failed';
      setError(message);
      toast({
        title: "Plugin uninstall failed",
        description: message,
        variant: "destructive",
      });
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  const enablePlugin = async (pluginId: string): Promise<boolean> => {
    try {
      await apiRequest(`/${pluginId}/enable`, { method: 'POST' });
      
      // Update plugin status
      setInstalledPlugins(prev => 
        prev.map(p => p.id === pluginId ? { ...p, status: 'enabled' } : p)
      );
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Enable failed';
      setError(message);
      toast({
        title: "Plugin enable failed",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  
  const disablePlugin = async (pluginId: string): Promise<boolean> => {
    try {
      await apiRequest(`/${pluginId}/disable`, { method: 'POST' });
      
      // Update plugin status
      setInstalledPlugins(prev => 
        prev.map(p => p.id === pluginId ? { ...p, status: 'disabled', loaded: false } : p)
      );
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Disable failed';
      setError(message);
      toast({
        title: "Plugin disable failed",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  
  const loadPlugin = async (pluginId: string): Promise<boolean> => {
    try {
      await apiRequest(`/${pluginId}/load`, { method: 'POST' });
      
      // Update plugin status
      setInstalledPlugins(prev => 
        prev.map(p => p.id === pluginId ? { ...p, loaded: true } : p)
      );
      
      // Load plugin UI components
      await loadPluginComponents(pluginId);
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Load failed';
      setError(message);
      toast({
        title: "Plugin load failed",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  
  const unloadPlugin = async (pluginId: string): Promise<boolean> => {
    try {
      await apiRequest(`/${pluginId}/unload`, { method: 'POST' });
      
      // Update plugin status
      setInstalledPlugins(prev => 
        prev.map(p => p.id === pluginId ? { ...p, loaded: false } : p)
      );
      
      // Unregister components
      setPluginComponents(prev => {
        const { [pluginId]: removed, ...rest } = prev;
        return rest;
      });
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unload failed';
      setError(message);
      toast({
        title: "Plugin unload failed",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  
  const getPluginConfiguration = async (pluginId: string): Promise<PluginConfiguration | null> => {
    try {
      const data = await apiRequest(`/${pluginId}/config`);
      return data;
    } catch (err) {
      console.warn(`Failed to fetch configuration for plugin ${pluginId}`, err);
      return null;
    }
  };
  
  const savePluginConfiguration = async (pluginId: string, config: Record<string, any>): Promise<boolean> => {
    try {
      await apiRequest(`/${pluginId}/config`, {
        method: 'POST',
        body: JSON.stringify({ configuration: config }),
      });
      
      // Update local state
      setPluginConfigurations(prev => ({
        ...prev,
        [pluginId]: {
          plugin_id: pluginId,
          configuration: config,
          last_updated: new Date().toISOString()
        }
      }));
      
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save configuration';
      setError(message);
      toast({
        title: "Save failed",
        description: message,
        variant: "destructive",
      });
      return false;
    }
  };
  
  const getPluginSchema = async (pluginId: string): Promise<any> => {
    try {
      // Add cache-busting timestamp to force fresh schema fetch
      const cacheBust = Date.now();
      const data = await apiRequest(`/${pluginId}/schema?t=${cacheBust}`);
      let schema = data.schema;
      
      // For certain plugins, we need to populate dynamic options
      // Find the plugin by ID to get its name
      const plugin = installedPlugins.find(p => p.id === pluginId);
      const pluginName = plugin?.name?.toLowerCase();
      
      if (schema && pluginName === 'zammad') {
        // Populate chatbot options for Zammad
        try {
          const chatbotsData = await apiClient.get('/api-internal/v1/chatbot/list');
          const chatbots = chatbotsData.chatbots || [];
          
          if (schema.properties?.chatbot_id) {
            schema.properties.chatbot_id.type = 'select';
            schema.properties.chatbot_id.options = chatbots.map((chatbot: any) => ({
              value: chatbot.id,
              label: `${chatbot.name} (${chatbot.chatbot_type})`
            }));
          }
        } catch (chatbotError) {
          console.warn(`Failed to populate chatbot options for plugin ${pluginId}`, chatbotError);
        }

        // Populate model options for AI settings
        try {
          const modelsData = await apiClient.get('/api-internal/v1/llm/models');
          const models = modelsData.data || [];
          
          const modelOptions = models.map((model: any) => ({
            value: model.id,
            label: model.id
          }));

          // Set model options for AI summarization
          if (schema.properties?.ai_summarization?.properties?.model) {
            schema.properties.ai_summarization.properties.model.type = 'select';
            schema.properties.ai_summarization.properties.model.options = modelOptions;
          }

          // Set model options for draft settings
          if (schema.properties?.draft_settings?.properties?.model) {
            schema.properties.draft_settings.properties.model.type = 'select';
            schema.properties.draft_settings.properties.model.options = modelOptions;
          }
        } catch (modelError) {
          console.warn(`Failed to populate model options for plugin ${pluginId}`, modelError);
        }
      }
      
      if (schema && pluginName === 'signal') {
        // Populate model options for Signal bot
        try {
          const modelsData = await apiClient.get('/api-internal/v1/llm/models');
          const models = modelsData.models || [];
          
          if (schema.properties?.model) {
            schema.properties.model.options = models.map((model: any) => ({
              value: model.id,
              label: model.name || model.id
            }));
          }
        } catch (modelError) {
          console.warn(`Failed to populate Signal model options for plugin ${pluginId}`, modelError);
        }
      }
      
      return schema;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load plugin schema';
      console.error(`Failed to load schema for plugin ${pluginId}`, err);
      toast({
        title: "Schema load failed",
        description: message,
        variant: "destructive",
      });
      return null;
    }
  };
  
  const loadPluginComponents = async (pluginId: string) => {
    try {
      // Load plugin UI components dynamically
      // This would involve loading the plugin's built JavaScript bundle
      // For now, we'll use a placeholder system
      
      const plugin = installedPlugins.find(p => p.id === pluginId);
      if (!plugin || !plugin.manifest) return;
      
      const uiConfig = plugin.manifest.spec?.ui_config;
      if (!uiConfig) return;
      
      // Register placeholder components for now
      const components: Record<string, React.ComponentType> = {};
      
      if (uiConfig.pages) {
        for (const page of uiConfig.pages) {
          components[page.component] = createPluginComponent(pluginId, page.component);
        }
      }
      
      setPluginComponents(prev => ({
        ...prev,
        [pluginId]: components
      }));
      
    } catch (err) {
      console.error(`Failed to load plugin components for ${pluginId}`, err);
      toast({
        title: "Component load failed",
        description: err instanceof Error ? err.message : 'Unable to load plugin components',
        variant: "destructive",
      });
    }
  };
  
  const createPluginComponent = (pluginId: string, componentName: string): React.ComponentType => {
    return () => (
      <div className="plugin-component-placeholder">
        <h3>Plugin Component: {componentName}</h3>
        <p>Plugin: {pluginId}</p>
        <p>This is a placeholder for the plugin component that would be loaded dynamically.</p>
      </div>
    );
  };
  
  const getPluginPages = (pluginId: string): PluginPage[] => {
    const plugin = installedPlugins.find(p => p.id === pluginId);
    if (!plugin || !plugin.manifest) return [];
    
    const uiConfig = plugin.manifest.spec?.ui_config;
    return uiConfig?.pages || [];
  };
  
  const isPluginPageAuthorized = (pluginId: string, pagePath: string): boolean => {
    const plugin = installedPlugins.find(p => p.id === pluginId);
    if (!plugin || plugin.status !== 'enabled' || !plugin.loaded) {
      return false;
    }

    const manifestPages = plugin.manifest?.spec?.ui_config?.pages ?? plugin.pages ?? [];
    const page = manifestPages.find((p: any) => p.path === pagePath);

    const requiresAuth = page?.requiresAuth !== false;
    if (requiresAuth && !isAuthenticated) {
      return false;
    }

    const requiredPermissions: string[] =
      page?.required_permissions ??
      page?.requiredPermissions ??
      [];

    if (requiredPermissions.length > 0) {
      return requiredPermissions.every(perm => hasPermission(perm));
    }

    if (!requiresAuth) {
      return true;
    }

    if (user?.role && ['super_admin', 'admin'].includes(user.role)) {
      return true;
    }

    const modulePrefix = `modules:${pluginId}`;
    const hasModuleAccess = userPermissions.some(granted => {
      if (granted === 'modules:*') {
        return true;
      }
      if (granted.startsWith(`${modulePrefix}:`)) {
        return true;
      }
      if (granted.endsWith(':*') && granted.startsWith(modulePrefix)) {
        return true;
      }
      return false;
    });

    return hasModuleAccess;
  };
  
  const getPluginComponent = (pluginId: string, componentName: string): React.ComponentType | null => {
    return pluginComponents[pluginId]?.[componentName] || null;
  };
  
  // Load installed plugins on mount, but only when authenticated
  useEffect(() => {
    if (user && isAuthenticated) {
      refreshInstalledPlugins();
    } else {
      // Clear plugin data when not authenticated
      setInstalledPlugins([]);
      setAvailablePlugins([]);
      setPluginConfigurations({});
      setError(null);
    }
  }, [user, isAuthenticated, refreshInstalledPlugins]);
  
  const value: PluginContextType = {
    // State
    installedPlugins,
    availablePlugins,
    pluginConfigurations,
    loading,
    error,
    
    // Actions
    refreshInstalledPlugins,
    searchAvailablePlugins,
    installPlugin,
    uninstallPlugin,
    enablePlugin,
    disablePlugin,
    loadPlugin,
    unloadPlugin,
    
    // Configuration
    getPluginConfiguration,
    savePluginConfiguration,
    getPluginSchema,
    
    // UI Integration
    getPluginPages,
    isPluginPageAuthorized,
    getPluginComponent,
  };
  
  return (
    <PluginContext.Provider value={value}>
      {children}
    </PluginContext.Provider>
  );
};
