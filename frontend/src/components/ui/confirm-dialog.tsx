"use client"

import * as React from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export interface ConfirmDialogOptions {
  title: string
  description: React.ReactNode
  confirmText?: string
  cancelText?: string
  destructive?: boolean
  requireText?: string
}

export interface ConfirmDialogProps extends ConfirmDialogOptions {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  destructive = false,
  requireText,
  onConfirm,
}: ConfirmDialogProps) {
  const [confirmationValue, setConfirmationValue] = React.useState("")

  React.useEffect(() => {
    if (!open) setConfirmationValue("")
  }, [open])

  const disabled = requireText ? confirmationValue !== requireText : false

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {requireText ? (
          <Input
            value={confirmationValue}
            onChange={(event) => setConfirmationValue(event.target.value)}
            placeholder={`Type "${requireText}" to confirm`}
            aria-label={`Type ${requireText} to confirm`}
          />
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            disabled={disabled}
            className={cn(
              destructive &&
                "bg-danger text-danger-foreground hover:bg-danger/90 focus-visible:ring-danger"
            )}
            onClick={onConfirm}
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

interface ConfirmContextValue {
  confirm: (options: ConfirmDialogOptions) => Promise<boolean>
}

const ConfirmContext = React.createContext<ConfirmContextValue | null>(null)

interface PendingConfirm {
  options: ConfirmDialogOptions
  resolve: (confirmed: boolean) => void
}

function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = React.useState<PendingConfirm | null>(null)

  const confirm = React.useCallback((options: ConfirmDialogOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending({ options, resolve })
    })
  }, [])

  const settle = React.useCallback(
    (confirmed: boolean) => {
      pending?.resolve(confirmed)
      setPending(null)
    },
    [pending]
  )

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending ? (
        <ConfirmDialog
          {...pending.options}
          open={true}
          onOpenChange={(open) => {
            if (!open) settle(false)
          }}
          onConfirm={() => settle(true)}
        />
      ) : null}
    </ConfirmContext.Provider>
  )
}

function useConfirm() {
  const context = React.useContext(ConfirmContext)
  if (!context) {
    throw new Error("useConfirm must be used within a ConfirmProvider")
  }
  return context.confirm
}

export { ConfirmDialog, ConfirmProvider, useConfirm }
