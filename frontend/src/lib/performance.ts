/**
 * Performance monitoring and optimization utilities
 */

import React from 'react'

export interface PerformanceMetric {
  name: string
  value: number
  timestamp: number
  metadata?: Record<string, any>
}

export interface PerformanceReport {
  metrics: PerformanceMetric[]
  summary: {
    averageResponseTime: number
    totalRequests: number
    errorRate: number
    slowestRequests: PerformanceMetric[]
  }
}

class PerformanceMonitor {
  private metrics: PerformanceMetric[] = []
  private maxMetrics = 1000 // Keep last 1000 metrics
  private enabled = process.env.NODE_ENV === 'development'

  /**
   * Start timing an operation
   */
  startTiming(name: string, metadata?: Record<string, any>): () => void {
    if (!this.enabled) {
      return () => {} // No-op in production
    }

    const startTime = performance.now()
    
    return () => {
      const duration = performance.now() - startTime
      this.recordMetric(name, duration, metadata)
    }
  }

  /**
   * Record a performance metric
   */
  recordMetric(name: string, value: number, metadata?: Record<string, any>): void {
    if (!this.enabled) return

    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      metadata
    }

    this.metrics.push(metric)
    
    // Keep only the most recent metrics
    if (this.metrics.length > this.maxMetrics) {
      this.metrics = this.metrics.slice(-this.maxMetrics)
    }

    // Log slow operations
    if (value > 1000) { // Slower than 1 second
    }
  }

  /**
   * Measure and track API calls
   */
  async trackApiCall<T>(
    name: string,
    apiCall: () => Promise<T>,
    metadata?: Record<string, any>
  ): Promise<T> {
    const endTiming = this.startTiming(`api_${name}`, metadata)
    
    try {
      const result = await apiCall()
      endTiming()
      return result
    } catch (error) {
      endTiming()
      this.recordMetric(`api_${name}_error`, 1, { 
        ...metadata, 
        error: error instanceof Error ? error.message : 'Unknown error'
      })
      throw error
    }
  }

  /**
   * Track React component render times
   */
  trackComponentRender(componentName: string, renderCount: number = 1): void {
    this.recordMetric(`render_${componentName}`, renderCount)
  }

  /**
   * Get performance report
   */
  getReport(): PerformanceReport {
    const apiMetrics = this.metrics.filter(m => m.name.startsWith('api_'))
    const errorMetrics = this.metrics.filter(m => m.name.includes('_error'))
    
    const totalRequests = apiMetrics.length
    const errorRate = totalRequests > 0 ? (errorMetrics.length / totalRequests) * 100 : 0
    
    const responseTimes = apiMetrics.map(m => m.value)
    const averageResponseTime = responseTimes.length > 0 
      ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length 
      : 0

    const slowestRequests = [...apiMetrics]
      .sort((a, b) => b.value - a.value)
      .slice(0, 10)

    return {
      metrics: this.metrics,
      summary: {
        averageResponseTime,
        totalRequests,
        errorRate,
        slowestRequests
      }
    }
  }

  /**
   * Clear all metrics
   */
  clear(): void {
    this.metrics = []
  }

  /**
   * Enable/disable monitoring
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled
  }

  /**
   * Export metrics for analysis
   */
  exportMetrics(): string {
    return JSON.stringify({
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
      metrics: this.metrics,
      summary: this.getReport().summary
    }, null, 2)
  }
}

// Global performance monitor instance
export const performanceMonitor = new PerformanceMonitor()

/**
 * React hook for component performance tracking
 */
export function usePerformanceTracking(componentName: string) {
  const [renderCount, setRenderCount] = React.useState(0)

  React.useEffect(() => {
    const newCount = renderCount + 1
    setRenderCount(newCount)
    performanceMonitor.trackComponentRender(componentName, newCount)
  })

  return {
    renderCount,
    trackOperation: (name: string, metadata?: Record<string, any>) => 
      performanceMonitor.startTiming(`${componentName}_${name}`, metadata),
    
    trackApiCall: <T>(name: string, apiCall: () => Promise<T>) =>
      performanceMonitor.trackApiCall(`${componentName}_${name}`, apiCall)
  }
}

/**
 * Debounce utility for performance optimization
 */
export function debounce<Args extends any[]>(
  func: (...args: Args) => void,
  delay: number
): (...args: Args) => void {
  let timeoutId: NodeJS.Timeout | null = null

  return (...args: Args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    timeoutId = setTimeout(() => {
      func.apply(null, args)
    }, delay)
  }
}

/**
 * Throttle utility for performance optimization
 */
export function throttle<Args extends any[]>(
  func: (...args: Args) => void,
  limit: number
): (...args: Args) => void {
  let inThrottle = false

  return (...args: Args) => {
    if (!inThrottle) {
      func.apply(null, args)
      inThrottle = true
      setTimeout(() => inThrottle = false, limit)
    }
  }
}

/**
 * Memoization utility with performance tracking
 */
export function memoizeWithTracking<Args extends any[], Return>(
  fn: (...args: Args) => Return,
  keyGenerator?: (...args: Args) => string
): (...args: Args) => Return {
  const cache = new Map<string, { result: Return; timestamp: number }>()
  const cacheTimeout = 5 * 60 * 1000 // 5 minutes
  
  return (...args: Args) => {
    const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args)
    const now = Date.now()
    
    // Check cache
    const cached = cache.get(key)
    if (cached && (now - cached.timestamp) < cacheTimeout) {
      performanceMonitor.recordMetric('memoize_hit', 1, { function: fn.name })
      return cached.result
    }
    
    // Compute result
    const endTiming = performanceMonitor.startTiming('memoize_compute', { function: fn.name })
    const result = fn(...args)
    endTiming()
    
    // Store in cache
    cache.set(key, { result, timestamp: now })
    performanceMonitor.recordMetric('memoize_miss', 1, { function: fn.name })
    
    // Clean up old entries
    if (cache.size > 100) {
      const entries = Array.from(cache.entries())
      entries
        .filter(([, value]) => (now - value.timestamp) > cacheTimeout)
        .forEach(([key]) => cache.delete(key))
    }
    
    return result
  }
}

/**
 * Web Vitals tracking
 */
export function trackWebVitals() {
  if (typeof window === 'undefined') return

  // Track Largest Contentful Paint
  if ('PerformanceObserver' in window) {
    try {
      new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.entryType === 'largest-contentful-paint') {
            performanceMonitor.recordMetric('lcp', entry.startTime)
          }
          if (entry.entryType === 'first-input') {
            performanceMonitor.recordMetric('fid', (entry as any).processingStart - entry.startTime)
          }
        })
      }).observe({ entryTypes: ['largest-contentful-paint', 'first-input'] })
    } catch (error) {
    }
  }

  // Track Cumulative Layout Shift
  if ('PerformanceObserver' in window) {
    try {
      let clsValue = 0
      new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value
            performanceMonitor.recordMetric('cls', clsValue)
          }
        })
      }).observe({ entryTypes: ['layout-shift'] })
    } catch (error) {
    }
  }
}