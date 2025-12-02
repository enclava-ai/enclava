"use client"

import { ExternalLink, Globe } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { ChatMessageSource } from "@/types/chatbot"

interface SourcesListProps {
  sources: ChatMessageSource[]
}

export function SourcesList({ sources }: SourcesListProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  return (
    <div className="mt-3 space-y-2" role="region" aria-label="Information sources">
      <p className="text-xs font-medium text-muted-foreground">
        Sources ({sources.length}):
      </p>
      <div className="space-y-2">
        {sources.map((source, index) => {
          const hasUrl = source.url && source.url.trim() !== ""
          const isNonEnglish = source.language && source.language.toLowerCase() !== "en"
          const hasRelevanceScore = typeof source.relevance_score === "number"

          return (
            <div
              key={index}
              className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 dark:bg-slate-800/50 border border-border/50"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-start gap-2 flex-wrap">
                  {hasUrl ? (
                    <a
                      href={source.url!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded inline-flex items-center gap-1 break-words"
                      aria-label={`Open source: ${source.title} (opens in new tab)`}
                    >
                      {source.title || `Source ${index + 1}`}
                      <ExternalLink
                        className="h-3 w-3 flex-shrink-0"
                        aria-hidden="true"
                      />
                    </a>
                  ) : (
                    <span className="text-sm font-medium text-foreground break-words">
                      {source.title || `Source ${index + 1}`}
                    </span>
                  )}

                  <div className="flex items-center gap-1.5 flex-wrap">
                    {isNonEnglish && (
                      <Badge
                        variant="outline"
                        className="text-xs px-1.5 py-0 h-5 flex items-center gap-1"
                        aria-label={`Language: ${source.language}`}
                      >
                        <Globe className="h-3 w-3" aria-hidden="true" />
                        {source.language?.toUpperCase()}
                      </Badge>
                    )}

                    {hasRelevanceScore && (
                      <Badge
                        variant="secondary"
                        className="text-xs px-1.5 py-0 h-5"
                        aria-label={`Relevance score: ${source.relevance_score!.toFixed(0)}%`}
                      >
                        {source.relevance_score!.toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                </div>

                {source.content_preview && (
                  <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 break-words">
                    {source.content_preview}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
