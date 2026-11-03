import { expect, test } from "@playwright/test";
import { freshEmail, signUpAndVerify } from "./helpers";

test("a new learner practises the sample set and is refused beyond it", async ({ page }) => {
  const email = freshEmail("free");
  await signUpAndVerify(page, email);

  // Home: the Zurich topics and the free-version notice.
  await expect(page.getByText(/You are using the free version: 30 sample questions/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Test topics: Zurich" })).toBeVisible();
  for (const topic of ["Federal authorities", "Popular rights", "Canton of Zurich"]) {
    await expect(page.getByRole("button", { name: new RegExp(topic) })).toBeVisible();
  }

  // Practise one sample question.
  await page.getByRole("link", { name: /Start practising/ }).click();
  await expect(page.getByText("Free version: the questions come from the sample set.")).toBeVisible();
  await page.getByRole("radio").first().click();
  await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByRole("button", { name: /Next question|See your round/ })).toBeVisible();
  // The explanation shows after answering, and Explain this is open on the sample questions.
  await expect(page.locator(".result .solution").first()).not.toBeEmpty();
  await page.getByRole("button", { name: "Explain this" }).click();
  await expect(page.getByText("Free account: 3 messages a day on the sample questions.")).toBeVisible();

  // The first 30 fixture questions are the sample set; the rest need a pass.
  const inside = await page.request.get("/api/study/question/e2e-q01");
  expect(inside.status()).toBe(200);
  const beyond = await page.request.get("/api/study/question/e2e-q60");
  expect(beyond.status()).toBe(403);
  expect((await beyond.json()).detail).toBe("sample_only");
});

test("a free learner checks where they stand, once a day", async ({ page }) => {
  test.setTimeout(120_000);
  const email = freshEmail("check");
  await signUpAndVerify(page, email);

  await expect(page.getByRole("heading", { name: "Check where you stand" })).toBeVisible();
  await expect(page.getByText("20 questions, about 10 minutes. See how ready you are in each topic area.")).toBeVisible();
  await page.getByRole("link", { name: "Start the check" }).click();
  await expect(page.getByText("Free account: one check a day. With a Viapunt Pass, as many as you like.")).toBeVisible();
  await page.getByRole("button", { name: "Start the check" }).click();
  await expect(page.getByText("0 of 20 answered")).toBeVisible();
  await expect(page.getByText(/Time left/)).toHaveCount(0);

  for (let i = 0; i < 3; i += 1) {
    await page.getByRole("radio").first().click();
    await expect(page.getByText(`${i + 1} of 20 answered`)).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
  }
  await page.getByRole("button", { name: "Check my answers" }).click();
  await expect(page.getByText("17 questions are still unanswered. Check your answers anyway?")).toBeVisible();
  await page.getByRole("button", { name: "Check now" }).click();

  await expect(page.getByRole("heading", { name: "Where you stand" })).toBeVisible();
  await expect(page.getByText(/^\d+ of 20 right \(\d+%\)$/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "By topic area" })).toBeVisible();
  await expect(page.getByRole("link", { name: "See the Viapunt Pass" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Explain this" })).toHaveCount(0);

  // One a day without a pass.
  await page.goto("/readiness");
  await expect(page.getByText("You have done today's free check. The next one is available tomorrow.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start the check" })).toBeDisabled();
});
