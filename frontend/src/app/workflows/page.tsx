"use client"

import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { WorkflowOperationsConsole } from "@/components/workflows/WorkflowOperationsConsole"
import { WorkflowRunsTable } from "@/components/workflows/WorkflowRunsTable"
import { WorkflowScheduleBoard } from "@/components/workflows/WorkflowScheduleBoard"
import { WorkflowTemplatesPanel } from "@/components/workflows/WorkflowTemplatesPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function WorkflowsPage() {
  return (
    <ProtectedRoute>
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="max-w-full overflow-x-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="schedules">Schedules</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>
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
