import { expect, test } from "./fixtures"

test.describe("@admin admin module", () => {
  test("shows user, role, and API key administration tabs", async ({ authenticatedPage: page }) => {
    await page.goto("/admin/users")

    await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible()
    await expect(page.getByRole("tab", { name: /Users/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /Roles/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /API Keys/i })).toBeVisible()
    await expect(page.getByLabel("Users").getByText("test-admin@example.com")).toBeVisible()
  })
})
