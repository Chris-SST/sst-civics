import { expect, test } from "@playwright/test";
import { adminApi, emailCount, freshEmail, linkFromEmail, signUpAndVerify } from "./helpers";

test("a learner deletes the account after re-authenticating with a fresh sign-in link", async ({ page }) => {
  const email = freshEmail("delete");
  await signUpAndVerify(page, email);

  // Sign out and back in with a link: that link is the re-authentication (valid for ten minutes).
  await page.getByRole("button", { name: "Log out" }).click();
  const seen = emailCount(email);
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send me a sign-in link" }).click();
  await page.goto(await linkFromEmail(email, seen));
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();

  await page.getByRole("link", { name: "Account" }).click();
  await expect(page.getByText(/no password is needed/)).toBeVisible();
  const remove = page.getByRole("button", { name: "Delete my account" });
  await expect(remove).toBeDisabled();
  await page.getByLabel(/I understand that my account/).check();
  await expect(remove).toBeEnabled();
  await remove.click();
  await expect(page.getByRole("heading", { name: "Your account is deleted" })).toBeVisible();

  // The account is gone and the session no longer works.
  expect((await page.request.get("/api/auth/me")).status()).toBeGreaterThanOrEqual(401);
  const admin = await adminApi();
  const rows = (await admin.get(`/api/admin/learners?q=${encodeURIComponent(email)}`)) as unknown[];
  expect(rows).toHaveLength(0);
  await admin.api.dispose();
});
