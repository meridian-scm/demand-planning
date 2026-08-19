import { expect, test } from "@playwright/test";

test.describe("Dashboard", () => {
  test("loads and shows the KPI tiles for the seeded portfolio", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Demand Planning Dashboard" })).toBeVisible();

    const kpis = page.locator('[data-testid="kpi-tile"]');
    await expect(kpis.first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Active Products")).toBeVisible();
    await expect(page.getByText("Open Exceptions")).toBeVisible();
  });

  test("renders the demand chart once history loads", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Demand: Actual vs. Forecast")).toBeVisible();
    // Recharts renders an SVG once data is available.
    await expect(page.locator(".recharts-surface").first()).toBeVisible({ timeout: 15_000 });
  });

  test("navigates to the forecast page from the primary action", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Run Forecast Cycle" }).click();
    await expect(page).toHaveURL(/\/forecast$/);
    await expect(page.getByRole("heading", { name: "Run Forecast Cycle" })).toBeVisible();
  });

  test("sidebar navigation reaches every primary section", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Products" }).click();
    await expect(page).toHaveURL(/\/products$/);

    await page.getByRole("link", { name: "Exceptions" }).click();
    await expect(page).toHaveURL(/\/exceptions$/);

    await page.getByRole("link", { name: "Data Upload" }).click();
    await expect(page).toHaveURL(/\/data$/);

    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL("/");
  });

  test("generates a portfolio AI insight", async ({ page }) => {
    await page.goto("/");
    const generateButton = page.getByRole("button", { name: /generate/i });
    await generateButton.click();
    await expect(page.getByText(/AI Insight/i)).toBeVisible();
    // Provenance must always be shown honestly — "template summary" when no
    // LLM produced the text, or "<model> via <provider>" (ollama/groq) when
    // one did. Never silently blank or a hardcoded provider name.
    await expect(page.getByText(/template summary|via (ollama|groq)/)).toBeVisible({
      timeout: 10_000,
    });
  });
});
