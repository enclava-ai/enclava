"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ThemeToggle } from "@/components/ui/theme-toggle"
import { UserMenu } from "@/components/ui/user-menu"
import { useAuth } from "@/components/providers/auth-provider"
import { useModules } from "@/contexts/ModulesContext"
import { usePlugin } from "@/contexts/PluginContext"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown } from "lucide-react"

// Module to navigation mapping
const MODULE_NAV_MAP = {
  chatbot: { href: "/chatbot", label: "Chatbot" },
  rag: { href: "/rag", label: "RAG" },
  // Add more mappings as needed
}

const Navigation = () => {
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const { isModuleEnabled } = useModules()
  const { installedPlugins, getPluginPages } = usePlugin()
  const [isClient, setIsClient] = React.useState(false)

  React.useEffect(() => {
    setIsClient(true)
  }, [])

  // Get plugin navigation items
  const pluginNavItems = installedPlugins
    .filter(plugin => plugin.status === 'enabled' && plugin.loaded)
    .map(plugin => {
      const pages = getPluginPages(plugin.id);
      if (pages.length === 0) return null;
      
      if (pages.length === 1) {
        // Single page plugin
        return {
          href: `/plugins/${plugin.id}${pages[0].path}`,
          label: plugin.name
        };
      } else {
        // Multi-page plugin
        return {
          href: `/plugins/${plugin.id}`,
          label: plugin.name,
          children: pages.map(page => ({
            href: `/plugins/${plugin.id}${page.path}`,
            label: page.title || page.name
          }))
        };
      }
    })
    .filter(Boolean);

  // Core navigation items that are always visible
  const coreNavItems = [
    { href: "/dashboard", label: "Dashboard" },
    { 
      href: "/llm", 
      label: "LLM",
      children: [
        { href: "/llm", label: "Models & Config" },
        { href: "/playground", label: "Playground" },
      ]
    },
    { 
      href: "/settings", 
      label: "Settings",
      children: [
        { href: "/settings", label: "System Settings" },
        { href: "/plugins", label: "Plugins" },
        { href: "/prompt-templates", label: "Prompt Templates" },
      ]
    },
  ]

  // Dynamic navigation items based on enabled modules
  const moduleNavItems = Object.entries(MODULE_NAV_MAP)
    .filter(([moduleName]) => isModuleEnabled(moduleName))
    .map(([, navItem]) => navItem)

  // Combine core, module-based, and plugin navigation items
  const navItems = [...coreNavItems, ...moduleNavItems, ...pluginNavItems]

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 hidden md:flex">
          <Link href={isClient && user ? "/dashboard" : "/"} className="mr-6 flex items-center space-x-2">
            <div className="h-6 w-6 rounded bg-gradient-to-br from-empire-600 to-empire-800" />
            <span className="hidden font-bold sm:inline-block">
              Enclava
            </span>
          </Link>
          {isClient && user && (
            <nav className="flex items-center space-x-6 text-sm font-medium">
              {navItems.map((item) => (
              item.children ? (
                <DropdownMenu key={item.href}>
                  <DropdownMenuTrigger className={cn(
                    "flex items-center gap-1 transition-colors hover:text-foreground/80",
                    pathname.startsWith(item.href) || item.children.some(child => pathname === child.href)
                      ? "text-foreground"
                      : "text-foreground/60"
                  )}>
                    {item.label}
                    <ChevronDown className="h-3 w-3" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {item.children.map((child) => (
                      <DropdownMenuItem key={child.href} asChild>
                        <Link
                          href={child.href}
                          className={cn(
                            "w-full",
                            pathname === child.href && "bg-accent"
                          )}
                        >
                          {child.label}
                        </Link>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "transition-colors hover:text-foreground/80",
                    pathname === item.href
                      ? "text-foreground"
                      : "text-foreground/60"
                  )}
                >
                  {item.label}
                </Link>
              )
            ))}
            </nav>
          )}
        </div>
        
        <div className="flex flex-1 items-center justify-end space-x-2">
          <nav className="flex items-center space-x-2">
            <ThemeToggle />
            
            {isClient && user ? (
              <UserMenu />
            ) : isClient ? (
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className="h-8"
                >
                  <Link href="/login">Login</Link>
                </Button>
                <Button
                  size="sm"
                  asChild
                  className="h-8"
                >
                  <Link href="/register">Register</Link>
                </Button>
              </div>
            ) : null}
          </nav>
        </div>
      </div>
    </header>
  )
}

export { Navigation }