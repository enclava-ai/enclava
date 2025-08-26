/**
 * Plugin Page Renderer - Renders plugin pages with security isolation
 */
"use client"

import React, { useState, useEffect, useRef } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { usePlugin, type PluginInfo } from '../../contexts/PluginContext';
import { config } from '../../lib/config';

interface PluginPageRendererProps {
  pluginId: string;
  pagePath: string;
  componentName?: string;
}

interface PluginIframeProps {
  pluginId: string;
  pagePath: string;
  token: string;
  onLoad?: () => void;
  onError?: (error: string) => void;
}

const PluginIframe: React.FC<PluginIframeProps> = ({ 
  pluginId, 
  pagePath, 
  token, 
  onLoad, 
  onError 
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    
    // Set up iframe communication
    const handleMessage = (event: MessageEvent) => {
      // Only accept messages from our iframe
      if (event.source !== iframe.contentWindow) return;
      
      // Validate origin - should be from our backend
      const allowedOrigins = [
        window.location.origin,
        config.getBackendUrl(),
        config.getApiUrl()
      ].filter(Boolean);
      
      if (!allowedOrigins.some(origin => event.origin.startsWith(origin))) {
        return;
      }
      
      try {
        const message = event.data;
        
        switch (message.type) {
          case 'plugin_loaded':
            setLoading(false);
            onLoad?.();
            break;
          case 'plugin_error':
            setLoading(false);
            onError?.(message.error || 'Plugin failed to load');
            break;
          case 'plugin_resize':
            if (message.height && iframe) {
              iframe.style.height = `${message.height}px`;
            }
            break;
          case 'plugin_navigate':
            // Handle navigation within plugin
            if (message.path) {
              // Update URL without reload
              const newUrl = `/plugins/${pluginId}${message.path}`;
              window.history.pushState(null, '', newUrl);
            }
            break;
        }
      } catch (err) {
      }
    };
    
    window.addEventListener('message', handleMessage);
    
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [pluginId, onLoad, onError]);
  
  const iframeUrl = `/api-internal/v1/plugins/${pluginId}/ui${pagePath}?token=${encodeURIComponent(token)}`;
  
  return (
    <div className="relative w-full">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
          <div className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm text-muted-foreground">Loading plugin...</span>
          </div>
        </div>
      )}
      
      <iframe
        ref={iframeRef}
        src={iframeUrl}
        title={`Plugin ${pluginId} - ${pagePath}`}
        className="w-full border-0"
        style={{ 
          minHeight: '400px',
          maxHeight: '100vh',
          backgroundColor: 'transparent'
        }}
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
        onLoad={() => {
          // Iframe loaded, but plugin might still be initializing
          // Wait for plugin_loaded message
        }}
        onError={() => {
          setLoading(false);
          onError?.('Failed to load plugin iframe');
        }}
      />
    </div>
  );
};

const PluginComponentRenderer: React.FC<{
  plugin: PluginInfo;
  componentName: string;
}> = ({ plugin, componentName }) => {
  const { getPluginComponent } = usePlugin();
  
  const PluginComponent = getPluginComponent(plugin.id, componentName);
  
  if (!PluginComponent) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Component '{componentName}' not found in plugin '{plugin.name}'
        </AlertDescription>
      </Alert>
    );
  }
  
  return (
    <div className="plugin-component-container">
      <PluginComponent />
    </div>
  );
};

export const PluginPageRenderer: React.FC<PluginPageRendererProps> = ({
  pluginId,
  pagePath,
  componentName
}) => {
  const { user, token } = useAuth();
  const { 
    installedPlugins, 
    getPluginPages, 
    isPluginPageAuthorized,
    loading: pluginsLoading 
  } = usePlugin();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Find the plugin
  const plugin = installedPlugins.find(p => p.id === pluginId);
  
  // Get plugin pages
  const pluginPages = plugin ? getPluginPages(pluginId) : [];
  const currentPage = pluginPages.find(p => p.path === pagePath);
  
  useEffect(() => {
    if (!pluginsLoading) {
      setLoading(false);
    }
  }, [pluginsLoading]);
  
  // Loading state
  if (loading || pluginsLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="space-y-3">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  // Plugin not found
  if (!plugin) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Plugin '{pluginId}' not found or not installed.
        </AlertDescription>
      </Alert>
    );
  }
  
  // Plugin not enabled or loaded
  if (plugin.status !== 'enabled' || !plugin.loaded) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Plugin '{plugin.name}' is not enabled or loaded. Please enable and load the plugin first.
        </AlertDescription>
      </Alert>
    );
  }
  
  // Check authorization
  if (!isPluginPageAuthorized(pluginId, pagePath)) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          You are not authorized to view this plugin page.
        </AlertDescription>
      </Alert>
    );
  }
  
  // Page not found
  if (!currentPage && pluginPages.length > 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Page '{pagePath}' not found in plugin '{plugin.name}'. 
          Available pages: {pluginPages.map(p => p.path).join(', ')}
        </AlertDescription>
      </Alert>
    );
  }
  
  // Authentication required
  if (!user || !token) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Authentication required to view plugin pages.
        </AlertDescription>
      </Alert>
    );
  }
  
  // Error state
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Error loading plugin page: {error}
        </AlertDescription>
      </Alert>
    );
  }
  
  // Render component directly if componentName is provided
  if (componentName) {
    return <PluginComponentRenderer plugin={plugin} componentName={componentName} />;
  }
  
  // Render plugin page in iframe (default)
  return (
    <div className="space-y-4">
      {currentPage && (
        <div>
          <h1 className="text-2xl font-bold">{currentPage.title || currentPage.name}</h1>
          <p className="text-muted-foreground">
            {plugin.name} v{plugin.version}
          </p>
        </div>
      )}
      
      <PluginIframe
        pluginId={pluginId}
        pagePath={pagePath}
        token={token}
        onLoad={() => setError(null)}
        onError={setError}
      />
    </div>
  );
};