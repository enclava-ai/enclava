"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronDown, Menu } from "lucide-react"

import { useAuth } from "@/components/providers/auth-provider"
import { useModules } from "@/contexts/ModulesContext"
import { usePlugin } from "@/contexts/PluginContext"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { ThemeToggle } from "@/components/ui/theme-toggle"
import { UserMenu } from "@/components/ui/user-menu"

interface NavItem {
  href: string
  label: string
  children?: NavItem[]
}

interface NavigationProps {
  children: React.ReactNode
}

// Module to navigation mapping
const MODULE_NAV_MAP: Record<string, NavItem> = {
  rag: { href: "/rag", label: "RAG" },
  extract: { href: "/extract", label: "Extract" },
  workflow: { href: "/workflows", label: "Workflows" },
}

function isActiveItem(item: NavItem, pathname: string) {
  if (item.children?.length) {
    return (
      pathname.startsWith(item.href) ||
      item.children.some((child) => pathname === child.href)
    )
  }

  return pathname === item.href
}

function getCurrentTitle(items: NavItem[], pathname: string) {
  for (const item of items) {
    const activeChild = item.children?.find((child) => pathname === child.href)

    if (activeChild) {
      return `${item.label} / ${activeChild.label}`
    }

    if (isActiveItem(item, pathname)) {
      return item.label
    }
  }

  return "Enclava"
}

function BrandLink({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      href="/dashboard"
      className={cn(
        "flex items-center gap-2 rounded-md font-display text-sm font-bold text-foreground outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring",
        compact && "justify-center"
      )}
    >
      <span className="h-7 w-7 rounded-sm bg-primary" aria-hidden="true" />
      {!compact && <span>Enclava</span>}
    </Link>
  )
}

function NavLinkList({
  items,
  pathname,
  onNavigate,
}: {
  items: NavItem[]
  pathname: string
  onNavigate?: () => void
}) {
  return (
    <nav className="space-y-1" aria-label="Primary navigation">
      {items.map((item) => {
        const active = isActiveItem(item, pathname)

        return (
          <div key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex min-h-9 items-center justify-between rounded-md px-3 py-2 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring",
                active && "bg-accent-soft text-primary"
              )}
            >
              <span>{item.label}</span>
              {item.children?.length ? (
                <ChevronDown
                  className={cn(
                    "h-4 w-4 text-muted-foreground transition-colors",
                    active && "text-primary"
                  )}
                  aria-hidden="true"
                />
              ) : null}
            </Link>
            {item.children?.length ? (
              <div className="mt-1 space-y-1 border-l border-border/70 pl-3 ml-3">
                {item.children.map((child) => {
                  const childActive = pathname === child.href

                  return (
                    <Link
                      key={child.href}
                      href={child.href}
                      onClick={onNavigate}
                      aria-current={childActive ? "page" : undefined}
                      className={cn(
                        "block rounded-md px-3 py-2 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring",
                        childActive && "bg-accent-soft text-primary"
                      )}
                    >
                      {child.label}
                    </Link>
                  )
                })}
              </div>
            ) : null}
          </div>
        )
      })}
    </nav>
  )
}

function PublicShell({
  children,
  isClient,
}: {
  children: React.ReactNode
  isClient: boolean
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="flex h-14 items-center justify-between px-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-md font-display text-sm font-bold text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <span className="h-7 w-7 rounded-sm bg-primary" aria-hidden="true" />
            <span>Enclava</span>
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {isClient ? (
              <>
                <Button variant="outline" size="sm" asChild>
                  <Link href="/login">Login</Link>
                </Button>
                <Button size="sm" asChild>
                  <Link href="/register">Register</Link>
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </header>
      <main className="min-h-[calc(100vh-3.5rem)]">{children}</main>
    </div>
  )
}

function AppShell({
  children,
  navItems,
  pathname,
}: {
  children: React.ReactNode
  navItems: NavItem[]
  pathname: string
}) {
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const currentTitle = getCurrentTitle(navItems, pathname)

  return (
    <div className="min-h-screen bg-background lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-border bg-card lg:flex lg:flex-col">
        <div className="flex h-14 items-center border-b border-border px-4">
          <BrandLink />
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <NavLinkList items={navItems} pathname={pathname} />
        </div>
        <div className="border-t border-border p-3">
          <UserMenu />
        </div>
      </aside>

      <div className="min-h-screen">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-card/80 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
              <Button
                variant="outline"
                size="icon"
                className="h-9 w-9 lg:hidden"
                onClick={() => setMobileOpen(true)}
              >
                <Menu className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Open navigation</span>
              </Button>
              <DialogContent className="!left-0 !top-0 !h-screen !w-80 !max-w-[calc(100vw-2rem)] !translate-x-0 !translate-y-0 rounded-none border-y-0 border-l-0 border-r border-border p-0 sm:rounded-none">
                <div className="flex h-full flex-col">
                  <div className="border-b border-border px-4 py-4">
                    <DialogTitle>Navigation</DialogTitle>
                    <DialogDescription className="sr-only">
                      Primary Enclava navigation
                    </DialogDescription>
                  </div>
                  <div className="flex-1 overflow-y-auto px-3 py-4">
                    <NavLinkList
                      items={navItems}
                      pathname={pathname}
                      onNavigate={() => setMobileOpen(false)}
                    />
                  </div>
                  <div className="border-t border-border p-3">
                    <UserMenu />
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <div className="hidden lg:block">
              <BrandLink compact />
            </div>
            <div className="min-w-0">
              <p className="truncate text-base font-semibold leading-tight text-foreground">
                {currentTitle}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <div className="lg:hidden">
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  )
}

function Navigation({ children }: NavigationProps) {
  const pathname = usePathname()
  const { user } = useAuth()
  const { isModuleEnabled } = useModules()
  const { installedPlugins, getPluginPages } = usePlugin()
  const [isClient, setIsClient] = React.useState(false)

  React.useEffect(() => {
    setIsClient(true)
  }, [])

  // Get plugin navigation items
  const pluginNavItems = installedPlugins
    .filter((plugin) => plugin.status === "enabled" && plugin.loaded)
    .map<NavItem | null>((plugin) => {
      const pages = getPluginPages(plugin.id)
      if (pages.length === 0) return null

      if (pages.length === 1) {
        // Single page plugin
        return {
          href: `/plugins/${plugin.id}${pages[0].path}`,
          label: plugin.name,
        }
      }

      // Multi-page plugin
      return {
        href: `/plugins/${plugin.id}`,
        label: plugin.name,
        children: pages.map((page) => ({
          href: `/plugins/${plugin.id}${page.path}`,
          label: page.title || page.name,
        })),
      }
    })
    .filter((item): item is NavItem => item !== null)

  // Check if user has admin permissions
  const hasAdminAccess =
    user?.role === "admin" ||
    user?.role === "super_admin" ||
    user?.is_superuser ||
    user?.permissions?.includes("platform:users:read") ||
    user?.permissions?.includes("platform:admin:access")

  // Build settings children based on permissions
  const settingsChildren: NavItem[] = [
    { href: "/settings", label: "System Settings" },
    { href: "/settings/llm", label: "LLM" },
    ...(hasAdminAccess
      ? [
          { href: "/admin/users", label: "Users" },
          { href: "/admin/api-keys", label: "API Keys" },
          { href: "/admin/connectors", label: "Connectors" },
        ]
      : []),
  ]

  // Core navigation items that are always visible
  // Order: Dashboard, Agents, module items, Settings
  const coreNavItems: NavItem[] = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/agents", label: "Agents" },
  ]

  // Settings goes at the end
  const settingsItem: NavItem = {
    href: "/settings",
    label: "Settings",
    children: settingsChildren,
  }

  // Dynamic navigation items based on enabled modules
  const moduleNavItems = Object.entries(MODULE_NAV_MAP)
    .filter(([moduleName]) => isModuleEnabled(moduleName))
    .map(([, navItem]) => navItem)

  // Combine: Dashboard, Agents, module items, plugins, then Settings at the end
  const navItems = [
    ...coreNavItems,
    ...moduleNavItems,
    ...pluginNavItems,
    settingsItem,
  ]

  if (!isClient || !user) {
    return <PublicShell isClient={isClient}>{children}</PublicShell>
  }

  return (
    <AppShell navItems={navItems} pathname={pathname}>
      {children}
    </AppShell>
  )
}

export { AppShell, Navigation }
