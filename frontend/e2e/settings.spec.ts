import { expect, test, request as pwRequest } from "@playwright/test";

/**
 * End-to-end acceptance tests for US-031-3: Settings screen API integration.
 *
 * These tests verify that the Settings screen correctly integrates with the
 * backend GET /settings and PATCH /settings endpoints.  They run against a
 * live backend on localhost:8000 (started by the Playwright webServer config)
 * using the seeded admin account (satya.ganaraju@quorq.ai / admin@123).
 *
 * Covered acceptance criteria:
 *   E2E — Settings screen loads and displays values fetched from GET /settings
 *   E2E — saving settings via the form triggers PATCH /settings and shows a
 *         success indicator
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
    if (req.method() !== "GET" && req.method() !== "HEAD") {
      const postDataBuffer = req.postDataBuffer();
      if (postDataBuffer) {
        fetchOpts.data = postDataBuffer;
      }
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

/**
 * Read the current settings from the backend via the API (used for
 * verification and for restoring original values after the test).
 */
async function getSettings(
  request: import("@playwright/test").APIRequestContext,
  sessionId: string,
): Promise<{
  gemini_answer_model: string;
  gemini_embedding_model: string;
  cosine_threshold: number;
  cookie_secure_flag: boolean;
}> {
  const resp = await request.get(`${API_BASE}/settings`, {
    headers: { Cookie: `session_id=${sessionId}` },
  });
  expect(resp.ok(), "GET /settings should succeed for admin").toBeTruthy();
  return await resp.json();
}

/**
 * PATCH settings via the backend API directly (used for restoring values).
 */
async function patchSettings(
  request: import("@playwright/test").APIRequestContext,
  sessionId: string,
  payload: Record<string, unknown>,
) {
  const resp = await request.patch(`${API_BASE}/settings`, {
    headers: { Cookie: `session_id=${sessionId}` },
    data: payload,
  });
  expect(resp.ok(), "PATCH /settings should succeed for admin").toBeTruthy();
  return await resp.json();
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe.serial("US-031-3: Settings screen API integration", () => {
  let _apiContext: import("@playwright/test").APIRequestContext;
  let _sessionId: string;
  let _originalSettings: {
    gemini_answer_model: string;
    gemini_embedding_model: string;
    cosine_threshold: number;
    cookie_secure_flag: boolean;
  };

  test.beforeAll(async () => {
    _apiContext = await pwRequest.newContext();
    _sessionId = await loginAsAdmin(_apiContext);
    _originalSettings = await getSettings(_apiContext, _sessionId);
  });

  test.afterAll(async () => {
    if (_apiContext && _sessionId && _originalSettings) {
      try {
        await patchSettings(_apiContext, _sessionId, _originalSettings);
      } catch {
        // Best-effort restore — swallow errors.
      }
    }
    await _apiContext?.dispose();
  });

  // ── E2E: Settings screen loads and displays values fetched from GET /settings
  test("Settings screen loads and displays values fetched from GET /settings", async ({ page }) => {
    // Read the current API values so we can assert the screen reflects them.
    const apiSettings = await getSettings(_apiContext, _sessionId);

    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/settings");

    // The page heading should be visible.
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    // The threshold input must reflect the value from GET /settings.
    const thresholdInput = page.locator("#cosine-threshold");
    await expect(thresholdInput).toBeVisible({ timeout: 15_000 });
    await expect(thresholdInput).toHaveValue(String(apiSettings.cosine_threshold));

    // The answer-model select must reflect the value from GET /settings.
    const answerSelect = page.locator("#answer-model");
    await expect(answerSelect).toHaveValue(apiSettings.gemini_answer_model);

    // The embedding-model select must reflect the value from GET /settings.
    const embeddingSelect = page.locator("#embedding-model");
    await expect(embeddingSelect).toHaveValue(apiSettings.gemini_embedding_model);
  });

  // ── E2E: saving settings via the form triggers PATCH /settings and shows success
  test("saving settings via the form triggers PATCH /settings and shows a success indicator", async ({
    page,
  }) => {
    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/settings");

    // Wait for the page to finish loading.
    const thresholdInput = page.locator("#cosine-threshold");
    await expect(thresholdInput).toBeVisible({ timeout: 15_000 });

    // Change the cosine threshold to a new value.
    const newValue = 0.63;
    await thresholdInput.fill(String(newValue));

    // The "Save Settings" button should become enabled (dirty state).
    const saveButton = page.getByRole("button", { name: "Save Settings" });
    await expect(saveButton).toBeEnabled();

    // Submit the form.
    await saveButton.click();

    // A success indicator must appear ("Changes saved").
    await expect(page.getByText("Changes saved")).toBeVisible({ timeout: 15_000 });

    // Verify the PATCH was persisted by reading the API directly.
    const updated = await getSettings(_apiContext, _sessionId);
    expect(updated.cosine_threshold).toBe(newValue);

    // Restore the original value so subsequent test runs start clean.
    await patchSettings(_apiContext, _sessionId, {
      cosine_threshold: _originalSettings.cosine_threshold,
    });
  });
});
