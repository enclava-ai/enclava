/**
 * Plugin Manager - Main plugin management interface
 */
"use client"

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Search, 
  Filter, 
  Download, 
  Trash2, 
  Play, 
  Square, 
  Settings, 
  Info, 
  RotateCw,
  Store,
  LayoutDashboard,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle
} from 'lucide-react';
import { usePlugin, type PluginInfo, type AvailablePlugin } from '../../contexts/PluginContext';
import { useAuth } from '../../contexts/AuthContext';
import { PluginConfigurationDialog } from './PluginConfigurationDialog';

interface PluginCardProps {
  plugin: PluginInfo;
  onAction: (action: string, plugin: PluginInfo) => void;
}

const InstalledPluginCard: React.FC<PluginCardProps> = ({ plugin, onAction }) => {
  const getStatusBadge = (status: string) => {
    const variants = {
      'enabled': { variant: 'default' as const, icon: CheckCircle, text: 'Enabled' },
      'disabled': { variant: 'secondary' as const, icon: XCircle, text: 'Disabled' },
      'installed': { variant: 'outline' as const, icon: Clock, text: 'Installed' },
      'uninstalled': { variant: 'destructive' as const, icon: AlertCircle, text: 'Uninstalled' }
    };
    
    const config = variants[status as keyof typeof variants] || variants.installed;
    const IconComponent = config.icon;
    
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <IconComponent className="h-3 w-3" />
        {config.text}
      </Badge>
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{plugin.name}</CardTitle>
            <CardDescription className="mt-1">
              v{plugin.version} • {plugin.author}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {getStatusBadge(plugin.status)}
            {plugin.loaded && (
              <Badge variant="outline" className="text-green-600">
                Loaded
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">{plugin.description}</p>
        
        <div className="flex flex-wrap gap-2">
          {plugin.status === 'enabled' ? (
            <>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={() => onAction('disable', plugin)}
                className="flex items-center gap-1"
              >
                <Square className="h-4 w-4" />
                Disable
              </Button>
              {!plugin.loaded ? (
                <Button 
                  size="sm" 
                  onClick={() => onAction('load', plugin)}
                  className="flex items-center gap-1"
                >
                  <Play className="h-4 w-4" />
                  Load
                </Button>
              ) : (
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => onAction('unload', plugin)}
                  className="flex items-center gap-1"
                >
                  <Square className="h-4 w-4" />
                  Unload
                </Button>
              )}
            </>
          ) : (
            <Button 
              size="sm" 
              onClick={() => onAction('enable', plugin)}
              className="flex items-center gap-1"
            >
              <Play className="h-4 w-4" />
              Enable
            </Button>
          )}
          
          <Button 
            size="sm" 
            variant="outline"
            onClick={() => onAction('configure', plugin)}
            className="flex items-center gap-1"
          >
            <Settings className="h-4 w-4" />
            Configure
          </Button>
          
          <Button 
            size="sm" 
            variant="destructive"
            onClick={() => onAction('uninstall', plugin)}
            className="flex items-center gap-1"
          >
            <Trash2 className="h-4 w-4" />
            Uninstall
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

interface AvailablePluginCardProps {
  plugin: AvailablePlugin;
  onInstall: (plugin: AvailablePlugin) => void;
}

const AvailablePluginCard: React.FC<AvailablePluginCardProps> = ({ plugin, onInstall }) => {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{plugin.name}</CardTitle>
            <CardDescription className="mt-1">
              v{plugin.version} • {plugin.author}
            </CardDescription>
          </div>
          <Badge variant="outline">{plugin.category}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-3">{plugin.description}</p>
        
        <div className="flex flex-wrap gap-1 mb-4">
          {plugin.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
        
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {plugin.local_status.installed ? (
              <div className="flex items-center gap-1 text-green-600">
                <CheckCircle className="h-4 w-4" />
                Installed {plugin.local_status.version && `(v${plugin.local_status.version})`}
              </div>
            ) : (
              'Not installed'
            )}
          </div>
          
          {!plugin.local_status.installed ? (
            <Button 
              size="sm"
              onClick={() => onInstall(plugin)}
              className="flex items-center gap-1"
            >
              <Download className="h-4 w-4" />
              Install
            </Button>
          ) : plugin.local_status.update_available ? (
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => onInstall(plugin)}
              className="flex items-center gap-1"
            >
              <RotateCw className="h-4 w-4" />
              Update
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
};

export const PluginManager: React.FC = () => {
  const { user, token } = useAuth();
  const {
    installedPlugins,
    availablePlugins,
    loading,
    error,
    refreshInstalledPlugins,
    searchAvailablePlugins,
    installPlugin,
    uninstallPlugin,
    enablePlugin,
    disablePlugin,
    loadPlugin,
    unloadPlugin,
  } = usePlugin();

  const [activeTab, setActiveTab] = useState<string>('installed');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [configuringPlugin, setConfiguringPlugin] = useState<PluginInfo | null>(null);

  // Load initial data only when authenticated
  useEffect(() => {
    if (user && token) {
      refreshInstalledPlugins();
    }
  }, [user, token, refreshInstalledPlugins]);

  // Load available plugins when switching to discover tab and authenticated
  useEffect(() => {
    if (activeTab === 'discover' && user && token) {
      searchAvailablePlugins();
    }
  }, [activeTab, user, token, searchAvailablePlugins]);

  const handlePluginAction = async (action: string, plugin: PluginInfo) => {
    try {
      switch (action) {
        case 'enable':
          await enablePlugin(plugin.id);
          break;
        case 'disable':
          await disablePlugin(plugin.id);
          break;
        case 'load':
          await loadPlugin(plugin.id);
          break;
        case 'unload':
          await unloadPlugin(plugin.id);
          break;
        case 'uninstall':
          if (confirm(`Are you sure you want to uninstall ${plugin.name}?`)) {
            await uninstallPlugin(plugin.id);
          }
          break;
        case 'configure':
          setConfiguringPlugin(plugin);
          break;
      }
    } catch (err) {
      console.error(`Failed to ${action} plugin:`, err);
    }
  };

  const handleInstallPlugin = async (plugin: AvailablePlugin) => {
    try {
      await installPlugin(plugin.id, plugin.version);
    } catch (err) {
      console.error('Failed to install plugin:', err);
    }
  };

  const filteredAvailablePlugins = availablePlugins.filter(plugin => {
    const matchesSearch = searchQuery === '' || 
      plugin.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      plugin.description.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesCategory = selectedCategory === '' || plugin.category === selectedCategory;
    
    return matchesSearch && matchesCategory;
  });

  const categories = Array.from(new Set(availablePlugins.map(p => p.category)));

  // Show authentication required message if not authenticated
  if (!user || !token) {
    return (
      <div className="space-y-6">
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            Please <a href="/login" className="underline">log in</a> to access the plugin manager.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="installed" className="flex items-center gap-2">
            <LayoutDashboard className="h-4 w-4" />
            Installed ({installedPlugins.length})
          </TabsTrigger>
          <TabsTrigger value="discover" className="flex items-center gap-2">
            <Store className="h-4 w-4" />
            Discover
          </TabsTrigger>
        </TabsList>

        <TabsContent value="installed" className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Installed Plugins</h3>
            <Button 
              variant="outline" 
              onClick={refreshInstalledPlugins}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RotateCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RotateCw className="h-6 w-6 animate-spin mr-2" />
              Loading plugins...
            </div>
          ) : installedPlugins.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <Store className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold mb-2">No Plugins Installed</h3>
                <p className="text-muted-foreground mb-4">
                  Get started by discovering and installing plugins from the marketplace.
                </p>
                <Button onClick={() => setActiveTab('discover')}>
                  Discover Plugins
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {installedPlugins.map((plugin) => (
                <InstalledPluginCard
                  key={plugin.id}
                  plugin={plugin}
                  onAction={handlePluginAction}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="discover" className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search plugins..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="max-w-sm"
              />
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-2 border rounded-md"
            >
              <option value="">All Categories</option>
              {categories.map(category => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RotateCw className="h-6 w-6 animate-spin mr-2" />
              Loading available plugins...
            </div>
          ) : filteredAvailablePlugins.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <Search className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold mb-2">No Plugins Found</h3>
                <p className="text-muted-foreground">
                  {searchQuery || selectedCategory 
                    ? 'Try adjusting your search criteria.'
                    : 'The plugin marketplace appears to be empty or unavailable.'
                  }
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredAvailablePlugins.map((plugin) => (
                <AvailablePluginCard
                  key={plugin.id}
                  plugin={plugin}
                  onInstall={handleInstallPlugin}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Configuration Dialog */}
      {configuringPlugin && (
        <PluginConfigurationDialog
          plugin={configuringPlugin}
          open={!!configuringPlugin}
          onOpenChange={(open) => !open && setConfiguringPlugin(null)}
        />
      )}
    </div>
  );
};