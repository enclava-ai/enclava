export const config = {
  getPublicApiUrl(): string {
    if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_BASE_URL) {
      return process.env.NEXT_PUBLIC_BASE_URL
    }
    if (typeof window !== 'undefined') {
      return window.location.origin
    }
    return 'http://localhost:3000'
  },
  getAppName(): string {
    return process.env.NEXT_PUBLIC_APP_NAME || 'Enclava'
  },
}
