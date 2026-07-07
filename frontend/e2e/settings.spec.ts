import { expect, expectAppShell, test } from "./fixtures"

test.describe("@settings system settings", () => {
  test("shows module and notification settings", async ({ authenticatedPage: page }) => {
    await page.goto("/settings")

    await expectAppShell(page, "Settings / System Settings")
    await expect(page.getByText(/System Settings/i).first()).toBeVisible()
    await expect(page.getByText(/Modules/i).first()).toBeVisible()
    await expect(page.getByText("rag")).toBeVisible()
  })
})

