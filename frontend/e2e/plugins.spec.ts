import { expect, test } from "./fixtures"

test.describe("@plugins plugin manager", () => {
  test("shows discovery and installed plugin surfaces", async ({ authenticatedPage: page }) => {
    await page.goto("/plugins")

    await expect(page.getByRole("heading", { name: "Plugin Manager" })).toBeVisible()
    await expect(page.getByText(/Discover, install, and manage plugins/i)).toBeVisible()
  })
})

