/**
 * Utility functions for error handling and user feedback
 */

export interface AppError {
  code: string
  message: string
  details?: string
  retryable?: boolean
}

export const ERROR_CODES = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  UNAUTHORIZED: 'UNAUTHORIZED',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  TIMEOUT_ERROR: 'TIMEOUT_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
} as const

/**
 * Converts various error types into standardized AppError format
 */
export function normalizeError(error: unknown): AppError {
  if (error instanceof Error) {
    // Network or fetch errors
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return {
        code: ERROR_CODES.NETWORK_ERROR,
        message: 'Unable to connect to server. Please check your internet connection.',
        retryable: true
      }
    }
    
    // Timeout errors
    if (error.name === 'AbortError' || error.message.includes('timeout')) {
      return {
        code: ERROR_CODES.TIMEOUT_ERROR,
        message: 'Request timed out. Please try again.',
        retryable: true
      }
    }
    
    return {
      code: ERROR_CODES.UNKNOWN_ERROR,
      message: error.message || 'An unexpected error occurred',
      details: error.stack,
      retryable: false
    }
  }
  
  if (typeof error === 'string') {
    return {
      code: ERROR_CODES.UNKNOWN_ERROR,
      message: error,
      retryable: false
    }
  }
  
  return {
    code: ERROR_CODES.UNKNOWN_ERROR,
    message: 'An unknown error occurred',
    retryable: false
  }
}

/**
 * Handles HTTP response errors
 */
export async function handleHttpError(response: Response): Promise<AppError> {
  let errorDetails: string
  
  try {
    const errorData = await response.json()
    errorDetails = errorData.error || errorData.message || 'Unknown error'
  } catch {
    try {
      // Use the cloned response for text reading since original body was consumed
      const responseClone = response.clone()
      errorDetails = await responseClone.text()
    } catch {
      errorDetails = `HTTP ${response.status} error`
    }
  }
  
  switch (response.status) {
    case 401:
      return {
        code: ERROR_CODES.UNAUTHORIZED,
        message: 'You need to log in to continue',
        details: errorDetails,
        retryable: false
      }
    
    case 400:
      return {
        code: ERROR_CODES.VALIDATION_ERROR,
        message: 'Invalid request. Please check your input.',
        details: errorDetails,
        retryable: false
      }
    
    case 429:
      return {
        code: ERROR_CODES.SERVER_ERROR,
        message: 'Too many requests. Please wait a moment and try again.',
        details: errorDetails,
        retryable: true
      }
    
    case 500:
    case 502:
    case 503:
    case 504:
      return {
        code: ERROR_CODES.SERVER_ERROR,
        message: 'Server error. Please try again in a moment.',
        details: errorDetails,
        retryable: true
      }
    
    default:
      return {
        code: ERROR_CODES.SERVER_ERROR,
        message: `Request failed (${response.status}): ${errorDetails}`,
        details: errorDetails,
        retryable: response.status >= 500
      }
  }
}

/**
 * Retry wrapper with exponential backoff
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxAttempts?: number
    initialDelay?: number
    maxDelay?: number
    backoffMultiplier?: number
  } = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    initialDelay = 1000,
    maxDelay = 10000,
    backoffMultiplier = 2
  } = options
  
  let lastError: unknown
  let delay = initialDelay
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      
      const appError = normalizeError(error)
      
      // Don't retry non-retryable errors
      if (!appError.retryable || attempt === maxAttempts) {
        throw error
      }
      
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, delay))
      delay = Math.min(delay * backoffMultiplier, maxDelay)
    }
  }
  
  throw lastError
}