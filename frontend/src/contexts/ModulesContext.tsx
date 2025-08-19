"use client"

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react"

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
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchModules = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const token = localStorage.getItem("token")
      if (!token) {
        setError("No authentication token")
        return
      }

      const response = await fetch("/api/modules", {
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        // Disable caching to ensure fresh data
        cache: "no-store"
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch modules: ${response.status}`)
      }

      const data: ModulesResponse = await response.json()
      
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
      console.error("Error fetching modules:", err)
      setError(err instanceof Error ? err.message : "Failed to load modules")
    } finally {
      setIsLoading(false)
    }
  }, [])

  const refreshModules = useCallback(async () => {
    await fetchModules()
  }, [fetchModules])

  const isModuleEnabled = useCallback((moduleName: string): boolean => {
    return enabledModules.has(moduleName)
  }, [enabledModules])

  useEffect(() => {
    fetchModules()
    
    // Set up periodic refresh every 30 seconds to catch module state changes
    const interval = setInterval(fetchModules, 30000)
    
    return () => clearInterval(interval)
  }, [fetchModules])

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