"use client"

import { useAuth } from "@/contexts/AuthContext"
import { useState, useEffect } from "react"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useToast } from "@/hooks/use-toast"

// Force dynamic rendering for authentication
export const dynamic = 'force-dynamic'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { 
  Shield, 
  Zap, 
  Database, 
  Activity, 
  Users, 
  Settings,
  Plus,
  TrendingUp,
  Clock,
  CheckCircle,
  Copy,
  AlertTriangle,
  ExternalLink
} from "lucide-react"

interface DashboardStats {
  activeModules: number
  runningModules: number
  standbyModules: number
  totalRequests: number
  requestsChange: number
  totalUsers: number
  activeSessions: number
  uptime: number
}

interface ModuleInfo {
  id: string
  name: string
  description: string
  status: 'running' | 'standby' | 'error'
  icon: string
}

interface RecentActivity {
  id: string
  message: string
  timestamp: string
  type: 'info' | 'success' | 'warning' | 'error'
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}

function DashboardContent() {
  const { user } = useAuth()
  const { toast } = useToast()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([])
  const [loadingStats, setLoadingStats] = useState(true)

  // Get the public API URL from the current window location
  const getPublicApiUrl = () => {
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol
      const hostname = window.location.hostname
      const port = window.location.hostname === 'localhost' ? '58000' : window.location.port || (protocol === 'https:' ? '443' : '80')
      const portSuffix = (protocol === 'https:' && port === '443') || (protocol === 'http:' && port === '80') ? '' : `:${port}`
      return `${protocol}//${hostname}${portSuffix}/v1`
    }
    return 'http://localhost:58000/v1'
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast({
      title: "Copied!",
      description: "API URL copied to clipboard"
    })
  }

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoadingStats(true)
      
      // Fetch real dashboard stats through API proxy
      
      const [statsRes, modulesRes, activityRes] = await Promise.all([
        fetch('/api/analytics/overview').catch(() => null),
        fetch('/api/modules').catch(() => null),
        fetch('/api/audit?limit=5').catch(() => null)
      ])

      // Parse stats response
      if (statsRes?.ok) {
        const statsData = await statsRes.json()
        const moduleStats = await fetch('/api/modules/status').then(r => r.ok ? r.json() : {}).catch(() => ({})) as { total?: number; running?: number; standby?: number }
        
        setStats({
          activeModules: moduleStats.total || 0,
          runningModules: moduleStats.running || 0,
          standbyModules: moduleStats.standby || 0,
          totalRequests: statsData.totalRequests || 0,
          requestsChange: statsData.requestsChange || 0,
          totalUsers: statsData.totalUsers || 0,
          activeSessions: statsData.activeSessions || 0,
          uptime: statsData.uptime || 0
        })
      } else {
        // No mock data - show zeros when API unavailable
        setStats({
          activeModules: 0,
          runningModules: 0,
          standbyModules: 0,
          totalRequests: 0,
          requestsChange: 0,
          totalUsers: 0,
          activeSessions: 0,
          uptime: 0
        })
      }

      // Parse modules response
      if (modulesRes?.ok) {
        const modulesData = await modulesRes.json()
        setModules(modulesData.modules || [])
      } else {
        setModules([])
      }

      // Parse activity response
      if (activityRes?.ok) {
        const activityData = await activityRes.json()
        setRecentActivity(activityData.logs || [])
      } else {
        setRecentActivity([])
      }

    } catch (error) {
      console.error('Error fetching dashboard data:', error)
      // Set empty states instead of mock data
      setStats({
        activeModules: 0,
        runningModules: 0,
        standbyModules: 0,
        totalRequests: 0,
        requestsChange: 0,
        totalUsers: 0,
        activeSessions: 0,
        uptime: 0
      })
      setModules([])
      setRecentActivity([])
    } finally {
      setLoadingStats(false)
    }
  }

  if (loadingStats) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    )
  }

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'success': return 'bg-green-400'
      case 'warning': return 'bg-yellow-400'
      case 'error': return 'bg-red-400'
      default: return 'bg-blue-400'
    }
  }

  const getModuleIcon = (iconType: string) => {
    switch (iconType) {
      case 'database': return Database
      case 'shield': return Shield
      case 'trending': return TrendingUp
      default: return Activity
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-empire-gold">
            Welcome back, {user.name}
          </h1>
          <p className="text-empire-gold/60 mt-1">
            Manage your Enclava platform and modules
          </p>
        </div>
        <Button className="bg-empire-gold hover:bg-empire-gold/90 text-empire-dark">
          <Plus className="h-4 w-4 mr-2" />
          Add Module
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-empire-darker/50 border-empire-gold/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-empire-gold/80">
              Active Modules
            </CardTitle>
            <Zap className="h-4 w-4 text-empire-gold" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-empire-gold">
              {stats?.activeModules || 0}
            </div>
            <p className="text-xs text-empire-gold/60">
              {stats?.runningModules || 0} running, {stats?.standbyModules || 0} standby
            </p>
          </CardContent>
        </Card>

        <Card className="bg-empire-darker/50 border-empire-gold/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-empire-gold/80">
              API Requests
            </CardTitle>
            <Activity className="h-4 w-4 text-empire-gold" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-empire-gold">
              {stats?.totalRequests?.toLocaleString() || 0}
            </div>
            <p className="text-xs text-empire-gold/60">
              {stats?.requestsChange ? 
                (stats.requestsChange > 0 ? '+' : '') + stats.requestsChange + '% from last hour' : 
                'No data available'
              }
            </p>
          </CardContent>
        </Card>

        <Card className="bg-empire-darker/50 border-empire-gold/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-empire-gold/80">
              Users
            </CardTitle>
            <Users className="h-4 w-4 text-empire-gold" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-empire-gold">
              {stats?.totalUsers || 0}
            </div>
            <p className="text-xs text-empire-gold/60">
              {stats?.activeSessions || 0} active sessions
            </p>
          </CardContent>
        </Card>

        <Card className="bg-empire-darker/50 border-empire-gold/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-empire-gold/80">
              Uptime
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-empire-gold" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-empire-gold">
              {stats?.uptime ? stats.uptime.toFixed(1) + '%' : '0%'}
            </div>
            <p className="text-xs text-empire-gold/60">
              {stats?.uptime ? 'System operational' : 'No data available'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Public API URL Section */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-blue-700">
            <ExternalLink className="h-5 w-5" />
            OpenAI-Compatible API Endpoint
          </CardTitle>
          <CardDescription className="text-blue-600">
            Configure external tools with this endpoint URL. Use any OpenAI-compatible client.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <code className="flex-1 p-3 bg-white border border-blue-200 rounded-md text-sm font-mono">
              {getPublicApiUrl()}
            </code>
            <Button
              onClick={() => copyToClipboard(getPublicApiUrl())}
              variant="outline"
              size="sm"
              className="flex items-center gap-1 border-blue-300 text-blue-700 hover:bg-blue-100"
            >
              <Copy className="h-4 w-4" />
              Copy
            </Button>
            <Button
              onClick={() => window.open('/llm', '_blank')}
              variant="outline"
              size="sm"
              className="flex items-center gap-1 border-blue-300 text-blue-700 hover:bg-blue-100"
            >
              <Settings className="h-4 w-4" />
              Configure
            </Button>
          </div>
          <div className="mt-3 text-sm text-blue-600">
            <span className="font-medium">Quick Setup:</span> Copy this URL and use it as the "API Base URL" in Open WebUI, Continue.dev, or any OpenAI client.
          </div>
        </CardContent>
      </Card>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Modules */}
        <div className="lg:col-span-2">
          <Card className="bg-empire-darker/50 border-empire-gold/20">
            <CardHeader>
              <CardTitle className="text-empire-gold">Active Modules</CardTitle>
              <CardDescription>
                Currently running AI processing modules
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {modules.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-empire-gold/60">No modules configured yet</p>
                  <Button className="mt-4 bg-empire-gold hover:bg-empire-gold/90 text-empire-dark">
                    Configure Modules
                  </Button>
                </div>
              ) : (
                modules.map((module) => {
                  const IconComponent = getModuleIcon(module.icon)
                  return (
                    <div key={module.name} className="flex items-center justify-between p-4 bg-empire-dark/50 rounded-lg">
                      <div className="flex items-center space-x-4">
                        <div className="p-2 bg-empire-gold/10 rounded-full">
                          <IconComponent className="h-5 w-5 text-empire-gold" />
                        </div>
                        <div>
                          <h3 className="font-medium text-empire-gold">{module.name}</h3>
                          <p className="text-sm text-empire-gold/60">{module.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge 
                          variant="outline" 
                          className={
                            module.status === 'running' 
                              ? "border-green-500/20 text-green-400"
                              : module.status === 'error'
                              ? "border-red-500/20 text-red-400"
                              : "border-yellow-500/20 text-yellow-400"
                          }
                        >
                          <div className={`w-2 h-2 rounded-full mr-1 ${
                            module.status === 'running' 
                              ? 'bg-green-400'
                              : module.status === 'error'
                              ? 'bg-red-400'
                              : 'bg-yellow-400'
                          }`}></div>
                          {module.status === 'running' ? 'Running' : 
                           module.status === 'error' ? 'Error' : 'Standby'}
                        </Badge>
                        <Button variant="ghost" size="sm">
                          <Settings className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )
                })
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity */}
        <Card className="bg-empire-darker/50 border-empire-gold/20">
          <CardHeader>
            <CardTitle className="text-empire-gold">Recent Activity</CardTitle>
            <CardDescription>
              Latest system events and requests
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {recentActivity.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-empire-gold/60">No recent activity</p>
              </div>
            ) : (
              recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-center space-x-3">
                  <div className={`w-2 h-2 rounded-full ${getActivityIcon(activity.type)}`}></div>
                  <div className="flex-1">
                    <p className="text-sm text-empire-gold">{activity.message}</p>
                    <p className="text-xs text-empire-gold/60">{activity.timestamp}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}