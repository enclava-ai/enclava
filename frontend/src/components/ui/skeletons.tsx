"use client"

import * as React from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface CardGridSkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  cards?: number
}

function CardGridSkeleton({
  cards = 6,
  className,
  ...props
}: CardGridSkeletonProps) {
  return (
    <div
      className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}
      {...props}
    >
      {Array.from({ length: cards }).map((_, index) => (
        <div key={index} className="rounded-lg border bg-card p-4">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-5/6" />
          <div className="mt-4 flex gap-2">
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        </div>
      ))}
    </div>
  )
}

interface TableSkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  rows?: number
  columns?: number
}

function TableSkeleton({
  rows = 5,
  columns = 4,
  className,
  ...props
}: TableSkeletonProps) {
  return (
    <div className={cn("rounded-lg border", className)} {...props}>
      <div
        className="grid gap-4 border-b bg-muted/40 p-4"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: columns }).map((_, index) => (
          <Skeleton key={index} className="h-4 w-3/4" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="grid gap-4 border-b p-4 last:border-b-0"
          style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        >
          {Array.from({ length: columns }).map((_, columnIndex) => (
            <Skeleton key={columnIndex} className="h-4 w-full" />
          ))}
        </div>
      ))}
    </div>
  )
}

function PageSkeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("space-y-6", className)} {...props}>
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <CardGridSkeleton cards={3} />
      <TableSkeleton rows={4} />
    </div>
  )
}

export { CardGridSkeleton, PageSkeleton, TableSkeleton }
