/**
 * TypeScript type definitions for agent functionality
 */

export interface ToolCall {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface AgentChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string | null
  timestamp: Date
  tool_calls?: ToolCall[]
  tool_call_id?: string
  tool_name?: string
}

export interface ToolsConfig {
  builtin_tools: string[]
  mcp_servers: string[]
  include_custom_tools: boolean
  tool_choice: string
  max_iterations: number
}

export interface FileSearchResource {
  vector_store_ids: string[]
  max_results?: number
}

export interface ToolResources {
  file_search?: FileSearchResource
}

export interface RagCollection {
  id: number | string
  name: string
  description: string
  document_count: number
}

export interface AgentConfig {
  id: number
  name: string
  display_name: string
  description?: string
  system_prompt: string
  model: string
  temperature: number
  max_tokens: number
  tools_config: ToolsConfig
  tool_resources?: ToolResources
  category?: string
  tags: string[]
  is_public: boolean
  is_template: boolean
  created_by_user_id?: number
  usage_count: number
  last_used_at?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Tool {
  name: string
  description: string
  display_name?: string
  category?: string
  parameters_schema?: Record<string, unknown>
}

// API Request Types
export interface CreateAgentConfigRequest {
  name: string
  display_name: string
  description?: string
  system_prompt: string
  model?: string
  temperature?: number
  max_tokens?: number
  builtin_tools?: string[]
  mcp_servers?: string[]
  include_custom_tools?: boolean
  tool_choice?: string
  max_iterations?: number
  category?: string
  tags?: string[]
  is_public?: boolean
  tool_resources?: ToolResources
}

export interface UpdateAgentConfigRequest extends Partial<CreateAgentConfigRequest> {}

export interface AgentChatRequest {
  agent_config_id: number
  message: string
  conversation_id?: string
}

// API Response Types
export interface AgentConfigListResponse {
  configs: AgentConfig[]
  count: number
}

export interface AgentChatResponse {
  content: string | null
  conversation_id: string
  tool_calls_made: ToolCall[]
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export interface ToolsListResponse {
  tools: Tool[]
  count: number
}

// Form State Types
export interface AgentFormState {
  config: CreateAgentConfigRequest
  errors: Record<string, string>
  isValid: boolean
  isDirty: boolean
}

export interface AgentChatInterfaceState {
  messages: AgentChatMessage[]
  input: string
  isLoading: boolean
  conversationId: string | null
  error: string | null
}

// Event Types
export type AgentEvent =
  | { type: 'MESSAGE_SENT'; payload: { message: string } }
  | { type: 'MESSAGE_RECEIVED'; payload: { message: AgentChatMessage } }
  | { type: 'TOOL_CALL_STARTED'; payload: { toolName: string } }
  | { type: 'TOOL_CALL_COMPLETED'; payload: { toolName: string; result: unknown } }
  | { type: 'ERROR'; payload: { error: string } }
  | { type: 'CONVERSATION_CREATED'; payload: { conversationId: string } }

// Utility Types
export type AgentConfigField = keyof CreateAgentConfigRequest
export type MessageRole = AgentChatMessage['role']

// Built-in Tools (RAG is configured via Knowledge Base tab, not here)
export const BUILTIN_TOOLS = [
  { value: 'web_search', label: 'Web Search', description: 'Search the web using Brave API' },
] as const

// Agent Categories
export const AGENT_CATEGORIES = [
  { value: 'support', label: 'Customer Support', description: 'Help customers with queries' },
  { value: 'development', label: 'Development', description: 'Assist with coding tasks' },
  { value: 'research', label: 'Research', description: 'Research and analysis' },
  { value: 'general', label: 'General Assistant', description: 'General purpose AI assistant' },
] as const
