import { expect, expectAppShell, test } from "./fixtures"

test.describe("@rag RAG module", () => {
  test("shows collections, documents, and upload workflow entry points", async ({ authenticatedPage: page }) => {
    await page.goto("/rag")

    await expectAppShell(page, "RAG")
    await expect(page.getByRole("heading", { name: "RAG Document Management" })).toBeVisible()
    await expect(page.getByText("Product Docs")).toBeVisible()

    await page.getByRole("tab", { name: "Browse Documents" }).click()
    await expect(page.getByText("getting-started.md")).toBeVisible()

    await page.getByRole("tab", { name: "Upload Documents" }).click()
    await expect(page.getByText(/Drop files here/i)).toBeVisible()
  })
})
