"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  DollarSign, 
  AlertTriangle, 
  TrendingUp, 
  Calendar, 
  RefreshCw,
  Clock,
  BarChart3,
  Target,
  Zap,
  AlertCircle
} from 'lucide-react'

interface BudgetData {
  id: string
  user_id: string
  name: string
  limit_amount: number
  current_usage: number
  time_period: 'daily' | 'weekly' | 'monthly' | 'yearly'
  warning_threshold: number
  auto_renew: boolean
  created_at: string
  updated_at: string
  period_start: string
  period_end: string
  is_active: boolean
}

interface BudgetStatus {
  budgets: BudgetData[]
  total_usage: number
  warnings: string[]
  projections: {
    daily_burn_rate: number
    projected_monthly: number
    days_remaining: number
  }
}

export default function BudgetMonitor() {
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const fetchBudgetStatus = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/v1/llm/budget/status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token') || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsImlzX3N1cGVydXNlciI6dHJ1ZSwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzU1ODQ1ODg3fQ.lrYJpoA2fUCvY97RX1Mpli4qtIhuDZjQ_LbDlqxTl6I'}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch budget status')
      }

      const data = await response.json()
      setBudgetStatus(data)
      setError(null)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBudgetStatus()
    const interval = setInterval(fetchBudgetStatus, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const getUtilizationPercentage = (usage: number, limit: number): number => {
    return Math.min((usage / limit) * 100, 100)
  }

  const getBudgetStatusColor = (usage: number, limit: number, warningThreshold: number): string => {
    const percentage = getUtilizationPercentage(usage, limit)
    if (percentage >= 100) return 'destructive'
    if (percentage >= warningThreshold) return 'default'
    return 'secondary'
  }

  const getBudgetStatusText = (usage: number, limit: number, warningThreshold: number): string => {
    const percentage = getUtilizationPercentage(usage, limit)
    if (percentage >= 100) return 'Exceeded'
    if (percentage >= warningThreshold) return 'Warning'
    return 'Active'
  }

  const formatTimeRemaining = (days: number): string => {
    if (days < 1) return 'Less than 1 day'
    if (days < 7) return `${Math.ceil(days)} days`
    if (days < 30) return `${Math.ceil(days / 7)} weeks`
    return `${Math.ceil(days / 30)} months`
  }

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount)
  }

  const getPeriodIcon = (period: string) => {
    switch (period) {
      case 'daily': return <Clock className="h-4 w-4" />
      case 'weekly': return <Calendar className="h-4 w-4" />
      case 'monthly': return <BarChart3 className="h-4 w-4" />
      case 'yearly': return <TrendingUp className="h-4 w-4" />
      default: return <Target className="h-4 w-4" />
    }
  }

  if (loading && !budgetStatus) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Budget Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin" />
            <span className="ml-2">Loading budget status...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Budget Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button onClick={fetchBudgetStatus} className="mt-4">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!budgetStatus) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Budget Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No budget data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Budget Overview
              </CardTitle>
              <CardDescription>
                Real-time spending monitoring and projections
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Last updated: {lastRefresh.toLocaleTimeString()}
              </span>
              <Button variant="outline" size="sm" onClick={fetchBudgetStatus} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{formatCurrency(budgetStatus.total_usage)}</div>
              <div className="text-sm text-muted-foreground">Total Usage</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{formatCurrency(budgetStatus.projections.daily_burn_rate)}</div>
              <div className="text-sm text-muted-foreground">Daily Burn Rate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{formatTimeRemaining(budgetStatus.projections.days_remaining)}</div>
              <div className="text-sm text-muted-foreground">Budget Runway</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Warnings */}
      {budgetStatus.warnings.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <div className="font-medium mb-2">Budget Warnings:</div>
            <ul className="list-disc list-inside space-y-1">
              {budgetStatus.warnings.map((warning, index) => (
                <li key={index} className="text-sm">{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Active Budgets */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Active Budgets
          </CardTitle>
          <CardDescription>
            Current spending against configured budget limits
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px]">
            <div className="space-y-4">
              {budgetStatus.budgets.map((budget) => {
                const utilization = getUtilizationPercentage(budget.current_usage, budget.limit_amount)
                const statusColor = getBudgetStatusColor(budget.current_usage, budget.limit_amount, budget.warning_threshold)
                const statusText = getBudgetStatusText(budget.current_usage, budget.limit_amount, budget.warning_threshold)
                
                return (
                  <div key={budget.id} className="border rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getPeriodIcon(budget.time_period)}
                        <h3 className="font-semibold">{budget.name}</h3>
                        <Badge variant={statusColor as any}>{statusText}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground capitalize">
                        {budget.time_period}
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Usage: {formatCurrency(budget.current_usage)}</span>
                        <span>Limit: {formatCurrency(budget.limit_amount)}</span>
                      </div>
                      <Progress value={utilization} className="h-2" />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{utilization.toFixed(1)}% used</span>
                        <span>{formatCurrency(budget.limit_amount - budget.current_usage)} remaining</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-4">
                        <span>Warning at {budget.warning_threshold}%</span>
                        {budget.auto_renew && (
                          <Badge variant="outline" className="text-xs">
                            Auto-renew
                          </Badge>
                        )}
                      </div>
                      <div className="text-muted-foreground">
                        {new Date(budget.period_start).toLocaleDateString()} - {new Date(budget.period_end).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Projections */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Spending Projections
          </CardTitle>
          <CardDescription>
            Forecasts based on current usage patterns
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-2">Daily Burn Rate</h4>
                <div className="text-2xl font-bold">{formatCurrency(budgetStatus.projections.daily_burn_rate)}</div>
                <p className="text-sm text-muted-foreground">
                  Average daily spending based on recent usage
                </p>
              </div>
              
              <Separator />
              
              <div>
                <h4 className="font-medium mb-2">Monthly Projection</h4>
                <div className="text-2xl font-bold">{formatCurrency(budgetStatus.projections.projected_monthly)}</div>
                <p className="text-sm text-muted-foreground">
                  Estimated monthly cost at current rate
                </p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-2">Budget Runway</h4>
                <div className="text-2xl font-bold">{formatTimeRemaining(budgetStatus.projections.days_remaining)}</div>
                <p className="text-sm text-muted-foreground">
                  Time until budget limits are reached
                </p>
              </div>
              
              <Separator />
              
              <div>
                <h4 className="font-medium mb-2">Efficiency Metrics</h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm">Active Budgets</span>
                    <span className="text-sm font-medium">{budgetStatus.budgets.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Avg. Utilization</span>
                    <span className="text-sm font-medium">
                      {(budgetStatus.budgets.reduce((sum, b) => sum + getUtilizationPercentage(b.current_usage, b.limit_amount), 0) / budgetStatus.budgets.length).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">Warnings</span>
                    <span className="text-sm font-medium">{budgetStatus.warnings.length}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}