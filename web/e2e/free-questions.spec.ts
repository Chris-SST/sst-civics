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

  // The first 30 fixture questions are the sample set; the rest need a pass.
  const inside = await page.request.get("/api/study/question/e2e-q01");
  expect(inside.status()).toBe(200);
  const beyond = await page.request.get("/api/study/question/e2e-q60");
  expect(beyond.status()).toBe(403);
  expect((await beyond.json()).detail).toBe("sample_only");
});
