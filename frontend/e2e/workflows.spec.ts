import { expect, expectAppShell, test } from "./fixtures"

test.describe("@workflows workflows module", () => {
  test("shows operations, run, schedule, and template views independently", async ({ authenticatedPage: page }) => {
    await page.goto("/workflows")

    await expectAppShell(page, "Workflows")
    await expect(page.getByRole("link", { name: "New workflow" })).toBeVisible()
    await expect(page.getByText("Nightly RAG Summary").first()).toBeVisible()

    await page.getByRole("tab", { name: "Runs" }).click()
    await expect(page.getByText("run-1")).toBeVisible()

    await page.getByRole("tab", { name: "Schedules" }).click()
    await expect(page.getByText("0 2 * * *")).toBeVisible()

    await page.getByRole("tab", { name: "Templates" }).click()
    await expect(page.getByText("Nightly RAG Summary").first()).toBeVisible()
  })

  test("opens the workflow builder", async ({ authenticatedPage: page }) => {
    await page.goto("/workflows/new")

    await expect(page.getByText(/Workflow/i).first()).toBeVisible()
    await expect(page.getByRole("link", { name: /Workflows/i }).first()).toBeVisible()
  })
})
