"use client"

import { useAuth } from "@/contexts/AuthContext"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

// Force dynamic rendering for authentication
export const dynamic = 'force-dynamic'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Shield, Zap, Cpu, Lock, Settings, BarChart3 } from "lucide-react"

export default function HomePage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && user) {
      router.push("/dashboard")
    }
  }, [user, isLoading, router])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
      </div>
    )
  }

  if (user) {
    return null // Will redirect to dashboard
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-empire-dark to-empire-darker">
      {/* Header */}
      <header className="border-b border-empire-gold/20">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-empire-gold rounded-lg flex items-center justify-center">
                <Shield className="w-5 h-5 text-empire-dark" />
              </div>
              <span className="text-xl font-bold text-empire-gold">AI Gateway</span>
            </div>
            <nav className="hidden md:flex items-center space-x-6">
              <a href="#features" className="text-empire-gold/60 hover:text-empire-gold">
                Features
              </a>
              <a href="#modules" className="text-empire-gold/60 hover:text-empire-gold">
                Modules
              </a>
              <Button 
                variant="ghost" 
                onClick={() => router.push("/login")}
                className="text-empire-gold/60 hover:text-empire-gold"
              >
                Login
              </Button>
              <Button 
                onClick={() => router.push("/login")}
                className="bg-empire-gold text-empire-dark hover:bg-empire-gold/90"
              >
                Get Started
              </Button>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20">
        <div className="container mx-auto px-4 text-center">
          <div className="max-w-3xl mx-auto">
            <Badge className="mb-6 bg-empire-gold/10 text-empire-gold border-empire-gold/20" variant="outline">
              AI Processing Platform
            </Badge>
            <h1 className="text-4xl md:text-6xl font-bold mb-6 text-empire-gold">
              Secure AI Gateway with{' '}
              <span className="bg-gradient-to-r from-empire-gold to-empire-gold/80 bg-clip-text text-transparent">
                Secure Computing
              </span>
            </h1>
            <p className="text-xl text-empire-gold/60 mb-8">
              Enterprise-grade AI processing platform with plugin-based architecture, 
              TEE integration, and comprehensive security controls. Process sensitive data 
              with confidence.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button 
                size="lg" 
                onClick={() => router.push("/login")}
                className="bg-empire-gold text-empire-dark hover:bg-empire-gold/90"
              >
                Start Free Trial
              </Button>
              <Button 
                size="lg" 
                variant="outline"
                onClick={() => router.push("/login")}
                className="border-empire-gold text-empire-gold hover:bg-empire-gold/10"
              >
                Try Playground
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-empire-darker/50">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4 text-empire-gold">Powerful Features</h2>
            <p className="text-empire-gold/60 max-w-2xl mx-auto">
              Built for enterprise security, scalability, and developer experience
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <Shield className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">Confidential Computing</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Process sensitive data in Trusted Execution Environments (TEE) 
                  with hardware-level security guarantees
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <Zap className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">Multi-LLM Support</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Unified API for OpenAI, Anthropic, Google, and other providers 
                  with intelligent routing and fallback
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <Cpu className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">Plugin Architecture</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Extensible module system with interceptor chains for 
                  custom processing, caching, and analytics
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <Lock className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">RBAC & API Keys</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Granular permissions, API key management, and comprehensive 
                  audit logging for enterprise compliance
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <Settings className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">Budget Controls</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Real-time usage tracking, budget enforcement, and 
                  automatic spending controls with detailed analytics
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <div className="w-12 h-12 bg-empire-gold/10 rounded-lg flex items-center justify-center mb-4">
                  <BarChart3 className="w-6 h-6 text-empire-gold" />
                </div>
                <CardTitle className="text-empire-gold">Analytics & Monitoring</CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Comprehensive metrics, performance monitoring, and 
                  real-time dashboards for operational insights
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* Modules Section */}
      <section id="modules" className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4 text-empire-gold">Available Modules</h2>
            <p className="text-empire-gold/60 max-w-2xl mx-auto">
              Extend your AI gateway with powerful modules for enhanced functionality
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-empire-gold">
                  <Badge variant="secondary" className="bg-empire-gold/10 text-empire-gold">Core</Badge>
                  RAG Module
                </CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Retrieval-Augmented Generation with vector storage and semantic search
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-empire-gold/60 space-y-1">
                  <li>• Qdrant vector database integration</li>
                  <li>• Document chunking and embedding</li>
                  <li>• Semantic search capabilities</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-empire-gold">
                  <Badge variant="secondary" className="bg-empire-gold/10 text-empire-gold">Core</Badge>
                  Cache Module
                </CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Intelligent caching with Redis for improved performance
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-empire-gold/60 space-y-1">
                  <li>• Response caching strategies</li>
                  <li>• TTL and invalidation policies</li>
                  <li>• Performance optimization</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="bg-empire-darker/50 border-empire-gold/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-empire-gold">
                  <Badge variant="secondary" className="bg-empire-gold/10 text-empire-gold">Core</Badge>
                  Analytics Module
                </CardTitle>
                <CardDescription className="text-empire-gold/60">
                  Comprehensive tracking and performance analytics
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-empire-gold/60 space-y-1">
                  <li>• Request/response tracking</li>
                  <li>• Performance metrics</li>
                  <li>• Usage analytics</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-empire-gold/20 py-12">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-2 mb-4 md:mb-0">
              <div className="w-6 h-6 bg-empire-gold rounded flex items-center justify-center">
                <Shield className="w-4 h-4 text-empire-dark" />
              </div>
              <span className="font-semibold text-empire-gold">AI Gateway</span>
            </div>
            <div className="flex items-center space-x-6 text-sm text-empire-gold/60">
              <a href="/docs" className="hover:text-empire-gold">Documentation</a>
              <a href="/support" className="hover:text-empire-gold">Support</a>
              <a href="/privacy" className="hover:text-empire-gold">Privacy</a>
              <a href="/terms" className="hover:text-empire-gold">Terms</a>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-empire-gold/20 text-center text-sm text-empire-gold/60">
            <p>&copy; 2024 AI Gateway. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}