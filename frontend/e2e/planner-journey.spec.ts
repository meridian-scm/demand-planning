import { expect, test } from '@playwright/test';

const referenceSku = 'SKU-00001';

test('backend health and reference artifacts are ready', async ({ request }) => {
  const backendURL = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000';

  const healthResponse = await request.get(`${backendURL}/api/health`);
  expect(healthResponse.ok()).toBeTruthy();
  await expect(healthResponse.json()).resolves.toMatchObject({ service: 'meridian-backend' });

  const readinessResponse = await request.get(`${backendURL}/api/ready`);
  expect(readinessResponse.ok()).toBeTruthy();
  await expect(readinessResponse.json()).resolves.toMatchObject({
    status: 'ready',
    data_ready: true,
  });
});

test('demand planner can review the complete planning journey', async ({ page }) => {
  await test.step('review the portfolio overview and change store scope', async () => {
    await page.goto('/');

    await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();
    await expect(page.getByLabel('Demand summary')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Validation evidence' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Priority planning exceptions' })).toBeVisible();

    const storeFilter = page.getByLabel('Overview store');
    await expect(storeFilter.locator('option')).toHaveCount(6);
    await storeFilter.selectOption({ index: 1 });
    await expect(page.getByText(/120 Store \+ SKU series/)).not.toBeVisible();
    await expect(page.getByText(/24 Store \+ SKU series/)).toBeVisible();
  });

  await test.step('select a Store + SKU and inspect its demand evidence', async () => {
    await page.getByRole('link', { name: 'Demand Explorer' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Demand Explorer' })).toBeVisible();

    const storeFilter = page.getByLabel('Store', { exact: true });
    await expect(storeFilter.locator('option')).toHaveCount(5);

    const search = page.getByLabel('Search SKU or product');
    await search.fill(referenceSku);
    const productFilter = page.getByLabel('SKU or product', { exact: true });
    await expect(productFilter.locator('option')).toHaveCount(1);
    await productFilter.selectOption('product-00001');

    await expect(page.getByText(referenceSku, { exact: true })).toBeVisible();
    await expect(page.getByLabel('Demand key performance indicators')).toBeVisible();
    await expect(
      page.getByRole('img', { name: `Historical monthly demand chart for ${referenceSku}` }),
    ).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Demand signals' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Inventory risk' })).toBeVisible();
    await expect(page.getByLabel('Projected inventory calculation')).toBeVisible();
  });

  await test.step('generate a validated forecast and inspect uncertainty', async () => {
    await page.getByLabel('Forecast horizon').selectOption('6');
    await page.getByRole('button', { name: 'Generate forecast' }).click();

    await expect(page.getByText('Selected model')).toBeVisible({ timeout: 60_000 });
    const metrics = page.getByLabel('Forecast validation metrics');
    await expect(metrics).toBeVisible();
    await expect(metrics.getByText('WAPE', { exact: true })).toBeVisible();
    await expect(metrics.getByText('MASE', { exact: true })).toBeVisible();
    await expect(metrics.getByText('RMSE', { exact: true })).toBeVisible();
    await expect(metrics.getByText('Bias', { exact: true })).toBeVisible();
    await expect(metrics.getByText('Interval coverage', { exact: true })).toBeVisible();
    await expect(
      page.getByRole('img', {
        name: `Actual and forecast monthly demand chart for ${referenceSku}`,
      }),
    ).toBeVisible();
    await expect(page.getByText(/shaded band is its 90% prediction interval/)).toBeVisible();
  });

  await test.step('review planning exceptions for the selected SKU', async () => {
    await page.getByRole('link', { name: 'Planning Exceptions' }).click();
    await expect(
      page.getByRole('heading', { level: 1, name: 'Planning Exceptions' }),
    ).toBeVisible();

    await page.getByLabel('Search exception SKU or product').fill(referenceSku);
    await expect(page.getByLabel('Exception SKU or product').locator('option')).toHaveCount(1);
    await expect(page.getByRole('heading', { name: 'Exception queue' })).toBeVisible();
    await expect(page.getByLabel('Exception summary')).toBeVisible();
  });

  await test.step('inspect the immutable published forecast run', async () => {
    await page.getByRole('link', { name: 'Forecast Runs' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Forecast Runs' })).toBeVisible();
    await expect(page.getByText('Published run', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Forecast run summary')).toBeVisible();

    await page.getByLabel('Search forecast series').fill(referenceSku);
    await expect(page.getByLabel('Forecast series results').getByRole('button')).toHaveCount(5);
    await expect(page.getByRole('heading', { name: /Northstar Herbal Tea/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Candidate evaluation' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Published forecast' })).toBeVisible();
  });
});
