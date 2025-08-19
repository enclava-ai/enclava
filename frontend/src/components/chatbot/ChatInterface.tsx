"use client"

import { useState, useRef, useEffect, useCallback, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { MessageCircle, Send, Bot, User, Loader2, Copy, ThumbsUp, ThumbsDown } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { generateTimestampId } from "@/lib/id-utils"
import { chatbotApi, type AppError } from "@/lib/api-client"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: Array<{
    title: string
    content: string
    metadata?: any
  }>
}

interface ChatInterfaceProps {
  chatbotId: string
  chatbotName: string
  onClose?: () => void
}

export function ChatInterface({ chatbotId, chatbotName, onClose }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  const scrollToBottom = useCallback(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return

    const messageToSend = input // Capture input before clearing
    const userMessage: ChatMessage = {
      id: generateTimestampId('msg'),
      role: 'user',
      content: messageToSend,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput("")
    setIsLoading(true)

    try {
      const data = await chatbotApi.sendMessage(
        chatbotId,
        messageToSend,
        conversationId || undefined
      )
      
      // Update conversation ID if it's a new conversation
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id)
      }

      const assistantMessage: ChatMessage = {
        id: data.message_id || generateTimestampId('msg'),
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        sources: data.sources
      }

      setMessages(prev => [...prev, assistantMessage])

    } catch (error) {
      const appError = error as AppError
      console.error('Error sending message:', appError)
      
      // More specific error handling
      if (appError.code === 'UNAUTHORIZED') {
        toast.error("Authentication Required", "Please log in to continue chatting.")
      } else if (appError.code === 'NETWORK_ERROR') {
        toast.error("Connection Error", "Please check your internet connection and try again.")
      } else {
        toast.error("Message Failed", appError.message || "Failed to send message. Please try again.")
      }
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, chatbotId, conversationId, toast])

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }, [sendMessage])

  const copyMessage = useCallback(async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      toast.success("Copied", "Message copied to clipboard")
    } catch (error) {
      console.error('Failed to copy message:', error)
      toast.error("Copy Failed", "Unable to copy message to clipboard")
    }
  }, [toast])

  const formatTime = useCallback((date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }, [])

  return (
    <Card className="h-[600px] flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MessageCircle className="h-5 w-5" />
            <CardTitle className="text-lg">Testing: {chatbotName}</CardTitle>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              ×
            </Button>
          )}
        </div>
        <Separator />
      </CardHeader>

      <CardContent className="flex-1 flex flex-col p-0">
        <ScrollArea 
          ref={scrollAreaRef} 
          className="flex-1 px-4"
          aria-label="Chat conversation"
          role="log"
          aria-live="polite"
        >
          <div className="space-y-4 py-4">
            {messages.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Start a conversation with your chatbot!</p>
                <p className="text-sm">Type a message below to begin.</p>
              </div>
            )}

            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] min-w-0 space-y-2`}>
                  <div className={`flex items-start space-x-2 ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    <div className={`p-2 rounded-full ${message.role === 'user' ? 'bg-primary' : 'bg-muted'}`}>
                      {message.role === 'user' ? (
                        <User className="h-4 w-4 text-primary-foreground" />
                      ) : (
                        <Bot className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1 space-y-2 min-w-0">
                      <div className={`rounded-lg p-4 ${
                        message.role === 'user' 
                          ? 'bg-primary text-primary-foreground ml-auto max-w-fit' 
                          : 'bg-muted'
                      }`}>
                        <div className="text-sm prose prose-sm max-w-full break-words overflow-hidden markdown-content">
                          {message.role === 'user' ? (
                            <div className="whitespace-pre-wrap break-words overflow-x-auto">{message.content}</div>
                          ) : (
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              rehypePlugins={[rehypeHighlight]}
                              components={{
                                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                                h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                                h2: ({ children }) => <h2 className="text-base font-bold mb-2">{children}</h2>,
                                h3: ({ children }) => <h3 className="text-sm font-bold mb-2">{children}</h3>,
                                ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                                ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                                li: ({ children }) => <li className="mb-1">{children}</li>,
                                code: ({ children, className }) => {
                                  const isInline = !className;
                                  return isInline ? (
                                    <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono border break-all">
                                      {children}
                                    </code>
                                  ) : (
                                    <code className={`block bg-muted p-3 rounded text-sm font-mono overflow-x-auto border max-w-full ${className || ''}`}>
                                      {children}
                                    </code>
                                  )
                                },
                                pre: ({ children }) => (
                                  <pre className="bg-muted p-3 rounded overflow-x-auto text-sm font-mono mb-2 border max-w-full">
                                    {children}
                                  </pre>
                                ),
                                blockquote: ({ children }) => (
                                  <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic mb-2">
                                    {children}
                                  </blockquote>
                                ),
                                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                                em: ({ children }) => <em className="italic">{children}</em>,
                              }}
                            >
                              {message.content}
                            </ReactMarkdown>
                          )}
                        </div>
                      </div>
                      
                      {/* Sources for assistant messages */}
                      {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground">Sources:</p>
                          <div className="space-y-1">
                            {message.sources.map((source, index) => (
                              <Badge key={index} variant="outline" className="text-xs">
                                {source.title || `Source ${index + 1}`}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>{formatTime(message.timestamp)}</span>
                        <div className="flex items-center space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0"
                            onClick={() => copyMessage(message.content)}
                            aria-label="Copy message to clipboard"
                          >
                            <Copy className="h-3 w-3" aria-hidden="true" />
                          </Button>
                          {message.role === 'assistant' && (
                            <>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-6 w-6 p-0"
                                aria-label="Mark response as helpful"
                              >
                                <ThumbsUp className="h-3 w-3" aria-hidden="true" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-6 w-6 p-0"
                                aria-label="Mark response as unhelpful"
                              >
                                <ThumbsDown className="h-3 w-3" aria-hidden="true" />
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="max-w-[80%]">
                  <div className="flex items-start space-x-2">
                    <div className="p-2 rounded-full bg-muted">
                      <Bot className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="bg-muted rounded-lg p-3">
                      <div className="flex items-center space-x-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm text-muted-foreground">Thinking...</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t">
          <div className="flex space-x-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              disabled={isLoading}
              className="flex-1"
              aria-label="Chat message input"
              aria-describedby="chat-input-help"
              maxLength={4000}
            />
            <Button 
              onClick={sendMessage} 
              disabled={!input.trim() || isLoading}
              size="sm"
              aria-label={isLoading ? "Sending message..." : "Send message"}
              type="submit"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-4 w-4" aria-hidden="true" />
              )}
            </Button>
          </div>
          <p id="chat-input-help" className="text-xs text-muted-foreground mt-2">
            Press Enter to send, Shift+Enter for new line. Maximum 4000 characters.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}