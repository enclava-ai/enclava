import { expect, test } from "./fixtures"

test.describe("@navigation app shell", () => {
  test("exposes core and module navigation entries", async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard")

    for (const label of ["Dashboard", "Agents", "RAG", "Extract", "Workflows", "Settings"]) {
      await expect(page.getByRole("link", { name: label }).first()).toBeVisible()
    }

    await page.getByRole("link", { name: "Workflows" }).first().click()
    await expect(page).toHaveURL(/\/workflows/)
    await expect(page.getByRole("link", { name: "Workflows" }).first()).toHaveAttribute("aria-current", "page")
  })
})

