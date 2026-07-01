"use client"

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function PromptTemplatesPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to LLM page with prompt-templates tab
    router.replace('/settings/llm?tab=prompt-templates')
  }, [router])

  return null
}
