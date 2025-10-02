/**
 * URL utilities for handling HTTP/HTTPS protocol detection
 */

/**
 * Get the base URL with proper protocol detection
 * This ensures API calls use the same protocol as the page was loaded with
 */
export const getBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Client-side: detect current protocol
    const protocol = window.location.protocol === 'https:' ? 'https' : 'http'
    const host = process.env.NEXT_PUBLIC_BASE_URL || window.location.hostname
    return `${protocol}://${host}`
  }

  // Server-side: default based on environment
  const protocol = process.env.NODE_ENV === 'production' ? 'https' : 'http'
  return `${protocol}://${process.env.NEXT_PUBLIC_BASE_URL || 'localhost'}`
}

/**
 * Get the API URL with proper protocol detection
 * This is the main function that should be used for all API calls
 */
export const getApiUrl = (): string => {
  if (typeof window !== 'undefined') {
    // Client-side: use the same protocol as the current page
    const protocol = window.location.protocol.slice(0, -1) // Remove ':' from 'https:'
    const host = window.location.hostname
    return `${protocol}://${host}`
  }

  // Server-side: default to HTTP for internal requests
  return `http://${process.env.NEXT_PUBLIC_BASE_URL || 'localhost'}`
}

/**
 * Get the internal API URL for authenticated endpoints
 * This ensures internal API calls use the same protocol as the page
 */
export const getInternalApiUrl = (): string => {
  const baseUrl = getApiUrl()
  return `${baseUrl}/api-internal`
}

/**
 * Get the public API URL for external client endpoints
 * This ensures public API calls use the same protocol as the page
 */
export const getPublicApiUrl = (): string => {
  const baseUrl = getApiUrl()
  return `${baseUrl}/api`
}

/**
 * Helper function to make API calls with proper protocol
 */
export const apiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const baseUrl = getApiUrl()
  const url = `${baseUrl}${endpoint}`

  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
}

/**
 * Helper function for internal API calls
 */
export const internalApiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const url = `${getInternalApiUrl()}${endpoint}`

  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
}

/**
 * Helper function for public API calls
 */
export const publicApiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const url = `${getPublicApiUrl()}${endpoint}`

  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
}