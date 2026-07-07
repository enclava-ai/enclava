import { expect, expectAppShell, test } from "./fixtures"

test.describe("@agents agents module", () => {
  test("lists configured agents and management affordances", async ({ authenticatedPage: page }) => {
    await page.goto("/agents")

    await expectAppShell(page, "Agents")
    await expect(page.getByText("Support Agent")).toBeVisible()
    await expect(page.getByRole("button", { name: /Create Agent/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /MCP Servers/i })).toBeVisible()
  })
})

