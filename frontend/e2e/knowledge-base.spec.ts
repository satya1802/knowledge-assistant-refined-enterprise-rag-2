import { expect, test, request as pwRequest } from "@playwright/test";

/**
 * End-to-end acceptance tests for US-009-3: KnowledgeBase screen API integration.
 *
 * These tests verify that the KnowledgeBase screen correctly integrates with
 * the backend GET /documents and POST /documents endpoints.  They run against
 * a live backend on localhost:8000 (started by the Playwright webServer config)
 * using the seeded admin account (satya.ganaraju@quorq.ai / admin@123).
 *
 * Covered acceptance criteria:
 *   E2E — KnowledgeBase screen loads and displays documents fetched from
 *         GET /documents (AC-047)
 *   E2E — uploading a valid file via the dropzone triggers POST /documents
 *         and shows the new document in the table
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
 *
 * Uses postDataBuffer() for non-GET requests so multipart form-data (file
 * uploads) is forwarded correctly without corrupting binary content.
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
 * Upload a document via the backend API directly (used to seed data before
 * navigating to the KnowledgeBase screen).
 */
async function uploadDocumentViaApi(
  request: import("@playwright/test").APIRequestContext,
  sessionId: string,
  filename: string,
  content: string,
): Promise<{ id: string; filename: string }> {
  const boundary = "----WebKitFormBoundaryE2E" + Date.now();
  const body = [
    `--${boundary}`,
    `Content-Disposition: form-data; name="file"; filename="${filename}"`,
    "Content-Type: application/octet-stream",
    "",
    content,
    `--${boundary}--`,
    "",
  ].join("\r\n");

  const resp = await request.post(`${API_BASE}/documents`, {
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
      Cookie: `session_id=${sessionId}`,
    },
    data: body,
  });
  expect(resp.ok(), `API upload of ${filename} should succeed`).toBeTruthy();
  return await resp.json();
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe.serial("US-009-3: KnowledgeBase screen API integration", () => {
  let _apiContext: import("@playwright/test").APIRequestContext;
  let _sessionId: string;

  test.beforeAll(async () => {
    _apiContext = await pwRequest.newContext();
    _sessionId = await loginAsAdmin(_apiContext);
  });

  test.afterAll(async () => {
    await _apiContext?.dispose();
  });

  // ── E2E: KnowledgeBase screen loads and displays documents from GET /documents
  test("KnowledgeBase screen loads and displays documents fetched from GET /documents", async ({
    page,
  }) => {
    // Seed a document via the API so there is data to display.
    const uniqueFilename = `e2e-display-${Date.now()}.txt`;
    await uploadDocumentViaApi(_apiContext, _sessionId, uniqueFilename, "e2e display content");

    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/knowledge-base");

    // The page heading should be visible.
    await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible();

    // Wait for the loading spinner to disappear and the seeded document to
    // appear in the table.
    await expect(page.getByText(uniqueFilename)).toBeVisible({ timeout: 15_000 });
  });

  // ── E2E: uploading a valid file via the dropzone triggers POST /documents
  //         and shows the new document in the table
  test("uploading a valid file via the dropzone triggers POST /documents and shows the new document", async ({
    page,
  }) => {
    await installApiProxy(page, _apiContext, _sessionId);

    await page.goto("/knowledge-base");

    // Wait for the page to finish loading (either empty state or documents).
    await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible();
    // Wait for loading to complete — the dropzone should be visible for admin.
    await expect(page.getByText("Drop a file here or click to browse")).toBeVisible({
      timeout: 15_000,
    });

    const uploadFilename = `e2e-upload-${Date.now()}.txt`;

    // Upload via the hidden file input — this triggers handleFileInputChange
    // → handleFileUpload → apiUpload("/documents", file) → POST /documents.
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: uploadFilename,
      mimeType: "text/plain",
      buffer: Buffer.from("e2e upload test content"),
    });

    // The uploaded document's filename must appear in the table.
    await expect(page.getByText(uploadFilename)).toBeVisible({ timeout: 15_000 });
  });
});
