"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Shield, Lock, Activity, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react'

interface ConfidentialityReport {
  report_timestamp: string
  confidence_score: number
  status: string
  components: {
    confidentiality_status: any
    encryption_metrics: any
    security_audit: any
    connection_test: any
    proxy_status: any
  }
  assurances: string[]
  recommendations: Array<{
    priority: string
    issue: string
    action: string
  }>
}

interface ConfidentialityDashboardProps {
  className?: string
}

export const ConfidentialityDashboard: React.FC<ConfidentialityDashboardProps> = ({ 
  className 
}) => {
  const [report, setReport] = useState<ConfidentialityReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchConfidentialityReport = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch('/api/v1/tee/confidentiality-report', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('api_key')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch confidentiality report: ${response.status}`)
      }

      const data = await response.json()
      
      if (data.success) {
        setReport(data.data)
        setLastUpdated(new Date())
      } else {
        throw new Error('Failed to get confidentiality report')
      }
    } catch (err) {
      console.error('Error fetching confidentiality report:', err)
      setError(err instanceof Error ? err.message : 'Unknown error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConfidentialityReport()
    
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchConfidentialityReport, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'fully_protected':
        return 'text-green-600 bg-green-100'
      case 'well_protected':
        return 'text-green-600 bg-green-100'
      case 'adequately_protected':
        return 'text-yellow-600 bg-yellow-100'
      case 'partially_protected':
        return 'text-orange-600 bg-orange-100'
      case 'at_risk':
        return 'text-red-600 bg-red-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'fully_protected':
      case 'well_protected':
        return <CheckCircle className="w-4 h-4" />
      case 'adequately_protected':
        return <Shield className="w-4 h-4" />
      case 'partially_protected':
      case 'at_risk':
        return <AlertTriangle className="w-4 h-4" />
      default:
        return <Activity className="w-4 h-4" />
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'critical':
        return 'text-red-600 bg-red-100'
      case 'high':
        return 'text-orange-600 bg-orange-100'
      case 'medium':
        return 'text-yellow-600 bg-yellow-100'
      case 'low':
        return 'text-blue-600 bg-blue-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  if (loading) {
    return (
      <div className={`space-y-4 ${className}`}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Confidentiality Dashboard
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-500">Loading confidentiality report...</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className={`space-y-4 ${className}`}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Confidentiality Dashboard
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {error || 'Failed to load confidentiality report. Please try again.'}
              </AlertDescription>
            </Alert>
            <Button 
              onClick={fetchConfidentialityReport} 
              className="mt-4"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5" />
                Confidentiality Dashboard
              </CardTitle>
              <CardDescription>
                Real-time confidentiality protection status and assurances
              </CardDescription>
            </div>
            <Button 
              onClick={fetchConfidentialityReport} 
              variant="outline"
              size="sm"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Overall Status */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {getStatusIcon(report.status)}
                <span className="font-medium">Protection Status</span>
              </div>
              <Badge className={getStatusColor(report.status)}>
                {report.status.replace('_', ' ').toUpperCase()}
              </Badge>
            </div>
            
            {/* Confidence Score */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                <span className="font-medium">Confidence Score</span>
              </div>
              <div className="space-y-1">
                <Progress value={report.confidence_score} className="h-2" />
                <span className="text-sm text-gray-500">
                  {report.confidence_score}% confident
                </span>
              </div>
            </div>
            
            {/* Last Updated */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                <span className="font-medium">Last Updated</span>
              </div>
              <span className="text-sm text-gray-600">
                {lastUpdated?.toLocaleString()}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Information Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="assurances">Assurances</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="recommendations">Actions</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Connection Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Proxy Connection</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span>Status</span>
                    <Badge className={
                      report.components.connection_test?.connected 
                        ? "text-green-600 bg-green-100" 
                        : "text-red-600 bg-red-100"
                    }>
                      {report.components.connection_test?.connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </div>
                  {report.components.connection_test?.response_time_ms && (
                    <div className="flex items-center justify-between">
                      <span>Response Time</span>
                      <span className="text-sm font-mono">
                        {report.components.connection_test.response_time_ms}ms
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span>TLS Enabled</span>
                    <Badge className={
                      report.components.connection_test?.tls_enabled 
                        ? "text-green-600 bg-green-100" 
                        : "text-yellow-600 bg-yellow-100"
                    }>
                      {report.components.connection_test?.tls_enabled ? 'Yes' : 'No'}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Encryption Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Encryption</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span>Status</span>
                    <Badge className={
                      report.components.encryption_metrics?.encryption_strength === 'strong'
                        ? "text-green-600 bg-green-100"
                        : "text-yellow-600 bg-yellow-100"
                    }>
                      {report.components.encryption_metrics?.encryption_strength || 'Unknown'}
                    </Badge>
                  </div>
                  {report.components.encryption_metrics?.encryption_metrics?.encryption?.cipher_suite && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span>Algorithm</span>
                        <span className="text-sm font-mono">
                          {report.components.encryption_metrics.encryption_metrics.encryption.cipher_suite.algorithm}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Key Size</span>
                        <span className="text-sm font-mono">
                          {report.components.encryption_metrics.encryption_metrics.encryption.cipher_suite.key_size} bits
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="assurances">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Confidentiality Assurances</CardTitle>
              <CardDescription>
                What we can guarantee about your data protection
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {report.assurances.map((assurance, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                    <span className="text-green-800">{assurance}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Technical Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <pre className="bg-gray-50 p-4 rounded-lg overflow-auto text-sm">
                  {JSON.stringify(report.components, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recommendations">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recommendations</CardTitle>
              <CardDescription>
                Actions to improve your confidentiality protection
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {report.recommendations.map((rec, index) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className={getPriorityColor(rec.priority)}>
                        {rec.priority.toUpperCase()}
                      </Badge>
                      <span className="font-medium">{rec.issue}</span>
                    </div>
                    <p className="text-gray-600">{rec.action}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default ConfidentialityDashboard