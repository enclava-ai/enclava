"use client"

import { Suspense, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"

export default function LLMRedirectPage() {
  return (
    <Suspense fallback={null}>
      <LLMRedirect />
    </Suspense>
  )
}

function LLMRedirect() {
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const queryString = searchParams.toString()
    router.replace(`/settings/llm${queryString ? `?${queryString}` : ""}`)
  }, [router, searchParams])

  return null
}
