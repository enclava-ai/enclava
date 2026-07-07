import { test as base, expect, type Page } from "@playwright/test"

import { seedAuthenticatedSession, setupApiMocks } from "./support/api-mocks"

type AppFixtures = {
  authenticatedPage: Page
}

export const test = base.extend<AppFixtures>({
  page: async ({ page }, run) => {
    await setupApiMocks(page)
    await run(page)
  },
  authenticatedPage: async ({ page }, run) => {
    await seedAuthenticatedSession(page)
    await run(page)
  },
})

export { expect }

export async function expectAppShell(page: Page, currentSection: string) {
  const primaryNav = page.getByLabel("Primary navigation")
  await expect(primaryNav.getByRole("link", { name: "Dashboard" })).toBeVisible()
  await expect(primaryNav.getByRole("link", { name: "Agents" })).toBeVisible()
  await expect(page.getByText(currentSection, { exact: true }).first()).toBeVisible()
}
