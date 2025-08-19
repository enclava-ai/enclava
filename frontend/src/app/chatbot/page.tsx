"use client"

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { ChatbotManager } from '@/components/chatbot/ChatbotManager'

export default function ChatbotPage() {
  return (
    <ProtectedRoute>
      <ChatbotPageContent />
    </ProtectedRoute>
  )
}

function ChatbotPageContent() {
  return (
    <div className="container mx-auto px-4 py-8">
      <ChatbotManager />
    </div>
  )
}