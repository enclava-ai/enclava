"use client"

import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useState } from "react"
import { apiClient } from "@/lib/api-client"
import { tokenManager } from "@/lib/token-manager"

export default function TestAuthPage() {
  const { user, logout, isAuthenticated } = useAuth()
  const [testResult, setTestResult] = useState<string>("")
  const [isLoading, setIsLoading] = useState(false)

  const testApiCall = async () => {
    setIsLoading(true)
    try {
      const result = await apiClient.get('/api-internal/v1/auth/me')
      setTestResult(`API call successful! User: ${JSON.stringify(result, null, 2)}`)
    } catch (error) {
      setTestResult(`API call failed: ${error}`)
    }
    setIsLoading(false)
  }

  const getTokenInfo = () => {
    const expiry = tokenManager.getTokenExpiry()
    const refreshExpiry = tokenManager.getRefreshTokenExpiry()

    if (!expiry.access_token_expiry) return "No token"

    const now = new Date()
    const accessTimeUntilExpiry = Math.floor((expiry.access_token_expiry - now.getTime() / 1000))
    const refreshTimeUntilExpiry = refreshExpiry ? Math.floor((refreshExpiry - now.getTime() / 1000)) : null

    return `
Access token expires in: ${Math.floor(accessTimeUntilExpiry / 60)} minutes ${accessTimeUntilExpiry % 60} seconds
Refresh token expires in: ${refreshTimeUntilExpiry ? `${Math.floor(refreshTimeUntilExpiry / 60)} minutes ${refreshTimeUntilExpiry % 60} seconds` : 'N/A'}
Access token expiry: ${new Date(expiry.access_token_expiry * 1000).toLocaleString()}
Refresh token expiry: ${refreshExpiry ? new Date(refreshExpiry * 1000).toLocaleString() : 'N/A'}
Authenticated: ${tokenManager.isAuthenticated()}
    `
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">Authentication Test Page</h1>
      
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Current User</CardTitle>
            <CardDescription>Logged in user information</CardDescription>
          </CardHeader>
          <CardContent>
            {user ? (
              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded">
                {JSON.stringify(user, null, 2)}
              </pre>
            ) : (
              <p>Not logged in</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Token Information</CardTitle>
            <CardDescription>Access token details and expiry</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded text-sm">
              {getTokenInfo()}
            </pre>
            {isAuthenticated && (
              <p className="mt-2 text-sm text-green-600">
                Auto-refresh enabled - tokens will refresh automatically
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API Test</CardTitle>
            <CardDescription>Test authenticated API calls</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Button 
                onClick={testApiCall} 
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? "Testing..." : "Test API Call"}
              </Button>
              
              {testResult && (
                <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded text-sm">
                  {testResult}
                </pre>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Auto-Refresh Test</CardTitle>
            <CardDescription>Instructions to test auto-refresh</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <p>1. Watch the "Token expires in" countdown above</p>
              <p>2. When it reaches ~1 minute, the token will auto-refresh</p>
              <p>3. You'll see the expiry time jump to 30 minutes again</p>
              <p>4. API calls will continue working without re-login</p>
              <p className="mt-4 font-semibold">Current token lifetime: 30 minutes</p>
              <p className="font-semibold">Refresh token lifetime: 7 days</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <Button 
              onClick={logout} 
              variant="destructive"
              className="w-full"
            >
              Logout
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
