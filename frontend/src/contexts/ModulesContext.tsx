"use client"

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react"
import { apiClient } from "@/lib/api-client"
import { tokenManager } from "@/lib/token-manager"
import { usePathname } from "next/navigation"

interface Module {
  name: string
  version: string
  description: string
  initialized: boolean
  enabled: boolean
  stats?: any
}

interface ModulesResponse {
  total: number
  modules: Module[]
  module_count: number
  initialized: boolean
}

interface ModulesContextType {
  modules: Module[]
  enabledModules: Set<string>
  isLoading: boolean
  error: string | null
  refreshModules: () => Promise<void>
  isModuleEnabled: (moduleName: string) => boolean
  lastUpdated: Date | null
}

const ModulesContext = createContext<ModulesContextType | undefined>(undefined)

export function ModulesProvider({ children }: { children: ReactNode }) {
  const [modules, setModules] = useState<Module[]>([])
  const [enabledModules, setEnabledModules] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const pathname = usePathname()

  // Check if we're on an auth page
  const isAuthPage = pathname === '/login' || pathname === '/register' || pathname === '/forgot-password'

  const fetchModules = useCallback(async () => {
    // Don't fetch if we're on an auth page or not authenticated
    if (isAuthPage || !tokenManager.isAuthenticated()) {
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      setError(null)

      const data: ModulesResponse = await apiClient.get("/api-internal/v1/modules/")
      
      setModules(data.modules)
      
      // Create set of enabled module names for fast lookup
      const enabledSet = new Set(
        data.modules
          .filter(module => module.enabled && module.initialized)
          .map(module => module.name)
      )
      setEnabledModules(enabledSet)
      setLastUpdated(new Date())
      
    } catch (err) {
      // If we get a 401 error, clear the tokens
      if (err && typeof err === 'object' && 'response' in err && (err.response as any)?.status === 401) {
        tokenManager.clearTokens()
        setModules([])
        setEnabledModules(new Set())
        setError(null)
        setLastUpdated(null)
      } else if (tokenManager.isAuthenticated()) {
        // Only set error if we're authenticated (to avoid noise on auth pages)
        setError(err instanceof Error ? err.message : "Failed to load modules")
      }
    } finally {
      setIsLoading(false)
    }
  }, [isAuthPage])

  const refreshModules = useCallback(async () => {
    await fetchModules()
  }, [fetchModules])

  const isModuleEnabled = useCallback((moduleName: string): boolean => {
    return enabledModules.has(moduleName)
  }, [enabledModules])

  useEffect(() => {
    // Only fetch if authenticated and not on auth page
    if (!isAuthPage && tokenManager.isAuthenticated()) {
      fetchModules()
    }
    
    // Set up periodic refresh every 30 seconds to catch module state changes
    // But only if authenticated
    let interval: NodeJS.Timeout | null = null
    if (!isAuthPage && tokenManager.isAuthenticated()) {
      interval = setInterval(fetchModules, 30000)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [fetchModules, isAuthPage])

  // Listen for custom events that indicate module state changes
  useEffect(() => {
    const handleModuleStateChange = () => {
      refreshModules()
    }

    window.addEventListener("moduleStateChanged", handleModuleStateChange)
    
    return () => {
      window.removeEventListener("moduleStateChanged", handleModuleStateChange)
    }
  }, [refreshModules])

  // Listen for authentication changes
  useEffect(() => {
    const handleTokensUpdated = () => {
      // When tokens are updated (user logs in), fetch modules
      if (!isAuthPage) {
        fetchModules()
      }
    }

    const handleTokensCleared = () => {
      // When tokens are cleared (user logs out), clear modules
      setModules([])
      setEnabledModules(new Set())
      setError(null)
      setLastUpdated(null)
    }

    tokenManager.on('tokensUpdated', handleTokensUpdated)
    tokenManager.on('tokensCleared', handleTokensCleared)
    tokenManager.on('logout', handleTokensCleared)

    return () => {
      tokenManager.off('tokensUpdated', handleTokensUpdated)
      tokenManager.off('tokensCleared', handleTokensCleared)
      tokenManager.off('logout', handleTokensCleared)
    }
  }, [fetchModules, isAuthPage])

  return (
    <ModulesContext.Provider
      value={{
        modules,
        enabledModules,
        isLoading,
        error,
        refreshModules,
        isModuleEnabled,
        lastUpdated,
      }}
    >
      {children}
    </ModulesContext.Provider>
  )
}

export function useModules() {
  const context = useContext(ModulesContext)
  if (context === undefined) {
    // During SSR/SSG, return default values instead of throwing
    if (typeof window === "undefined") {
      return {
        modules: [],
        enabledModules: new Set<string>(),
        isLoading: true,
        error: null,
        refreshModules: async () => {},
        isModuleEnabled: () => false,
        lastUpdated: null,
      }
    }
    throw new Error("useModules must be used within a ModulesProvider")
  }
  return context
}

// Helper function to trigger module state refresh from other components
export function triggerModuleRefresh() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("moduleStateChanged"))
  }
}