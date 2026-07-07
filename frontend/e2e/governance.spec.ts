import { expect, test } from "./fixtures"

test.describe("@governance governance and reporting", () => {
  test("shows analytics dashboard", async ({ authenticatedPage: page }) => {
    await page.goto("/analytics")

    await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible()
    await expect(page.getByText("Total Users")).toBeVisible()
    await expect(page.getByRole("tab", { name: "Usage" })).toBeVisible()
  })

  test("shows budget management", async ({ authenticatedPage: page }) => {
    await page.goto("/budgets")

    await expect(page.getByText(/Budget/i).first()).toBeVisible()
    await expect(page.getByRole("button", { name: /Create|New|Add/i }).first()).toBeVisible()
  })

  test("shows audit log reporting", async ({ authenticatedPage: page }) => {
    await page.goto("/audit")

    await expect(page.getByText(/Audit/i).first()).toBeVisible()
    await expect(page.getByRole("button", { name: /Filter|Refresh|Export|Download/i }).first()).toBeVisible()
  })
})
