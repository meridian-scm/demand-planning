import { expect, test } from "@playwright/test";

test.describe("Products", () => {
  test("lists the seeded products", async ({ page }) => {
    await page.goto("/products");
    await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
    await expect(page.locator(".table tbody tr").first()).toBeVisible({ timeout: 15_000 });
  });

  test("filters the product list by search term", async ({ page }) => {
    await page.goto("/products");
    await expect(page.locator(".table tbody tr").first()).toBeVisible({ timeout: 15_000 });

    await page.getByPlaceholder("Search by SKU or name…").fill("Sparkling");
    await expect(page.getByText("Sparkling Water")).toBeVisible();
    await expect(page.locator(".table tbody tr")).toHaveCount(1);
  });

  test("creates a new product end to end", async ({ page }) => {
    const sku = `E2E-${Date.now()}`;
    await page.goto("/products");

    await page.getByRole("button", { name: "+ New Product" }).click();
    await page.locator("#sku").fill(sku);
    await page.locator("#name").fill("Playwright Test Widget");
    await page.locator("#category").fill("QA");
    await page.getByRole("button", { name: "Create Product" }).click();

    // Form closes and the new row appears in the (now-filtered-by-nothing) list.
    await expect(page.getByRole("button", { name: "+ New Product" })).toBeVisible();
    await page.getByPlaceholder("Search by SKU or name…").fill(sku);
    await expect(page.getByText(sku.toUpperCase())).toBeVisible({ timeout: 10_000 });
  });

  test("rejects a duplicate SKU with a visible error", async ({ page }) => {
    await page.goto("/products");
    await expect(page.locator(".table tbody tr").first()).toBeVisible({ timeout: 15_000 });

    const firstSku = await page.locator(".table tbody tr").first().locator("td").first().innerText();

    await page.getByRole("button", { name: "+ New Product" }).click();
    await page.locator("#sku").fill(firstSku.trim());
    await page.locator("#name").fill("Duplicate Attempt");
    await page.locator("#category").fill("QA");
    await page.getByRole("button", { name: "Create Product" }).click();

    await expect(page.getByRole("alert")).toContainText(/already exists/i);
  });

  test("drills into a product detail page", async ({ page }) => {
    await page.goto("/products");
    await expect(page.locator(".table tbody tr").first()).toBeVisible({ timeout: 15_000 });

    const firstSkuLink = page.locator(".table tbody tr").first().locator("a").first();
    const skuText = await firstSkuLink.innerText();
    await firstSkuLink.click();

    await expect(page).toHaveURL(/\/products\/\d+$/);
    await expect(page.getByText(skuText)).toBeVisible();
    // The section heading and an empty-state message ("No open exceptions")
    // both contain this text, so target the heading role specifically.
    await expect(page.getByRole("heading", { name: "Open Exceptions" })).toBeVisible();
  });
});
