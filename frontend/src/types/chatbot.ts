/**
 * TypeScript type definitions for chatbot functionality
 */

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  sources?: ChatMessageSource[]
  metadata?: Record<string, unknown>
}

export interface ChatMessageSource {
  title: string
  content: string
  url?: string
  metadata?: Record<string, unknown>
}

export interface ChatConversation {
  id: string
  chatbot_id: string
  user_id: string
  title: string
  messages: ChatMessage[]
  created_at: Date
  updated_at: Date
  is_active: boolean
  metadata?: Record<string, unknown>
}

export interface ChatbotConfig {
  name: string
  chatbot_type: string
  model: string
  system_prompt: string
  use_rag: boolean
  rag_collection?: string
  rag_top_k: number
  temperature: number
  max_tokens: number
  memory_length: number
  fallback_responses: string[]
}

export interface ChatbotInstance extends ChatbotConfig {
  id: string
  description?: string
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface ChatbotType {
  value: string
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  color: string
}

export interface RagCollection {
  id: string
  name: string
  description: string
  document_count: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PromptTemplate {
  id: string
  type_key: string
  name: string
  description: string
  system_prompt: string
  variables: PromptVariable[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PromptVariable {
  id: string
  template_id: string
  name: string
  description: string
  default_value?: string
  is_required: boolean
}

// API Response Types
export interface ChatResponse {
  response: string
  conversation_id: string
  message_id: string
  sources?: ChatMessageSource[]
  metadata?: Record<string, unknown>
}

export interface ChatbotListResponse {
  chatbots: ChatbotInstance[]
  total: number
}

export interface PromptTemplateListResponse {
  templates: PromptTemplate[]
  total: number
}

// API Request Types
export interface CreateChatbotRequest extends ChatbotConfig {}

export interface UpdateChatbotRequest extends Partial<ChatbotConfig> {
  id: string
}

export interface SendMessageRequest {
  chatbot_id: string
  message: string
  conversation_id?: string
}

export interface CreatePromptTemplateRequest {
  type_key: string
  name: string
  description: string
  system_prompt: string
  variables?: Omit<PromptVariable, 'id' | 'template_id'>[]
}

// Form State Types
export interface ChatbotFormState {
  config: ChatbotConfig
  errors: Record<keyof ChatbotConfig, string>
  isValid: boolean
  isDirty: boolean
}

export interface ChatInterfaceState {
  messages: ChatMessage[]
  input: string
  isLoading: boolean
  conversationId: string | null
  error: string | null
}

// Event Types
export type ChatbotEvent = 
  | { type: 'MESSAGE_SENT'; payload: { message: string } }
  | { type: 'MESSAGE_RECEIVED'; payload: { message: ChatMessage } }
  | { type: 'ERROR'; payload: { error: string } }
  | { type: 'TYPING_START' }
  | { type: 'TYPING_STOP' }
  | { type: 'CONVERSATION_CREATED'; payload: { conversationId: string } }

// Utility Types
export type ChatbotConfigField = keyof ChatbotConfig
export type MessageRole = ChatMessage['role']
export type ChatbotVariant = 'default' | 'compact' | 'fullscreen'

// Validation Types
export interface ValidationRule<T = string> {
  required?: boolean
  minLength?: number
  maxLength?: number
  min?: number
  max?: number
  pattern?: RegExp
  custom?: (value: T) => string | null
}

export type ValidationRules<T> = {
  [K in keyof T]?: ValidationRule<T[K]>
}

export interface ValidationResult {
  isValid: boolean
  errors: Record<string, string>
}