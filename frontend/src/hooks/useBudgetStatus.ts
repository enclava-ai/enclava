"use client"

import { useState, useEffect } from 'react'
import { apiClient } from '@/lib/api-client'

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

export function useBudgetStatus(autoRefresh = true, refreshInterval = 30000) {
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const fetchBudgetStatus = async () => {
    try {
      setLoading(true)

      const data = await apiClient.get('/api-internal/v1/llm/budget/status')
      setBudgetStatus(data)
      setError(null)
      setLastRefresh(new Date())
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      console.error('Budget status fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  const refresh = () => {
    fetchBudgetStatus()
  }

  useEffect(() => {
    fetchBudgetStatus()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(fetchBudgetStatus, refreshInterval)
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])

  const getWarningCount = (): number => {
    return budgetStatus?.warnings?.length || 0
  }

  const getTotalBudgetUtilization = (): number => {
    if (!budgetStatus?.budgets || !Array.isArray(budgetStatus.budgets) || budgetStatus.budgets.length === 0) return 0
    
    const totalUsage = budgetStatus.budgets.reduce((sum, budget) => sum + (budget.current_usage || 0), 0)
    const totalLimit = budgetStatus.budgets.reduce((sum, budget) => sum + (budget.limit_amount || 0), 0)
    
    return totalLimit > 0 ? (totalUsage / totalLimit) * 100 : 0
  }

  const hasWarnings = (): boolean => {
    return getWarningCount() > 0
  }

  const isOverBudget = (): boolean => {
    if (!budgetStatus?.budgets || !Array.isArray(budgetStatus.budgets)) return false
    return budgetStatus.budgets.some(budget => (budget.current_usage || 0) >= (budget.limit_amount || 0))
  }

  return {
    budgetStatus,
    loading,
    error,
    lastRefresh,
    refresh,
    getWarningCount,
    getTotalBudgetUtilization,
    hasWarnings,
    isOverBudget
  }
}