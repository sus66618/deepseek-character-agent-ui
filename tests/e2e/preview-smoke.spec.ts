import { expect, test } from "@playwright/test";

test("preview displays the character UI label", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("preview-root")).toHaveText("DeepSeek Character UI");
});
