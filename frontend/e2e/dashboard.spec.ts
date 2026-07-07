import { expect, expectAppShell, test } from "./fixtures"

test.describe("@dashboard dashboard", () => {
  test("shows operational overview and primary navigation", async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard")

    await expectAppShell(page, "Dashboard")
    await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible()
    await expect(page.getByText("Trust line")).toBeVisible()
    await expect(page.getByText("Module health")).toBeVisible()
    await expect(page.getByText("rag", { exact: true })).toBeVisible()
    await expect(page.getByRole("main").getByRole("link", { name: /API keys/i })).toBeVisible()
  })
})
