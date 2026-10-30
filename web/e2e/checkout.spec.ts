import { expect, request, test } from "@playwright/test";
import { BASE_URL, adminApi, freshEmail, learnerId, postStripeEvent, signUpAndVerify } from "./helpers";

test("checkout in test mode: not connected without a key; a signed webhook opens access", async ({ page }) => {
  const email = freshEmail("pay");
  await signUpAndVerify(page, email);

  // No Stripe key in this environment: the pricing panel says so and offers no Buy button.
  await expect(page.getByRole("heading", { name: "Civics Pass", exact: true })).toBeVisible();
  await expect(page.getByText("Payments are not switched on in this environment yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Buy" })).toHaveCount(0);
  await expect(page.getByText("Free practice", { exact: true })).toBeVisible();

  // A wrongly signed event is refused.
  const anon = await request.newContext({ baseURL: BASE_URL });
  const bad = await anon.post("/api/billing/webhook", {
    data: "{}",
    headers: { "content-type": "application/json", "stripe-signature": "t=1,v1=00" },
  });
  expect(bad.status()).toBe(400);
  await anon.dispose();

  // Simulate fulfilment: a signed checkout.session.completed event for this learner.
  const admin = await adminApi();
  const uid = await learnerId(admin, email);
  const stamp = Date.now();
  const event = {
    id: `evt_e2e_${stamp}`,
    type: "checkout.session.completed",
    created: Math.floor(stamp / 1000),
    data: {
      object: {
        id: `cs_test_e2e_${stamp}`,
        object: "checkout.session",
        mode: "payment",
        payment_status: "paid",
        customer: "cus_e2e",
        client_reference_id: uid,
        payment_intent: `pi_e2e_${stamp}`,
        amount_total: 2900,
        currency: "chf",
        metadata: { product: "civics_pass_zh", canton: "zh" },
        customer_details: { email, name: "E2E Learner" },
      },
    },
  };
  expect(await postStripeEvent(event)).toBe(200);
  // A repeated event is acknowledged and not applied twice.
  expect(await postStripeEvent(event)).toBe(200);

  await page.goto("/learner");
  await expect(page.getByText(/Active until/).first()).toBeVisible();
  await expect(page.getByText(/You are using the free version/)).toHaveCount(0);
  const detail = await admin.get(`/api/admin/learners/${uid}`);
  expect(detail.payments).toHaveLength(1);
  expect(detail.entitlements.filter((e: { active: boolean }) => e.active)).toHaveLength(1);
  await admin.api.dispose();
});
