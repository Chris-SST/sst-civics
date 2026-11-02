import { expect, test } from "@playwright/test";
import { freshEmail, signUpAndVerify } from "./helpers";

// The help chat (D-066) for a learner without a pass: the free allowance, a suggested question,
// the streamed reply (LLM_FAKE answers with the demo reply) and a fresh conversation.
test("a free learner asks the help chat and starts a new conversation", async ({ page }) => {
  const email = freshEmail("help");
  await signUpAndVerify(page, email);

  await expect(page.getByRole("heading", { name: "Questions? Ask Viapunt" })).toBeVisible();
  await page.getByRole("link", { name: "Open the help chat" }).click();
  await expect(page.getByRole("heading", { name: "Ask Viapunt" })).toBeVisible();
  await expect(page.getByText(/Free account: a few questions a day/)).toBeVisible();

  // A suggested question goes out as the learner's message and gets a reply.
  await page.getByRole("button", { name: "How does the knowledge test work?" }).click();
  const log = page.getByRole("log");
  await expect(log.getByText("How does the knowledge test work?")).toBeVisible();
  await expect(log.getByText(/Switzerland is a federal state/)).toBeVisible();
  await expect(page.getByText("4 of 5 messages left today")).toBeVisible();

  // A typed follow-up, sent with Enter.
  const box = page.getByRole("textbox", { name: /Type your question/ });
  await box.fill("And how many cantons are there?");
  await box.press("Enter");
  await expect(log.getByText("And how many cantons are there?")).toBeVisible();
  await expect(page.getByText("3 of 5 messages left today")).toBeVisible();

  // The conversation is kept when the page is opened again ...
  await page.goto("/help");
  await expect(page.getByRole("log").getByText("And how many cantons are there?")).toBeVisible();

  // ... until the learner starts a new one; the daily count stays.
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByRole("button", { name: "How does the knowledge test work?" })).toBeVisible();
  await expect(page.getByRole("log").getByText("And how many cantons are there?")).toHaveCount(0);
  await expect(page.getByText("3 of 5 messages left today")).toBeVisible();

  // Explain this stays a paid feature.
  const explain = await page.request.post("/api/explain/start", {
    data: { question_id: "e2e-q01" },
    headers: { "X-CSRF-Token": (await page.context().cookies()).find((c) => c.name === "sst_csrf")?.value ?? "" },
  });
  expect(explain.status()).toBe(403);
});
