import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock the api module so tests don't hit the network.
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(message: string, status: number, body?: unknown) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.body = body;
    }
  }
  return {
    apiFetch: vi.fn(),
    ApiError,
    API_BASE_URL: "http://localhost:8000",
  };
});

import { apiFetch } from "@/lib/api";
import Settings from "@/screens/Settings";

const mockedApiFetch = vi.mocked(apiFetch);

/* eslint-disable @typescript-eslint/no-explicit-any */

function makeSettings(overrides?: any) {
  return {
    gemini_answer_model: "gemini-2.0-flash",
    gemini_embedding_model: "text-embedding-004",
    cosine_threshold: 0.62,
    cookie_secure_flag: true,
    ...overrides,
  };
}

function renderScreen() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  );
}

function statusError(status: number): Error {
  const err = new Error(`request failed: ${status}`);
  (err as any).status = status;
  return err;
}

/** The Switch component does not forward `id` to the underlying checkbox,
 *  so tests find the checkbox by role instead. */
function getCookieCheckbox(): HTMLInputElement {
  return screen.getByRole("checkbox") as HTMLInputElement;
}

describe("Settings screen — API wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading ────────────────────────────────────────────────────────────────
  it("shows a loading indicator while fetching settings", () => {
    // Never resolves — keeps the component in the loading state.
    mockedApiFetch.mockReturnValue(new Promise(() => {}));
    renderScreen();
    expect(screen.getByText("Loading settings…")).toBeInTheDocument();
  });

  // ── Success (GET) ───────────────────────────────────────────────────────────
  it("fetches settings from GET /settings and displays real data", async () => {
    mockedApiFetch.mockResolvedValue(makeSettings());
    renderScreen();

    // The answer model select should reflect the API value.
    await waitFor(() => {
      const select = document.getElementById("answer-model") as HTMLSelectElement;
      expect(select.value).toBe("gemini-2.0-flash");
    });

    const embeddingSelect = document.getElementById("embedding-model") as HTMLSelectElement;
    expect(embeddingSelect.value).toBe("text-embedding-004");

    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    expect(thresholdInput.value).toBe("0.62");

    // Secure cookie flag — the Switch renders a hidden checkbox.
    const cookieCheckbox = getCookieCheckbox();
    expect(cookieCheckbox.checked).toBe(true);
  });

  // ── No hardcoded initialSettings ────────────────────────────────────────────
  it("does not use a hardcoded initialSettings object — settings come from the API", async () => {
    mockedApiFetch.mockResolvedValue(
      makeSettings({
        gemini_answer_model: "gemini-1.5-pro",
        cosine_threshold: 0.75,
        cookie_secure_flag: false,
      }),
    );
    renderScreen();

    await waitFor(() => {
      const select = document.getElementById("answer-model") as HTMLSelectElement;
      expect(select.value).toBe("gemini-1.5-pro");
    });

    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    expect(thresholdInput.value).toBe("0.75");

    const cookieCheckbox = getCookieCheckbox();
    expect(cookieCheckbox.checked).toBe(false);
  });

  // ── Calls apiFetch for GET /settings on mount ───────────────────────────────
  it("calls apiFetch for GET /settings on initial render", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith("/settings");
    });
  });

  // ── Network error ───────────────────────────────────────────────────────────
  it("shows a user-visible error message on network failure with a retry button", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("network error"));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Failed to load settings")).toBeInTheDocument();
    });
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("re-fetches settings when the retry button is clicked", async () => {
    mockedApiFetch
      .mockRejectedValueOnce(new Error("network error"))
      .mockResolvedValueOnce(makeSettings({ gemini_answer_model: "gemini-1.5-pro" }));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      const select = document.getElementById("answer-model") as HTMLSelectElement;
      expect(select.value).toBe("gemini-1.5-pro");
    });
  });

  // ── 403 Forbidden ───────────────────────────────────────────────────────────
  it("shows the admin-only restricted view on 403 Forbidden", async () => {
    mockedApiFetch.mockRejectedValueOnce(statusError(403));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Settings are admin-only")).toBeInTheDocument();
    });
    // The Save Settings button must not be shown when forbidden.
    expect(screen.queryByText("Save Settings")).not.toBeInTheDocument();
  });

  // ── Dirty / clean tracking ─────────────────────────────────────────────────
  it("disables the Save Settings button when no changes are pending", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      const saveBtn = screen.getByText("Save Settings");
      expect(saveBtn).toBeDisabled();
    });
  });

  it("enables the Save Settings button when a field is changed", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    // Change the threshold.
    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    fireEvent.change(thresholdInput, { target: { value: "0.75" } });

    await waitFor(() => {
      const saveBtn = screen.getByText("Save Settings");
      expect(saveBtn).not.toBeDisabled();
    });
  });

  it("shows 'Unsaved changes' indicator when a field is modified", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    fireEvent.change(thresholdInput, { target: { value: "0.75" } });

    await waitFor(() => {
      expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    });
  });

  it("re-disables the Save button when changes are discarded", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    fireEvent.change(thresholdInput, { target: { value: "0.75" } });

    await waitFor(() => {
      expect(screen.getByText("Discard changes")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Discard changes"));

    await waitFor(() => {
      const saveBtn = screen.getByText("Save Settings");
      expect(saveBtn).toBeDisabled();
    });
  });

  // ── Save (PATCH) — success ────────────────────────────────────────────────
  it("submits changes via PATCH /settings and shows a success indicator", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    // Change the answer model.
    const answerSelect = document.getElementById("answer-model") as HTMLSelectElement;
    fireEvent.change(answerSelect, { target: { value: "gemini-1.5-pro" } });

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).not.toBeDisabled();
    });

    // Mock the PATCH response.
    mockedApiFetch.mockResolvedValueOnce(makeSettings({ gemini_answer_model: "gemini-1.5-pro" }));

    fireEvent.click(screen.getByText("Save Settings"));

    // Verify PATCH was called with the right path, method, and JSON body.
    await waitFor(() => {
      const patchCall = mockedApiFetch.mock.calls.find(
        (call) => (call[1] as any)?.method === "PATCH",
      );
      expect(patchCall).toBeTruthy();
      expect(patchCall![0]).toBe("/settings");
      const body = JSON.parse((patchCall![1] as any).body);
      expect(body).toEqual({
        gemini_answer_model: "gemini-1.5-pro",
        gemini_embedding_model: "text-embedding-004",
        cosine_threshold: 0.62,
        cookie_secure_flag: true,
      });
    });

    // Success indicator should appear.
    await waitFor(() => {
      expect(screen.getByText("Changes saved")).toBeInTheDocument();
    });

    // The updated value should be reflected on screen.
    expect((document.getElementById("answer-model") as HTMLSelectElement).value).toBe(
      "gemini-1.5-pro",
    );

    // Save button should be disabled again after successful save.
    expect(screen.getByText("Save Settings")).toBeDisabled();
  });

  // ── Save (PATCH) — network error ──────────────────────────────────────────
  it("shows a user-visible error message when PATCH fails with a network error", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    const answerSelect = document.getElementById("answer-model") as HTMLSelectElement;
    fireEvent.change(answerSelect, { target: { value: "gemini-1.5-pro" } });

    mockedApiFetch.mockRejectedValueOnce(new Error("network error"));

    fireEvent.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to save settings. Please check your connection and try again."),
      ).toBeInTheDocument();
    });
  });

  // ── Save (PATCH) — 403 forbidden ───────────────────────────────────────────
  it("shows the admin-only restricted view on 403 during PATCH", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    const answerSelect = document.getElementById("answer-model") as HTMLSelectElement;
    fireEvent.change(answerSelect, { target: { value: "gemini-1.5-pro" } });

    mockedApiFetch.mockRejectedValueOnce(statusError(403));

    fireEvent.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      expect(screen.getByText("Settings are admin-only")).toBeInTheDocument();
    });
  });

  // ── Threshold preset buttons ────────────────────────────────────────────────
  it("preset buttons update the threshold and enable save", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    // Click the "Strict (0.75)" preset.
    fireEvent.click(screen.getByText("Strict (0.75)"));

    const thresholdInput = document.getElementById("cosine-threshold") as HTMLInputElement;
    expect(thresholdInput.value).toBe("0.75");

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).not.toBeDisabled();
    });
  });

  // ── Cookie secure toggle ───────────────────────────────────────────────────
  it("toggling the secure cookie flag enables save and submits the new value", async () => {
    mockedApiFetch.mockResolvedValueOnce(makeSettings());
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).toBeInTheDocument();
    });

    const cookieCheckbox = getCookieCheckbox();
    expect(cookieCheckbox.checked).toBe(true);

    fireEvent.click(cookieCheckbox);

    await waitFor(() => {
      expect(screen.getByText("Save Settings")).not.toBeDisabled();
    });

    mockedApiFetch.mockResolvedValueOnce(makeSettings({ cookie_secure_flag: false }));

    fireEvent.click(screen.getByText("Save Settings"));

    await waitFor(() => {
      const patchCall = mockedApiFetch.mock.calls.find(
        (call) => (call[1] as any)?.method === "PATCH",
      );
      const body = JSON.parse((patchCall![1] as any).body);
      expect(body.cookie_secure_flag).toBe(false);
    });
  });
});
