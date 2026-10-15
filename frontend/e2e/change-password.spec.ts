import { expect, test, request as pwRequest } from "@playwright/test";

/**
 * End-to-end acceptance tests for US-006: Password Change After Sign-In.
 *
 * These tests exercise the real backend HTTP stack (started by the Playwright
 * webServer config) via Playwright's APIRequestContext.  The seeded admin
 * account (satya.ganaraju@quorq.ai / admin@123) is used as the test fixture.
 *
 * Covered acceptance criteria:
 *   AC-013 — correct current password + new password → hash replaced, success
 *   AC-014 — incorrect current password → hash unchanged, error returned
 *
 * The suite runs serially (test.describe.serial) because every test mutates
 * the same seeded admin account and parallel execution would cause
 * login-failure interference.
 */

const API_BASE = "http://127.0.0.1:8000";

const ADMIN_EMAIL = "satya.ganaraju@quorq.ai";
const ADMIN_PASSWORD = "admin@123";

// The temporary password used by the AC-013 test.  Kept as a constant so the
// afterAll safety-net can attempt restoration if the test is interrupted.
const TEMP_PASSWORD = "e2e-temp-pw-789!";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the `session_id` cookie value from a `Set-Cookie` response header.
 * Returns `null` when the header is absent or does not contain the cookie.
 */
function extractSessionId(setCookie: string | null | undefined): string | null {
  if (!setCookie) return null;
  const match = setCookie.match(/session_id=([^;]+)/);
  return match ? match[1] : null;
}

/**
 * Log in via POST /auth/login and return the session_id cookie value.
 * Throws an assertion error when login does not return 200.
 */
async function login(
  request: import("@playwright/test").APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const resp = await request.post(`${API_BASE}/auth/login`, {
    data: { email, password },
  });
  expect(resp.ok(), `Login for ${email} should succeed`).toBeTruthy();
  const sessionId = extractSessionId(resp.headers()["set-cookie"]);
  expect(sessionId, "Login response should set a session_id cookie").toBeTruthy();
  return sessionId!;
}

/**
 * Call POST /auth/change-password with the given session cookie.
 */
async function changePassword(
  request: import("@playwright/test").APIRequestContext,
  sessionId: string,
  currentPassword: string,
  newPassword: string,
) {
  return request.post(`${API_BASE}/auth/change-password`, {
    data: { current_password: currentPassword, new_password: newPassword },
    headers: { Cookie: `session_id=${sessionId}` },
  });
}

// ---------------------------------------------------------------------------
// Safety net: ensure the admin password is restored to admin@123 even if a
// test is interrupted mid-flight.  We try logging in with the temp password
// first; if that succeeds, the AC-013 test changed the password but did not
// restore it, so we restore it here.
// ---------------------------------------------------------------------------

let _cleanupContext: import("@playwright/test").APIRequestContext | null = null;

test.beforeAll(async () => {
  _cleanupContext = await pwRequest.newContext();
});

test.afterAll(async () => {
  if (!_cleanupContext) return;
  try {
    // If the temp password still works, the AC-013 test left the admin in a
    // changed state — restore it.
    const loginResp = await _cleanupContext.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: TEMP_PASSWORD },
    });
    if (loginResp.ok()) {
      const sid = extractSessionId(loginResp.headers()["set-cookie"]);
      if (sid) {
        await _cleanupContext.post(`${API_BASE}/auth/change-password`, {
          data: { current_password: TEMP_PASSWORD, new_password: ADMIN_PASSWORD },
          headers: { Cookie: `session_id=${sid}` },
        });
      }
    }
  } catch {
    // Best-effort cleanup — swallow errors.
  }
  await _cleanupContext.dispose();
  _cleanupContext = null;
});

// ===========================================================================
// AC-013 — correct current password + new password → hash replaced, success
// ===========================================================================

test.describe.serial("US-006 AC-013: change password with correct current password", () => {
  test("returns success and replaces the stored hash", async ({ request }) => {
    // Login as the seeded admin.
    const sessionId = await login(request, ADMIN_EMAIL, ADMIN_PASSWORD);

    // Change the password.
    const changeResp = await changePassword(request, sessionId, ADMIN_PASSWORD, TEMP_PASSWORD);

    // Must be a success response (200 or 204).
    expect(changeResp.status(), "Change-password should return a success status").toBeLessThan(300);
    expect(changeResp.status()).toBeGreaterThanOrEqual(200);

    if (changeResp.status() === 200) {
      const body = await changeResp.json();
      expect(body).toHaveProperty("message");
    }

    // The old password must no longer work.
    const oldLoginResp = await request.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(oldLoginResp.ok(), "Old password should no longer work").toBeFalsy();

    // The new password must work.
    const newLoginResp = await request.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: TEMP_PASSWORD },
    });
    expect(newLoginResp.ok(), "New password should work").toBeTruthy();

    // Restore the admin password so subsequent tests (and test runs) can
    // log in with the original credentials.
    const restoreSessionId = extractSessionId(newLoginResp.headers()["set-cookie"]);
    expect(restoreSessionId, "New-password login should set a session cookie").toBeTruthy();
    const restoreResp = await changePassword(
      request,
      restoreSessionId!,
      TEMP_PASSWORD,
      ADMIN_PASSWORD,
    );
    expect(restoreResp.ok(), "Password restoration should succeed").toBeTruthy();

    // Verify restoration: the original password works again.
    const verifyResp = await request.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(verifyResp.ok(), "Original password should work after restoration").toBeTruthy();
  });
});

// ===========================================================================
// AC-014 — incorrect current password → hash unchanged, error returned
// ===========================================================================

test.describe.serial("US-006 AC-014: change password with incorrect current password", () => {
  test("returns an error and does not change the stored password", async ({ request }) => {
    // Login as the seeded admin.
    const sessionId = await login(request, ADMIN_EMAIL, ADMIN_PASSWORD);

    // Attempt to change the password with a wrong current password.
    const changeResp = await changePassword(
      request,
      sessionId,
      "this-is-the-wrong-password",
      "should-never-be-used-999",
    );

    // Must be an error status (>= 400), and must not be a 501 stub.
    expect(
      changeResp.status(),
      "Wrong current password should return an error",
    ).toBeGreaterThanOrEqual(400);
    expect(changeResp.status(), "Endpoint must be implemented (not a 501 stub)").not.toBe(501);

    // The error message should indicate the current password is incorrect.
    const body = await changeResp.json();
    const detail: string = (body.detail ?? "").toLowerCase();
    expect(
      detail,
      `Error message should mention the current password; got: ${body.detail}`,
    ).toMatch(/current|password/);

    // The original password must still work — the hash was not changed.
    const reloginResp = await request.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(
      reloginResp.ok(),
      "Original password should still work after a failed change",
    ).toBeTruthy();

    // The attempted new password must NOT work.
    const badLoginResp = await request.post(`${API_BASE}/auth/login`, {
      data: { email: ADMIN_EMAIL, password: "should-never-be-used-999" },
    });
    expect(badLoginResp.ok(), "The rejected new password should not work").toBeFalsy();
  });
});

// ===========================================================================
// Critical path: unauthenticated request is rejected
// ===========================================================================

test.describe.serial("US-006: change-password requires authentication", () => {
  test("returns 401 when no session cookie is provided", async ({ request }) => {
    const resp = await request.post(`${API_BASE}/auth/change-password`, {
      data: { current_password: "any-password", new_password: "new-password-123" },
    });
    expect(resp.status(), "Unauthenticated change-password should return 401").toBe(401);
  });
});
