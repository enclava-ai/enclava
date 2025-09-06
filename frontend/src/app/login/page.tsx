"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/contexts/AuthContext"

// Force dynamic rendering for authentication
export const dynamic = 'force-dynamic'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { Eye, EyeOff, Shield } from "lucide-react"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attemptCount, setAttemptCount] = useState(0)
  const [isLocked, setIsLocked] = useState(false)
  const { login } = useAuth()
  const router = useRouter()
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Check if account is temporarily locked
    if (isLocked) {
      toast({
        title: "Account Temporarily Locked",
        description: "Too many failed attempts. Please try again in 30 seconds.",
        variant: "destructive",
      })
      return
    }
    
    setIsLoading(true)
    setError(null) // Clear any previous errors

    try {
      await login(email, password)
      toast({
        title: "Login successful",
        description: "Welcome to Enclava",
      })
      // Reset attempt count on successful login
      setAttemptCount(0)
      // Add a small delay to ensure token is fully stored and propagated
      setTimeout(() => {
        // For now, do a full page reload to ensure everything is initialized with the new token
        window.location.href = "/dashboard"
      }, 100)
    } catch (error) {
      const newAttemptCount = attemptCount + 1
      setAttemptCount(newAttemptCount)
      
      // Lock account after 5 failed attempts
      if (newAttemptCount >= 5) {
        setIsLocked(true)
        setError("Too many failed attempts. Account temporarily locked.")
        toast({
          title: "Account Locked",
          description: "Too many failed login attempts. Please wait 30 seconds before trying again.",
          variant: "destructive",
        })
        
        // Unlock after 30 seconds
        setTimeout(() => {
          setIsLocked(false)
          setAttemptCount(0)
          setError(null)
        }, 30000)
      } else {
        // Set error message for display in the form
        const remainingAttempts = 5 - newAttemptCount
        setError(`Invalid credentials. ${remainingAttempts} attempt${remainingAttempts === 1 ? '' : 's'} remaining.`)
        
        // Also show toast for additional feedback
        toast({
          title: "Authentication Failed",
          description: `Invalid credentials. ${remainingAttempts} attempt${remainingAttempts === 1 ? '' : 's'} remaining before temporary lock.`,
          variant: "destructive",
        })
      }
      
      // Clear password field for security
      setPassword("")
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-empire-dark to-empire-darker p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-empire-gold/10 rounded-full">
              <Shield className="h-8 w-8 text-empire-gold" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold text-empire-gold">
            Enclava
          </CardTitle>
          <CardDescription>
            Sign in to your secure AI platform
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20">
                <p className="text-sm text-red-500 flex items-center gap-2">
                  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  {error}
                </p>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setError(null) // Clear error when user starts typing
                }}
                required
                className={`bg-empire-darker/50 border-empire-gold/20 focus:border-empire-gold ${
                  error ? 'border-red-500/50' : ''
                }`}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setError(null) // Clear error when user starts typing
                  }}
                  required
                  className={`bg-empire-darker/50 border-empire-gold/20 focus:border-empire-gold pr-10 ${
                    error ? 'border-red-500/50' : ''
                  }`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-empire-gold/60" />
                  ) : (
                    <Eye className="h-4 w-4 text-empire-gold/60" />
                  )}
                </Button>
              </div>
            </div>
            <Button
              type="submit"
              className="w-full bg-empire-gold hover:bg-empire-gold/90 text-empire-dark disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLoading || isLocked}
            >
              {isLocked ? "Account Locked (30s)" : isLoading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}