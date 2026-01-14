/**
 * TypeScript type definitions for MCP Server management
 */

// =============================================================================
// Core Types
// =============================================================================

export interface MCPToolInfo {
  name: string
  description?: string
  parameters_schema?: Record<string, unknown>
}

export interface MCPServer {
  id: number
  name: string
  display_name: string
  description?: string
  server_url: string
  has_api_key: boolean
  api_key_header_name: string
  timeout_seconds: number
  max_retries: number
  is_global: boolean
  is_active: boolean
  created_by_user_id: number
  cached_tools: Array<{
    type: string
    function: {
      name: string
      description?: string
      parameters?: Record<string, unknown>
    }
  }>
  tool_count: number
  last_connected_at?: string
  last_connection_status?: 'success' | 'failed'
  last_connection_error?: string
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

// =============================================================================
// Request Types
// =============================================================================

export interface CreateMCPServerRequest {
  name: string
  display_name: string
  description?: string
  server_url: string
  api_key?: string
  api_key_header_name?: string
  timeout_seconds?: number
  max_retries?: number
  is_global?: boolean
}

export interface UpdateMCPServerRequest {
  display_name?: string
  description?: string
  server_url?: string
  api_key?: string
  api_key_header_name?: string
  timeout_seconds?: number
  max_retries?: number
  is_global?: boolean
  is_active?: boolean
}

export interface TestMCPServerRequest {
  server_url: string
  api_key?: string
  api_key_header_name?: string
  timeout_seconds?: number
}

// =============================================================================
// Response Types
// =============================================================================

export interface MCPServerListResponse {
  servers: MCPServer[]
  total: number
  user_servers: number
  global_servers: number
}

export interface MCPServerTestResponse {
  success: boolean
  message: string
  tools: MCPToolInfo[]
  tool_count: number
  response_time_ms?: number
  error?: string
}

export interface MCPServerRefreshResponse {
  success: boolean
  tools: MCPToolInfo[]
  tool_count: number
  message: string
  error?: string
}

export interface MCPServerDeleteResponse {
  success: boolean
  message: string
  deleted_id: number
}

export interface AvailableMCPServersResponse {
  servers: Array<{
    name: string
    display_name: string
    description?: string
    tool_count: number
    is_global: boolean
  }>
  count: number
}

// =============================================================================
// Form State Types
// =============================================================================

export interface MCPServerFormState {
  name: string
  display_name: string
  description: string
  server_url: string
  api_key: string
  api_key_header_name: string
  timeout_seconds: number
  max_retries: number
  is_global: boolean
}

export interface MCPServerFormErrors {
  name?: string
  display_name?: string
  server_url?: string
  api_key?: string
  timeout_seconds?: string
  max_retries?: string
}

// =============================================================================
// UI State Types
// =============================================================================

export interface MCPServerManagerState {
  servers: MCPServer[]
  isLoading: boolean
  error: string | null
  selectedServer: MCPServer | null
  isCreateDialogOpen: boolean
  isEditDialogOpen: boolean
  isDeleteDialogOpen: boolean
  isTestDialogOpen: boolean
  testResult: MCPServerTestResponse | null
}

// =============================================================================
// Validation Helpers
// =============================================================================

export const validateMCPServerName = (name: string): string | undefined => {
  if (!name) return 'Name is required'
  if (name.length < 1) return 'Name must be at least 1 character'
  if (name.length > 100) return 'Name must be less than 100 characters'
  if (!/^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$/.test(name)) {
    return 'Name must start with a letter, contain only lowercase letters, numbers, and hyphens, and end with a letter or number'
  }
  return undefined
}

export const validateServerUrl = (url: string): string | undefined => {
  if (!url) return 'Server URL is required'
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return 'Server URL must start with http:// or https://'
  }
  return undefined
}

// =============================================================================
// Default Values
// =============================================================================

export const DEFAULT_MCP_SERVER_FORM: MCPServerFormState = {
  name: '',
  display_name: '',
  description: '',
  server_url: '',
  api_key: '',
  api_key_header_name: 'Authorization',
  timeout_seconds: 30,
  max_retries: 3,
  is_global: false,
}

// Common API key header options
export const API_KEY_HEADER_OPTIONS = [
  { value: 'Authorization', label: 'Authorization (Bearer token)' },
  { value: 'X-API-Key', label: 'X-API-Key' },
  { value: 'Api-Key', label: 'Api-Key' },
  { value: 'X-Auth-Token', label: 'X-Auth-Token' },
]

// =============================================================================
// Connection Status Helpers
// =============================================================================

export type ConnectionStatus = 'success' | 'failed' | 'unknown'

export const getConnectionStatus = (server: MCPServer): ConnectionStatus => {
  if (!server.last_connection_status) return 'unknown'
  return server.last_connection_status
}

export const getConnectionStatusColor = (status: ConnectionStatus): string => {
  switch (status) {
    case 'success':
      return 'bg-green-500'
    case 'failed':
      return 'bg-red-500'
    default:
      return 'bg-gray-400'
  }
}

export const getConnectionStatusText = (status: ConnectionStatus): string => {
  switch (status) {
    case 'success':
      return 'Connected'
    case 'failed':
      return 'Failed'
    default:
      return 'Unknown'
  }
}
