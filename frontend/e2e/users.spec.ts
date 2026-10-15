import { expect, test, request as pwRequest } from "@playwright/test";

/**
 * End-to-end acceptance tests for US-007-3: Users screen API integration.
 *
 * These tests verify that the Users screen correctly integrates with the
 * backend GET /users and POST /users endpoints.  They run against a live
 * backend on localhost:8000 (started by the Playwright webServer config)
 * using the seeded admin account (satya.ganaraju@quorq.ai / admin@123).
 *
 * Covered acceptance criteria:
 *   E2E — Users screen loads and displays users fetched from GET /users
 *   E2E — creating a user via the form results in a new row in the table
 *   E2E — duplicate email submission shows an inline error message
 *
 * CORS note: The frontend preview server runs on port 4173 while the CORS
 * middleware only allows port 5173 by default.  To avoid CORS blocking
 * cross-origin credentialed requests from the browser, page.route() is used
 * to proxy API calls through Playwright's APIRequestContext — the real
 * backend still processes every request, so the integration is genuinely
 * end-to-end.
 */

const API_BASE = "http://localhost:8000";

const ADMIN_EMAIL = "satya.ganaraju@quorq.ai";
const ADMIN_PASSWORD = "admin@123";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractSessionId(setCookie: string | null | undefined): string | null {
  if (!setCookie) return null;
  const match = setCookie.match(/session_id=([^;]+)/);
  return match ? match[1] : null;
}

async function loginAsAdmin(
  request: import("@playwright/test").APIRequestContext,
): Promise<string> {
  const resp = await request.post(`${API_BASE}/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  expect(resp.ok(), "Admin login should succeed").toBeTruthy();
  const sessionId = extractSessionId(resp.headers()["set-cookie"]);
  expect(sessionId, "Login should set a session_id cookie").toBeTruthy();
  return sessionId!;
}

type FetchOpts = import("@playwright/test").APIRequestContextOptions;

/**
 * Install a page.route() handler that proxies every API call to the real
 * backend via Playwright's APIRequestContext, attaching the session cookie.
 * This bypasses browser CORS restrictions while still hitting the real
 * backend — the integration under test.
 */
async function installApiProxy(
  page: import("@playwright/test").Page,
  apiContext: import("@playwright/test").APIRequestContext,
  sessionId: string,
): Promise<void> {
  await page.route(`${API_BASE}/**`, async (route) => {
    const req = route.request();
    const headers: Record<string, string> = {
      ...req.headers(),
      Cookie: `session_id=${sessionId}`,
    };
    const fetchOpts: FetchOpts = {
      method: req.method(),
      headers,
    };
    if (req.method() !== "GET" && req.method() !== "HEAD" && req.postData()) {
      fetchOpts.data = req.postData()!;
    }
    const resp = await apiContext.fetch(req.url(), fetchOpts);
    const body = await resp.body();
    await route.fulfill({
      status: resp.status(),
      contentType: resp.headers()["content-type"] || "application/json",
      body: body,
    });
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe.serial("US-007-3: Users screen API integration", () => {
  let _apiContext: import("@playwright/test").APIRequestContext;
  let _sessionId: string;

  test.beforeAll(async () => {
    _apiContext = await pwRequest.newContext();
    _sessionId = await loginAsAdmin(_apiContext);
  });

  test.afterAll(async () => {
    await _apiContext?.dispose();
  });

  // ── E2E: Users screen loads and displays users from GET /users ────────────
  test("Users screen loads and displays users fetched from GET /users", async ({ page }) => {
    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/users");

    // The page heading should be visible.
    await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible();

    // Wait for the loading spinner to disappear and users to render.
    // The seeded admin email must appear in the table.
    await expect(page.getByText(ADMIN_EMAIL)).toBeVisible({ timeout: 15_000 });
  });

  // ── E2E: creating a user via the form results in a new row ────────────────
  test("creating a user via the form results in a new row in the table", async ({ page }) => {
    const uniqueEmail = `e2e-create-${Date.now()}@example.com`;
    const uniquePassword = "e2e-test-password-123";

    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/users");

    // Wait for users to load.
    await expect(page.getByText(ADMIN_EMAIL)).toBeVisible({ timeout: 15_000 });

    // Open the create-user form.
    await page.getByRole("button", { name: "New User" }).click();

    // Fill in the form.
    await page.locator("#new-email").fill(uniqueEmail);
    await page.locator("#new-password").fill(uniquePassword);
    // Role defaults to "Regular User" — leave it as is.

    // Submit the form.
    await page.getByRole("button", { name: "Create account" }).click();

    // The new row with the unique email must appear in the table.
    await expect(page.getByText(uniqueEmail)).toBeVisible({ timeout: 15_000 });

    // A success banner should also be visible.
    await expect(page.getByText(/Account created for/)).toBeVisible({ timeout: 10_000 });
  });

  // ── E2E: duplicate email shows an inline error ────────────────────────────
  test("duplicate email submission shows an inline error message", async ({ page }) => {
    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/users");

    // Wait for users to load (the seeded admin is in the list).
    await expect(page.getByText(ADMIN_EMAIL)).toBeVisible({ timeout: 15_000 });

    // Open the create-user form.
    await page.getByRole("button", { name: "New User" }).click();

    // Enter the seeded admin email — already in the users list.
    await page.locator("#new-email").fill(ADMIN_EMAIL);
    await page.locator("#new-password").fill("any-valid-password-123");

    // Submit the form.
    await page.getByRole("button", { name: "Create account" }).click();

    // An inline error message must appear next to the email field.
    await expect(page.getByText("A user with this email already exists")).toBeVisible({
      timeout: 10_000,
    });
  });
});
