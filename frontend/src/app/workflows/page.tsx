"use client"

import Link from "next/link"
import { Plus } from "lucide-react"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { Button } from "@/components/ui/button"
import { WorkflowOperationsConsole } from "@/components/workflows/WorkflowOperationsConsole"
import { WorkflowRunsTable } from "@/components/workflows/WorkflowRunsTable"
import { WorkflowScheduleBoard } from "@/components/workflows/WorkflowScheduleBoard"
import { WorkflowTemplatesPanel } from "@/components/workflows/WorkflowTemplatesPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function WorkflowsPage() {
  return (
    <ProtectedRoute>
      <Tabs defaultValue="overview" className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <TabsList className="max-w-full overflow-x-auto">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="runs">Runs</TabsTrigger>
            <TabsTrigger value="schedules">Schedules</TabsTrigger>
            <TabsTrigger value="templates">Templates</TabsTrigger>
          </TabsList>
          <Button asChild size="sm" className="w-fit">
            <Link href="/workflows/new">
              <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
              New workflow
            </Link>
          </Button>
        </div>
        <TabsContent value="overview">
          <WorkflowOperationsConsole />
        </TabsContent>
        <TabsContent value="runs">
          <WorkflowRunsTable />
        </TabsContent>
        <TabsContent value="schedules">
          <WorkflowScheduleBoard />
        </TabsContent>
        <TabsContent value="templates">
          <WorkflowTemplatesPanel />
        </TabsContent>
      </Tabs>
    </ProtectedRoute>
  )
}
