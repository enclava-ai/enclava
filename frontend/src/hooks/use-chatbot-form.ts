/**
 * Custom hook for managing chatbot form state and operations
 */

import { useState, useCallback, useMemo } from 'react'
import { generateId } from '@/lib/id-utils'
import { chatbotApi } from '@/lib/api-client'
import { useToast } from './use-toast'

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
  created_by: string
  created_at: string
  updated_at: string
  is_active: boolean
}

const DEFAULT_FALLBACK_RESPONSES = [
  "I'm not sure how to help with that. Could you please rephrase your question?",
  "I don't have enough information to answer that question accurately.",
  "That's outside my knowledge area. Is there something else I can help you with?"
]

export const createDefaultChatbotConfig = (): ChatbotConfig => ({
  name: "",
  chatbot_type: "assistant",
  model: "",
  system_prompt: "",
  use_rag: false,
  rag_collection: "",
  rag_top_k: 5,
  temperature: 0.7,
  max_tokens: 1000,
  memory_length: 10,
  fallback_responses: [...DEFAULT_FALLBACK_RESPONSES]
})

export function useChatbotForm() {
  const [chatbots, setChatbots] = useState<ChatbotInstance[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const toast = useToast()

  // Load chatbots
  const loadChatbots = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await chatbotApi.list()
      setChatbots(data)
    } catch (error) {
      console.error('Load chatbots error:', error)
      toast.error("Loading Failed", "Failed to load chatbots")
    } finally {
      setIsLoading(false)
    }
  }, [toast])

  // Create chatbot
  const createChatbot = useCallback(async (config: ChatbotConfig) => {
    setIsSubmitting(true)
    try {
      const newChatbot = await chatbotApi.create(config)
      setChatbots(prev => [...prev, newChatbot])
      toast.success("Success", `Chatbot "${config.name}" created successfully`)
      return newChatbot
    } catch (error) {
      console.error('Create chatbot error:', error)

      if (error && typeof error === 'object' && 'response' in error) {
        const detail = error.response?.data?.detail || error.response?.data?.error
        if (detail) {
          toast.error("Validation Error", detail)
        } else {
          toast.error("Creation Failed", "Failed to create chatbot")
        }
      } else {
        toast.error("Creation Failed", "Failed to create chatbot")
      }
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }, [toast])

  // Update chatbot
  const updateChatbot = useCallback(async (id: string, config: ChatbotConfig) => {
    setIsSubmitting(true)
    try {
      const updatedChatbot = await chatbotApi.update(id, config)
      setChatbots(prev => prev.map(bot => bot.id === id ? updatedChatbot : bot))
      toast.success("Success", `Chatbot "${config.name}" updated successfully`)
      return updatedChatbot
    } catch (error) {
      console.error('Update chatbot error:', error)
      toast.error("Update Failed", "Failed to update chatbot")
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }, [toast])

  // Delete chatbot
  const deleteChatbot = useCallback(async (id: string) => {
    setIsSubmitting(true)
    try {
      await chatbotApi.delete(id)
      setChatbots(prev => prev.filter(bot => bot.id !== id))
      toast.success("Success", "Chatbot deleted successfully")
    } catch (error) {
      console.error('Delete chatbot error:', error)
      toast.error("Deletion Failed", "Failed to delete chatbot")
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }, [toast])

  // Validation helpers
  const validateConfig = useCallback((config: ChatbotConfig): string[] => {
    const errors: string[] = []
    
    if (!config.name.trim()) {
      errors.push("Name is required")
    }
    
    if (!config.model.trim()) {
      errors.push("Model is required")
    }
    
    if (config.temperature < 0 || config.temperature > 2) {
      errors.push("Temperature must be between 0 and 2")
    }
    
    if (config.max_tokens < 1 || config.max_tokens > 4000) {
      errors.push("Max tokens must be between 1 and 4000")
    }
    
    if (config.memory_length < 1 || config.memory_length > 50) {
      errors.push("Memory length must be between 1 and 50")
    }
    
    if (config.rag_top_k < 1 || config.rag_top_k > 20) {
      errors.push("RAG top-k must be between 1 and 20")
    }

    if (config.use_rag && !config.rag_collection) {
      errors.push("RAG collection is required when RAG is enabled")
    }
    
    return errors
  }, [])

  const memoizedChatbots = useMemo(() => chatbots, [chatbots])

  return {
    // State
    chatbots: memoizedChatbots,
    isLoading,
    isSubmitting,
    
    // Actions
    loadChatbots,
    createChatbot,
    updateChatbot,
    deleteChatbot,
    validateConfig,
    
    // Utilities
    createDefaultConfig: createDefaultChatbotConfig,
  }
}