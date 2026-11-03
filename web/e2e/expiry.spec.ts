import { expect, test } from "@playwright/test";
import { adminApi, freshEmail, learnerId, signUpAndVerify } from "./helpers";

test("a pass that expired yesterday leaves the learner on the free tier with the free Explain this", async ({ page }) => {
  const email = freshEmail("expired");
  await signUpAndVerify(page, email);

  const admin = await adminApi();
  const uid = await learnerId(admin, email);
  const day = 24 * 3600 * 1000;
  const granted = await admin.post(`/api/admin/users/${uid}/entitlements`, {
    canton: "zh",
    starts_at: new Date(Date.now() - 30 * day).toISOString(),
    expires_at: new Date(Date.now() - day).toISOString(),
    source: "admin",
  });
  expect(granted.status).toBe(201);
  expect(granted.body.active).toBe(false);
  await admin.api.dispose();

  await page.goto("/learner");
  await expect(page.getByText(/You are using the free version/)).toBeVisible();
  await expect(page.getByText(/Ended on/)).toBeVisible();
  expect((await page.request.get("/api/study/question/e2e-q60")).status()).toBe(403);

  // Explain this on a sample question works within the free allowance, as for any free learner.
  await page.goto("/practise");
  await page.getByRole("radio").first().click();
  await page.getByRole("button", { name: "Check answer" }).click();
  await page.getByRole("button", { name: "Explain this" }).click();
  await expect(page.getByText("Free account: 3 messages a day on the sample questions.")).toBeVisible();
});
