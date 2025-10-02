/**
 * Validation utilities with TypeScript support
 */

import type { ValidationRule, ValidationRules, ValidationResult } from '@/types/chatbot'

/**
 * Validates a single field against its rules
 */
export function validateField<T>(
  value: T, 
  rules: ValidationRule<T> = {}
): string | null {
  const {
    required = false,
    minLength,
    maxLength,
    min,
    max,
    pattern,
    custom
  } = rules

  // Required validation
  if (required) {
    if (value === null || value === undefined) {
      return 'This field is required'
    }
    if (typeof value === 'string' && value.trim().length === 0) {
      return 'This field is required'
    }
    if (Array.isArray(value) && value.length === 0) {
      return 'This field is required'
    }
  }

  // Skip other validations if value is empty and not required
  if (!required && (value === null || value === undefined || value === '')) {
    return null
  }

  // String length validation
  if (typeof value === 'string') {
    if (minLength !== undefined && value.length < minLength) {
      return `Must be at least ${minLength} characters`
    }
    if (maxLength !== undefined && value.length > maxLength) {
      return `Must be no more than ${maxLength} characters`
    }
  }

  // Number range validation
  if (typeof value === 'number') {
    if (min !== undefined && value < min) {
      return `Must be at least ${min}`
    }
    if (max !== undefined && value > max) {
      return `Must be no more than ${max}`
    }
  }

  // Array length validation
  if (Array.isArray(value)) {
    if (minLength !== undefined && value.length < minLength) {
      return `Must have at least ${minLength} items`
    }
    if (maxLength !== undefined && value.length > maxLength) {
      return `Must have no more than ${maxLength} items`
    }
  }

  // Pattern validation
  if (typeof value === 'string' && pattern) {
    if (!pattern.test(value)) {
      return 'Invalid format'
    }
  }

  // Custom validation
  if (custom) {
    return custom(value)
  }

  return null
}

/**
 * Validates an entire object against validation rules
 */
export function validateObject<T extends Record<string, any>>(
  obj: T,
  rules: ValidationRules<T>
): ValidationResult {
  const errors: Record<string, string> = {}

  for (const [key, rule] of Object.entries(rules)) {
    if (rule && key in obj) {
      const error = validateField(obj[key], rule as ValidationRule<any>)
      if (error) {
        errors[key] = error
      }
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

/**
 * Common validation rules for chatbot fields
 */
export const chatbotValidationRules = {
  name: {
    required: true,
    minLength: 1,
    maxLength: 100,
    custom: (value: string) => {
      if (!/^[a-zA-Z0-9\s\-_]+$/.test(value)) {
        return 'Name can only contain letters, numbers, spaces, hyphens, and underscores'
      }
      return null
    }
  },
  
  model: {
    required: true,
    minLength: 1,
    maxLength: 100
  },
  
  system_prompt: {
    maxLength: 4000,
    custom: (value: string) => {
      if (value && value.trim().length === 0) {
        return 'System prompt cannot be only whitespace'
      }
      return null
    }
  },
  
  temperature: {
    required: true,
    min: 0,
    max: 2
  },
  
  max_tokens: {
    required: true,
    min: 1,
    max: 4000
  },
  
  memory_length: {
    required: true,
    min: 1,
    max: 50
  },
  
  rag_top_k: {
    required: true,
    min: 1,
    max: 20
  },
  
  fallback_responses: {
    minLength: 1,
    maxLength: 10,
    custom: (responses: string[]) => {
      if (responses.some(r => !r || r.trim().length === 0)) {
        return 'All fallback responses must be non-empty'
      }
      return null
    }
  }
} as const

/**
 * Email validation rule
 */
export const emailRule: ValidationRule<string> = {
  pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  custom: (value: string) => {
    if (value && !emailRule.pattern?.test(value)) {
      return 'Please enter a valid email address'
    }
    return null
  }
}

/**
 * URL validation rule
 */
export const urlRule: ValidationRule<string> = {
  pattern: /^https?:\/\/.+/,
  custom: (value: string) => {
    if (value && !urlRule.pattern?.test(value)) {
      return 'Please enter a valid URL starting with http:// or https://'
    }
    return null
  }
}

/**
 * Username validation rule
 */
export const usernameRule: ValidationRule<string> = {
  minLength: 3,
  maxLength: 30,
  pattern: /^[a-zA-Z0-9_-]+$/,
  custom: (value: string) => {
    if (value && !usernameRule.pattern?.test(value)) {
      return 'Username can only contain letters, numbers, hyphens, and underscores'
    }
    return null
  }
}

/**
 * Password validation rule
 */
export const passwordRule: ValidationRule<string> = {
  minLength: 8,
  maxLength: 128,
  custom: (value: string) => {
    if (!value) return null
    
    if (!/(?=.*[a-z])/.test(value)) {
      return 'Password must contain at least one lowercase letter'
    }
    if (!/(?=.*[A-Z])/.test(value)) {
      return 'Password must contain at least one uppercase letter'
    }
    if (!/(?=.*\d)/.test(value)) {
      return 'Password must contain at least one number'
    }
    if (!/(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\?])/.test(value)) {
      return 'Password must contain at least one special character'
    }
    
    return null
  }
}

/**
 * Utility to create conditional validation rules
 */
export function when<T>(
  condition: (obj: any) => boolean,
  rules: ValidationRule<T>
): ValidationRule<T> {
  return {
    ...rules,
    custom: (value: T, obj?: any) => {
      if (!condition(obj)) {
        return null
      }
      
      const originalCustom = rules.custom
      if (originalCustom) {
        return originalCustom(value, obj)
      }
      
      return validateField(value, { ...rules, custom: undefined })
    }
  }
}

/**
 * Debounced validation for real-time form validation
 */
export function createDebouncedValidator<T extends Record<string, any>>(
  rules: ValidationRules<T>,
  delay: number = 300
) {
  let timeoutId: NodeJS.Timeout | null = null
  
  return (obj: T, callback: (result: ValidationResult) => void) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    timeoutId = setTimeout(() => {
      const result = validateObject(obj, rules)
      callback(result)
    }, delay)
  }
}