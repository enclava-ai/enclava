import { expect, expectAppShell, test } from "./fixtures"

test.describe("@extract extract module", () => {
  test("shows document extraction workspace", async ({ authenticatedPage: page }) => {
    await page.goto("/extract")

    await expectAppShell(page, "Extract")
    await expect(page.getByRole("heading", { name: "Document Extraction" })).toBeVisible()
    await expect(page.getByText(/Extract structured data/i)).toBeVisible()
    await expect(page.getByText("invoice").first()).toBeVisible()
  })
})

