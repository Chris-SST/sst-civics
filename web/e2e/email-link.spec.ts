import { expect, test } from "@playwright/test";
import { emailCount, freshEmail, linkFromEmail, signUpAndVerify } from "./helpers";

test("signing in with an emailed link lands the learner signed in", async ({ page }) => {
  const email = freshEmail("link");
  await signUpAndVerify(page, email);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();

  const seen = emailCount(email);
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send me a sign-in link" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();

  await page.goto(await linkFromEmail(email, seen));
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
});
