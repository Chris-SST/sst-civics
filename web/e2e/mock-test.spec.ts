import { expect, test } from "@playwright/test";
import { adminLoginUi, freshEmail, signUpAndVerify } from "./helpers";

test("an admin grants a pass; the learner takes a 50-question mock test and reviews it", async ({ page, browser }) => {
  test.setTimeout(180_000);
  const email = freshEmail("mock");
  await signUpAndVerify(page, email);

  // The admin, in a second browser context, grants access through the admin area.
  const adminContext = await browser.newContext({ baseURL: page.url().split("/").slice(0, 3).join("/"), locale: "en-GB", serviceWorkers: "block" });
  const admin = await adminContext.newPage();
  await adminLoginUi(admin);
  await admin.goto("/admin/learners");
  await admin.getByPlaceholder("Search by email").fill(email);
  await admin.getByRole("row", { name: new RegExp(email) }).getByRole("button", { name: "Open" }).click();
  await admin.getByRole("button", { name: "Grant", exact: true }).click();
  await expect(admin.getByText(/Access for Zurich granted until/)).toBeVisible();
  await adminContext.close();

  // The learner: the pass shows, the mock test starts and has 50 questions.
  await page.goto("/learner");
  await expect(page.getByText("Active until").first()).toBeVisible();
  await page.goto("/mock");
  await expect(page.getByText("50 questions, 60 minutes, four options each")).toBeVisible();
  await expect(page.getByText("(not yet confirmed by the canton)")).toBeVisible();
  await page.getByRole("button", { name: "Start the mock test" }).click();
  await expect(page.getByText("0 of 50 answered")).toBeVisible();

  for (let i = 0; i < 50; i += 1) {
    await page.getByRole("radio").first().click();
    await expect(page.getByText(`${i + 1} of 50 answered`)).toBeVisible();
    if (i < 49) await page.getByRole("button", { name: "Next", exact: true }).click();
  }

  await page.getByRole("button", { name: "Hand in", exact: true }).click();
  await page.getByRole("button", { name: "Hand in now" }).click();

  await expect(page.getByRole("heading", { name: "Your result" })).toBeVisible();
  await expect(page.getByText(/^\d+ \/ 50$/)).toBeVisible();
  await expect(page.getByText("Pass mark: 30 of 50")).toBeVisible();
  await expect(page.getByText("(not yet confirmed by the canton)")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your wrong answers" })).toBeVisible();
  await expect(page.locator("article.question-card").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Explain this" })).toHaveCount(0);
});
