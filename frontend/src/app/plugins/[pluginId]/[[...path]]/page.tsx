"use client"

import React from 'react';
import { PluginPageRenderer } from '@/components/plugins/PluginPageRenderer';
import { notFound } from 'next/navigation';

interface PluginPageProps {
  params: {
    pluginId: string;
    path?: string[];
  };
}

export default function PluginPage({ params }: PluginPageProps) {
  const { pluginId, path = [] } = params;
  
  if (!pluginId) {
    notFound();
  }
  
  // Construct the page path from the URL segments
  const pagePath = path.length > 0 ? `/${path.join('/')}` : '/';
  
  return (
    <div className="h-full">
      <PluginPageRenderer 
        pluginId={pluginId} 
        pagePath={pagePath}
      />
    </div>
  );
}