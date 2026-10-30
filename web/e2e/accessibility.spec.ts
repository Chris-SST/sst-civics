import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { adminLoginUi, freshEmail, linkFromEmail, signUpAndVerify } from "./helpers";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** Serious and critical axe violations on the current page, as short readable lines. */
async function violations(page: Page, name: string): Promise<string[]> {
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${name}: ${v.id} (${v.impact}) ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
}

/** Press Tab until `target` has focus (at most `max` presses). */
async function tabTo(page: Page, target: Locator, max = 40): Promise<void> {
  for (let i = 0; i < max; i += 1) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return;
  }
  throw new Error("Could not reach the element with the keyboard");
}

test("the main screens have no serious or critical accessibility violations", async ({ page, browser }) => {
  test.setTimeout(180_000);
  const found: string[] = [];

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  found.push(...(await violations(page, "landing")));

  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  found.push(...(await violations(page, "sign-up")));

  await signUpAndVerify(page, freshEmail("axe"));
  await expect(page.getByRole("heading", { name: /Readiness for the/ })).toBeVisible();
  found.push(...(await violations(page, "learner home")));

  await page.goto("/practise");
  await expect(page.getByRole("radio").first()).toBeVisible();
  found.push(...(await violations(page, "practise")));
  await page.getByRole("radio").first().click();
  await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByText("Answer", { exact: true }).first()).toBeVisible();
  found.push(...(await violations(page, "practise, answered")));

  await page.goto("/mock");
  await expect(page.getByRole("button", { name: "Start the mock test" })).toBeVisible();
  found.push(...(await violations(page, "mock intro")));
  await page.getByRole("button", { name: "Start the mock test" }).click();
  await expect(page.getByRole("radio").first()).toBeVisible();
  found.push(...(await violations(page, "mock test")));

  await page.goto("/account");
  await expect(page.getByRole("heading", { name: "Your account" })).toBeVisible();
  found.push(...(await violations(page, "account")));

  const adminContext = await browser.newContext({ baseURL: page.url().split("/").slice(0, 3).join("/"), locale: "en-GB", serviceWorkers: "block" });
  const admin = await adminContext.newPage();
  await adminLoginUi(admin);
  await admin.goto("/admin/learners");
  await expect(admin.getByRole("table")).toBeVisible();
  found.push(...(await violations(admin, "admin learners")));
  await adminContext.close();

  expect(found, found.join("\n")).toEqual([]);
});

test("sign-up and one practise answer work with the keyboard alone", async ({ page }) => {
  const email = freshEmail("keys");
  await page.goto("/signup");

  await tabTo(page, page.getByLabel("Email address"));
  await page.keyboard.type(email);
  await tabTo(page, page.getByLabel("I am 16 or older"));
  await page.keyboard.press("Space");
  await tabTo(page, page.getByLabel(/I accept the/));
  await page.keyboard.press("Space");
  await tabTo(page, page.getByRole("button", { name: "Create account" }));
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();

  await page.goto(await linkFromEmail(email));
  await expect(page.getByText("Your email address is confirmed and you are signed in.")).toBeVisible();
  await page.goto("/practise");
  await expect(page.getByRole("radio").first()).toBeVisible();

  const option = page.getByRole("radio").first();
  await tabTo(page, option);
  await expect(option).toBeFocused();
  await page.keyboard.press("Space");
  await expect(option).toHaveAttribute("aria-checked", "true");
  await tabTo(page, page.getByRole("button", { name: "Check answer" }));
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Next question|See your round/ })).toBeVisible();
  await expect(page.getByText("Answer", { exact: true }).first()).toBeVisible();
});
