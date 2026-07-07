import { expect, test } from "./fixtures"

test.describe("@llm LLM settings", () => {
  test("shows usage, playground, providers, and prompt template tabs", async ({ authenticatedPage: page }) => {
    await page.goto("/settings/llm")

    await expect(page.getByRole("tab", { name: /Usage/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /Playground/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /Providers/i })).toBeVisible()

    await page.getByRole("tab", { name: /Providers/i }).click()
    await expect(page.getByText("Inference Providers")).toBeVisible()
  })
})

