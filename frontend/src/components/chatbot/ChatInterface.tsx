"use client"

import { useState, useRef, useEffect, useCallback, useMemo, memo } from "react"
import "./ChatInterface.css"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { MessageCircle, Send, Bot, User, Loader2, Copy, ThumbsUp, ThumbsDown } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { generateTimestampId } from "@/lib/id-utils"
import { chatbotApi } from "@/lib/api-client"
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

// Memoized markdown renderer to prevent re-render issues with Next.js HotReload
const MessageMarkdown = memo(({ content }: { content: string }) => {
  const markdownComponents = useMemo(() => ({
    p: ({ children }: any) => <p className="mb-2 last:mb-0 break-words">{children}</p>,
    h1: ({ children }: any) => <h1 className="text-lg font-bold mb-2 break-words">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-base font-bold mb-2 break-words">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-sm font-bold mb-2 break-words">{children}</h3>,
    ul: ({ children }: any) => <ul className="list-disc pl-4 mb-2 break-words">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal pl-4 mb-2 break-words">{children}</ol>,
    li: ({ children }: any) => <li className="mb-1 break-words">{children}</li>,
    code: ({ children, className }: any) => {
      const isInline = !className;
      return isInline ? (
        <code className="bg-muted/50 text-foreground px-1.5 py-0.5 rounded text-xs font-mono border break-words">
          {children}
        </code>
      ) : (
        <code className={`block bg-muted/50 text-foreground p-3 rounded text-sm font-mono overflow-x-auto border w-full ${className || ''}`}>
          {children}
        </code>
      )
    },
    pre: ({ children }: any) => (
      <pre className="bg-muted/50 text-foreground p-3 rounded overflow-x-auto text-sm font-mono mb-2 border w-full whitespace-pre-wrap">
        {children}
      </pre>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic mb-2 break-words">
        {children}
      </blockquote>
    ),
    strong: ({ children }: any) => <strong className="font-semibold break-words">{children}</strong>,
    em: ({ children }: any) => <em className="italic break-words">{children}</em>,
  }), [])

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={markdownComponents}
    >
      {content}
    </ReactMarkdown>
  )
})

MessageMarkdown.displayName = 'MessageMarkdown'

export function ChatInterface({ chatbotId, chatbotName, onClose }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const { success: toastSuccess, error: toastError } = useToast()

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

    // Enhanced logging for debugging
    const debugInfo = {
      chatbotId,
      messageLength: messageToSend.length,
      conversationId,
      timestamp: new Date().toISOString(),
      messagesCount: messages.length
    }
    console.log('=== CHAT REQUEST DEBUG ===', debugInfo)

    try {
      let data: any

      // Use internal API
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }))

      data = await chatbotApi.sendMessage(
        chatbotId,
        messageToSend,
        undefined, // No conversation ID
        conversationHistory
      )

      const assistantMessage: ChatMessage = {
        id: data.id || generateTimestampId('msg'),
        role: 'assistant',
        content: data.choices?.[0]?.message?.content || data.response || 'No response',
        timestamp: new Date(),
        sources: data.sources
      }

      setMessages(prev => [...prev, assistantMessage])

    } catch (error) {
      const appError = error as AppError
      
      // More specific error handling
      if (appError.code === 'UNAUTHORIZED') {
        toastError("Authentication Required", "Please log in to continue chatting.")
      } else if (appError.code === 'NETWORK_ERROR') {
        toastError("Connection Error", "Please check your internet connection and try again.")
      } else {
        toastError("Message Failed", appError.message || "Failed to send message. Please try again.")
      }
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, chatbotId, messages, toastError])

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }, [sendMessage])

  const copyMessage = useCallback(async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      toastSuccess("Copied", "Message copied to clipboard")
    } catch (error) {
      toastError("Copy Failed", "Unable to copy message to clipboard")
    }
  }, [toastSuccess, toastError])

  const formatTime = useCallback((date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }, [])

  return (
    <Card className="h-full flex flex-col bg-background border-border">
      <CardHeader className="pb-3 border-b border-border flex-shrink-0">
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

      <CardContent className="flex-1 flex flex-col p-0 min-h-0 overflow-hidden">
        <ScrollArea 
          ref={scrollAreaRef} 
          className="flex-1 px-4 h-full"
          aria-label="Chat conversation"
          role="log"
          aria-live="polite"
        >
          <div className="space-y-4 py-4 chat-messages-container">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <Bot className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-foreground/70">Start a conversation with your chatbot!</p>
                <p className="text-sm text-muted-foreground">Type a message below to begin.</p>
              </div>
            )}

            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] min-w-0 space-y-2`}>
                  <div className={`flex items-start space-x-2 ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                    <div className={`p-2 rounded-full ${message.role === 'user' ? 'bg-primary' : 'bg-secondary/50 dark:bg-slate-700'}`}>
                      {message.role === 'user' ? (
                        <User className="h-4 w-4 text-primary-foreground" />
                      ) : (
                        <Bot className="h-4 w-4 text-muted-foreground dark:text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1 space-y-2 min-w-0">
                      <div className={`rounded-lg p-4 ${
                        message.role === 'user' 
                          ? 'bg-primary text-primary-foreground ml-auto chat-message-user' 
                          : 'bg-muted text-foreground dark:bg-slate-700 dark:text-slate-200 chat-message-assistant'
                      } break-words overflow-wrap-anywhere`}>
                        <div className="text-sm prose prose-sm dark:prose-invert max-w-none break-words overflow-wrap-anywhere markdown-content dark:text-slate-200">
                          {message.role === 'user' ? (
                            <div className="whitespace-pre-wrap break-words overflow-x-auto">{message.content}</div>
                          ) : (
                            <MessageMarkdown content={message.content} />
                          )}
                        </div>
                      </div>
                      
                      {/* Sources for assistant messages */}
                      {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs text-foreground/60">Sources:</p>
                          <div className="space-y-1">
                            {message.sources.map((source, index) => (
                              <Badge key={index} variant="outline" className="text-xs">
                                {source.title || `Source ${index + 1}`}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-xs text-foreground/50 dark:text-slate-400 chat-timestamp">
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
                <div className="max-w-[85%]">
                  <div className="flex items-start space-x-2">
                    <div className="p-2 rounded-full bg-secondary/50 dark:bg-slate-700">
                      <Bot className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="bg-muted dark:bg-slate-700 rounded-lg p-3 chat-thinking">
                      <div className="flex items-center space-x-2">
                        <Loader2 className="h-4 w-4 animate-spin text-foreground dark:text-slate-200" />
                        <span className="text-sm text-foreground/70 dark:text-slate-200">Thinking...</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t flex-shrink-0">
          <div className="flex space-x-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              disabled={isLoading}
              className="flex-1 bg-background text-foreground placeholder:text-muted-foreground dark:bg-slate-800 dark:text-slate-200 dark:placeholder:text-slate-400 chat-input"
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
          <p id="chat-input-help" className="text-xs text-foreground/60 mt-2">
            Press Enter to send, Shift+Enter for new line. Maximum 4000 characters.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}