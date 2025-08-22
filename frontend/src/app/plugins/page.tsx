"use client"

import React from 'react';
import { PluginManager } from '@/components/plugins/PluginManager';

export default function PluginsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Plugin Manager</h1>
        <p className="text-muted-foreground">
          Discover, install, and manage plugins to extend platform functionality
        </p>
      </div>
      
      <PluginManager />
    </div>
  );
}