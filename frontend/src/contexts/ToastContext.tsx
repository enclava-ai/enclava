"use client"

import React, { createContext, useContext, useState, useCallback, useRef } from 'react'
import { generateShortId } from '@/lib/id-utils'

export interface ToastProps {
  id: string
  title?: string
  description?: string
  variant?: 'default' | 'destructive' | 'success' | 'warning'
  action?: React.ReactElement
  duration?: number
}

export interface ToastOptions extends Omit<ToastProps, 'id'> {
  duration?: number
}

interface ToastContextType {
  toasts: ToastProps[]
  toast: (options: ToastOptions) => () => void
  success: (title: string, description?: string, options?: Partial<ToastOptions>) => () => void
  error: (title: string, description?: string, options?: Partial<ToastOptions>) => () => void
  warning: (title: string, description?: string, options?: Partial<ToastOptions>) => () => void
  info: (title: string, description?: string, options?: Partial<ToastOptions>) => () => void
  dismiss: (id: string) => void
  clearAll: () => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastProps[]>([])
  const timeoutRefs = useRef<Map<string, NodeJS.Timeout>>(new Map())

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))

    // Clear timeout if exists
    const timeoutId = timeoutRefs.current.get(id)
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutRefs.current.delete(id)
    }
  }, [])

  const toast = useCallback((options: ToastOptions) => {
    const {
      duration = 5000,
      variant = 'default',
      ...props
    } = options

    // Generate unique ID using improved utility
    const id = generateShortId('toast')
    const toastWithId: ToastProps = {
      ...props,
      id,
      variant,
      duration
    }

    // Add to toasts array
    setToasts(prev => [...prev, toastWithId])

    // Auto-remove after specified duration
    if (duration > 0) {
      const timeoutId = setTimeout(() => {
        dismissToast(id)
      }, duration)

      timeoutRefs.current.set(id, timeoutId)
    }

    // Return dismiss function for manual control
    return () => dismissToast(id)
  }, [dismissToast])

  // Convenience methods for common toast types
  const success = useCallback((title: string, description?: string, options?: Partial<ToastOptions>) => {
    return toast({
      title,
      description,
      variant: 'success',
      ...options
    })
  }, [toast])

  const error = useCallback((title: string, description?: string, options?: Partial<ToastOptions>) => {
    return toast({
      title,
      description,
      variant: 'destructive',
      duration: 7000, // Errors should stay longer
      ...options
    })
  }, [toast])

  const warning = useCallback((title: string, description?: string, options?: Partial<ToastOptions>) => {
    return toast({
      title,
      description,
      variant: 'warning',
      ...options
    })
  }, [toast])

  const info = useCallback((title: string, description?: string, options?: Partial<ToastOptions>) => {
    return toast({
      title,
      description,
      variant: 'default',
      ...options
    })
  }, [toast])

  // Clear all toasts
  const clearAll = useCallback(() => {
    // Clear all timeouts
    timeoutRefs.current.forEach(timeoutId => clearTimeout(timeoutId))
    timeoutRefs.current.clear()

    setToasts([])
  }, [])

  const value: ToastContextType = {
    toasts,
    toast,
    success,
    error,
    warning,
    info,
    dismiss: dismissToast,
    clearAll,
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}