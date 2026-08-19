import { expect, test } from "@playwright/test";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

test.describe("CSV data upload", () => {
  test("uploads a well-formed CSV and shows the import summary", async ({ page }) => {
    // Uses the first seeded SKU so the upload targets a product that already
    // exists, matching the real workflow of refreshing an existing SKU's history.
    await page.goto("/products");
    await expect(page.locator(".table tbody tr").first()).toBeVisible({ timeout: 15_000 });
    const sku = (await page.locator(".table tbody tr").first().locator("td").first().innerText()).trim();

    const csvPath = path.join(tmpdir(), `e2e-upload-${Date.now()}.csv`);
    writeFileSync(
      csvPath,
      `sku,period_start,units_sold\n${sku},2025-01-01,999\n${sku},2025-02-01,1050\n`,
    );

    await page.goto("/data");
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Choose CSV File" }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(csvPath);

    await expect(page.getByText("Import Result")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Rows Received")).toBeVisible();
  });

  test("surfaces row-level errors for a malformed CSV", async ({ page }) => {
    const csvPath = path.join(tmpdir(), `e2e-bad-upload-${Date.now()}.csv`);
    writeFileSync(
      csvPath,
      "sku,period_start,units_sold\nSKU-DOES-NOT-EXIST,2025-01-01,10\n",
    );

    await page.goto("/data");
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Choose CSV File" }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(csvPath);

    await expect(page.getByText("Import Result")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("1")).toBeVisible(); // rows rejected
  });
});
