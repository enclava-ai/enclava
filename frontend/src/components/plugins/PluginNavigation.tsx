/**
 * Plugin Navigation - Utility components for plugin navigation integration
 */
"use client"

import React from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  LayoutDashboard,
  Settings,
  BarChart3,
  Ticket,
  Users,
  Bell,
  Shield,
  Puzzle
} from 'lucide-react';
import { usePlugin, type PluginInfo, type PluginPage } from '../../contexts/PluginContext';

interface PluginNavigationProps {
  className?: string;
}

const getIconForPage = (pageName: string, pluginId: string) => {
  const iconMap = {
    dashboard: LayoutDashboard,
    settings: Settings,
    analytics: BarChart3,
    tickets: Ticket,
    users: Users,
    notifications: Bell,
    security: Shield,
  };
  
  // Try to match by page name first
  for (const [key, Icon] of Object.entries(iconMap)) {
    if (pageName.toLowerCase().includes(key)) {
      return Icon;
    }
  }
  
  // Try to match by plugin type
  if (pluginId.includes('zammad') || pluginId.includes('helpdesk')) {
    return Ticket;
  }
  if (pluginId.includes('discord') || pluginId.includes('slack')) {
    return Bell;
  }
  if (pluginId.includes('analytics') || pluginId.includes('reporting')) {
    return BarChart3;
  }
  
  // Default plugin icon
  return Puzzle;
};

const PluginNavItem: React.FC<{
  plugin: PluginInfo;
  pages: PluginPage[];
  currentPath: string;
}> = ({ plugin, pages, currentPath }) => {
  const getPluginStatusVariant = () => {
    if (!plugin.loaded) return 'secondary' as const;
    if (plugin.health?.status === 'healthy') return 'default' as const;
    if (plugin.health?.status === 'warning') return 'outline' as const;
    if (plugin.health?.status === 'error') return 'destructive' as const;
    return 'default' as const;
  };

  if (pages.length === 0) return null;

  if (pages.length === 1) {
    const page = pages[0];
    const IconComponent = getIconForPage(page.name, plugin.id);
    const isActive = currentPath.startsWith(`/plugins/${plugin.id}`);
    
    return (
      <Link href={`/plugins/${plugin.id}${page.path}`}>
        <Button 
          variant={isActive ? "default" : "ghost"} 
          className="w-full justify-start"
        >
          <IconComponent className="mr-2 h-4 w-4" />
          {plugin.name}
          <Badge variant={getPluginStatusVariant()} className="ml-auto">
            {plugin.loaded ? 'loaded' : plugin.status}
          </Badge>
        </Button>
      </Link>
    );
  }

  // Multi-page plugin - show as expandable or use a default page
  const mainPage = pages.find(p => p.path === '/' || p.name.toLowerCase().includes('dashboard')) || pages[0];
  const IconComponent = getIconForPage(mainPage.name, plugin.id);
  const isActive = currentPath.startsWith(`/plugins/${plugin.id}`);
  
  return (
    <div className="space-y-1">
      <Link href={`/plugins/${plugin.id}${mainPage.path}`}>
        <Button 
          variant={isActive ? "default" : "ghost"} 
          className="w-full justify-start"
        >
          <IconComponent className="mr-2 h-4 w-4" />
          {plugin.name}
          <Badge variant={getPluginStatusVariant()} className="ml-auto">
            {plugin.loaded ? 'loaded' : plugin.status}
          </Badge>
        </Button>
      </Link>
      
      {/* Additional pages as sub-items */}
      {pages.length > 1 && isActive && (
        <div className="ml-4 space-y-1">
          {pages.filter(p => p !== mainPage).map((page) => {
            const PageIcon = getIconForPage(page.name, plugin.id);
            const pageActive = currentPath === `/plugins/${plugin.id}${page.path}`;
            
            return (
              <Link key={page.path} href={`/plugins/${plugin.id}${page.path}`}>
                <Button 
                  variant={pageActive ? "default" : "ghost"} 
                  size="sm"
                  className="w-full justify-start"
                >
                  <PageIcon className="mr-2 h-3 w-3" />
                  {page.title || page.name}
                </Button>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const PluginNavigation: React.FC<PluginNavigationProps> = ({ 
  className = "" 
}) => {
  const { installedPlugins, getPluginPages, isPluginPageAuthorized } = usePlugin();
  
  // Filter to loaded plugins with accessible pages
  const availablePlugins = installedPlugins.filter(plugin => {
    if (plugin.status !== 'enabled' || !plugin.loaded) return false;
    
    const pages = getPluginPages(plugin.id);
    if (pages.length === 0) return false;
    
    // Check if user has access to at least one page
    return pages.some(page => isPluginPageAuthorized(plugin.id, page.path));
  });

  if (availablePlugins.length === 0) {
    return null;
  }

  return (
    <nav className={`space-y-2 ${className}`}>
      <div className="text-sm font-medium text-muted-foreground">
        Plugin Pages
      </div>
      
      <div className="space-y-1">
        {availablePlugins.map((plugin) => {
          const pages = getPluginPages(plugin.id).filter(page =>
            isPluginPageAuthorized(plugin.id, page.path)
          );
          
          return (
            <PluginNavItem
              key={plugin.id}
              plugin={plugin}
              pages={pages}
              currentPath={typeof window !== 'undefined' ? window.location.pathname : ''}
            />
          );
        })}
      </div>
    </nav>
  );
};

// Simplified plugin quick access for header/toolbar
export const PluginQuickAccess: React.FC = () => {
  const { installedPlugins, getPluginPages } = usePlugin();
  
  // Get plugins with dashboard/main pages
  const quickAccessPlugins = installedPlugins
    .filter(plugin => 
      plugin.status === 'enabled' && 
      plugin.loaded
    )
    .map(plugin => {
      const pages = getPluginPages(plugin.id);
      const dashboardPage = pages.find(page => 
        page.name.toLowerCase().includes('dashboard') ||
        page.name.toLowerCase().includes('main') ||
        page.path === '/'
      );
      
      return dashboardPage ? { plugin, page: dashboardPage } : null;
    })
    .filter(Boolean)
    .slice(0, 5); // Limit to 5 quick access items

  if (quickAccessPlugins.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      {quickAccessPlugins.map(({ plugin, page }) => {
        const IconComponent = getIconForPage(page!.name, plugin!.id);
        
        return (
          <Link key={plugin!.id} href={`/plugins/${plugin!.id}${page!.path}`}>
            <Button variant="outline" size="sm" className="flex items-center gap-1">
              <IconComponent className="h-3 w-3" />
              {plugin!.name}
            </Button>
          </Link>
        );
      })}
    </div>
  );
};

// Plugin status indicator for use in other components
export const PluginStatusIndicator: React.FC<{ plugin: PluginInfo }> = ({ plugin }) => {
  const getStatusVariant = () => {
    if (!plugin.loaded) return 'secondary' as const;
    if (plugin.health?.status === 'healthy') return 'default' as const;
    if (plugin.health?.status === 'warning') return 'outline' as const;
    if (plugin.health?.status === 'error') return 'destructive' as const;
    return 'default' as const;
  };

  const getStatusText = () => {
    if (!plugin.loaded) return plugin.status;
    if (plugin.health?.status) return plugin.health.status;
    return 'loaded';
  };

  return (
    <Badge variant={getStatusVariant()}>
      {getStatusText()}
    </Badge>
  );
};