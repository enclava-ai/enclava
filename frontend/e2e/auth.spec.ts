import { expect, test } from "./fixtures"
import { testUser } from "./support/api-mocks"

test.describe("@auth authentication", () => {
  test("public landing page routes to login", async ({ page }) => {
    await page.route("**/api-internal/v1/auth/me", async (route) => {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) })
    })

    await page.goto("/")
    await expect(page.getByRole("heading", { name: "Enclava AI Platform" })).toBeVisible()

    await page.getByRole("button", { name: "Get Started" }).click()
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole("heading", { name: "Enclava" })).toBeVisible()
  })

  test("user can sign in and reach the dashboard", async ({ page }) => {
    let loggedIn = false
    await page.route("**/api-internal/v1/auth/me", async (route) => {
      if (!loggedIn) {
        await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) })
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(testUser) })
    })
    await page.route("**/api-internal/v1/auth/login", async (route) => {
      loggedIn = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "e2e-access-token",
          refresh_token: "e2e-refresh-token",
          token_type: "bearer",
          expires_in: 3600,
          user: testUser,
        }),
      })
    })

    await page.goto("/login")
    await page.getByLabel("Email").fill("test-admin@example.com")
    await page.getByLabel("Password").fill("test-admin-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible()
  })
})
