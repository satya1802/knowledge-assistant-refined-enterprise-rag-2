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
import Users from "@/screens/Users";

const mockedApiFetch = vi.mocked(apiFetch);

/* eslint-disable @typescript-eslint/no-explicit-any */

function renderScreen() {
  return render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  );
}

function statusError(status: number): Error {
  const err = new Error(`request failed: ${status}`);
  (err as any).status = status;
  return err;
}

describe("Users screen — API wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading ────────────────────────────────────────────────────────────────
  it("shows a loading indicator while fetching users", () => {
    // Never resolves — keeps the component in the loading state.
    mockedApiFetch.mockReturnValue(new Promise(() => {}));
    renderScreen();
    expect(screen.getByText("Loading users…")).toBeInTheDocument();
  });

  // ── Success (GET) ───────────────────────────────────────────────────────────
  it("fetches users from GET /users and displays real data", async () => {
    mockedApiFetch.mockResolvedValue([
      { id: 1, email: "admin@company.com", role: "Administrator" },
      { id: 2, email: "jane@company.com", role: "Regular User" },
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });
    expect(screen.getByText("jane@company.com")).toBeInTheDocument();
    // "Administrator" and "Regular User" appear in both the role badge and
    // the filter dropdown options, so use getAllByText.
    expect(screen.getAllByText("Administrator").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Regular User").length).toBeGreaterThan(0);
  });

  // ── Empty state ─────────────────────────────────────────────────────────────
  it("shows an empty state when the API returns no users", async () => {
    mockedApiFetch.mockResolvedValue([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No users yet")).toBeInTheDocument();
    });
  });

  // ── No sample data ──────────────────────────────────────────────────────────
  it("does not render any hardcoded sample users", async () => {
    mockedApiFetch.mockResolvedValue([{ id: 1, email: "real@company.com", role: "Administrator" }]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("real@company.com")).toBeInTheDocument();
    });
    // The old SAMPLE_USERS emails must never appear.
    expect(screen.queryByText("satya.ganaraju@quorq.ai")).not.toBeInTheDocument();
    expect(screen.queryByText("ananya.reddy@quorq.ai")).not.toBeInTheDocument();
    expect(screen.queryByText("priya.sharma@quorq.ai")).not.toBeInTheDocument();
    expect(screen.queryByText("meera.iyer@quorq.ai")).not.toBeInTheDocument();
  });

  // ── Network error ───────────────────────────────────────────────────────────
  it("shows a user-visible error message on network failure with a retry button", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("network error"));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Failed to load users")).toBeInTheDocument();
    });
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("re-fetches users when the retry button is clicked", async () => {
    mockedApiFetch
      .mockRejectedValueOnce(new Error("network error"))
      .mockResolvedValueOnce([{ id: 1, email: "admin@company.com", role: "Administrator" }]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });
  });

  // ── 403 Forbidden ───────────────────────────────────────────────────────────
  it("shows an admin-only restricted view on 403 Forbidden", async () => {
    mockedApiFetch.mockRejectedValueOnce(statusError(403));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Administrator access required")).toBeInTheDocument();
    });
    // The New User button must not be shown when forbidden.
    expect(screen.queryByText("New User")).not.toBeInTheDocument();
  });

  // ── Create user (POST) — success ───────────────────────────────────────────
  it("creates a new user via POST /users, adds it to the table, and shows success", async () => {
    const existing = [{ id: 1, email: "admin@company.com", role: "Administrator" }];
    mockedApiFetch.mockResolvedValueOnce(existing);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });

    // Open the create form.
    fireEvent.click(screen.getByText("New User"));

    const emailInput = document.getElementById("new-email") as HTMLInputElement;
    const passwordInput = document.getElementById("new-password") as HTMLInputElement;
    expect(emailInput).toBeTruthy();
    expect(passwordInput).toBeTruthy();

    fireEvent.change(emailInput, { target: { value: "newuser@company.com" } });
    fireEvent.change(passwordInput, { target: { value: "securepass123" } });

    // Mock the POST response.
    mockedApiFetch.mockResolvedValueOnce({
      id: 2,
      email: "newuser@company.com",
      role: "Regular User",
    });

    fireEvent.click(screen.getByText("Create account"));

    await waitFor(() => {
      expect(screen.getByText("newuser@company.com")).toBeInTheDocument();
    });
    // Success banner should be visible.
    await waitFor(() => {
      expect(screen.getByText(/Account created for newuser@company.com/)).toBeInTheDocument();
    });

    // Verify POST was called with the right JSON body.
    const postCall = mockedApiFetch.mock.calls.find(
      (call) => (call[1] as any)?.method === "POST",
    );
    expect(postCall).toBeTruthy();
    expect(postCall![0]).toBe("/users");
    const body = JSON.parse((postCall![1] as any).body);
    expect(body).toEqual({
      email: "newuser@company.com",
      password: "securepass123",
      role: "Regular User",
    });
  });

  // ── Create user (POST) — 409 conflict ──────────────────────────────────────
  it("shows an inline error on the form when the server returns 409 conflict", async () => {
    mockedApiFetch.mockResolvedValueOnce([
      { id: 1, email: "admin@company.com", role: "Administrator" },
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("New User"));

    const emailInput = document.getElementById("new-email") as HTMLInputElement;
    const passwordInput = document.getElementById("new-password") as HTMLInputElement;

    // Use an email NOT in the current list so client-side validation passes;
    // the server returns 409 to simulate a race condition.
    fireEvent.change(emailInput, { target: { value: "race@company.com" } });
    fireEvent.change(passwordInput, { target: { value: "securepass123" } });

    mockedApiFetch.mockRejectedValueOnce(statusError(409));

    fireEvent.click(screen.getByText("Create account"));

    await waitFor(() => {
      expect(screen.getByText("A user with this email already exists")).toBeInTheDocument();
    });
  });

  // ── Create user (POST) — generic error ─────────────────────────────────────
  it("shows a form-level error message on a generic POST failure", async () => {
    mockedApiFetch.mockResolvedValueOnce([
      { id: 1, email: "admin@company.com", role: "Administrator" },
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("New User"));

    const emailInput = document.getElementById("new-email") as HTMLInputElement;
    const passwordInput = document.getElementById("new-password") as HTMLInputElement;

    fireEvent.change(emailInput, { target: { value: "newuser@company.com" } });
    fireEvent.change(passwordInput, { target: { value: "securepass123" } });

    mockedApiFetch.mockRejectedValueOnce(new Error("server error"));

    fireEvent.click(screen.getByText("Create account"));

    await waitFor(() => {
      expect(screen.getByText("Failed to create user. Please try again.")).toBeInTheDocument();
    });
  });

  // ── Role select sends backend values ────────────────────────────────────────
  it("sends 'Administrator' or 'Regular User' as the role in the POST body", async () => {
    mockedApiFetch.mockResolvedValueOnce([
      { id: 1, email: "admin@company.com", role: "Administrator" },
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("admin@company.com")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("New User"));

    const emailInput = document.getElementById("new-email") as HTMLInputElement;
    const passwordInput = document.getElementById("new-password") as HTMLInputElement;
    const roleSelect = document.getElementById("new-role") as HTMLSelectElement;

    fireEvent.change(emailInput, { target: { value: "newadmin@company.com" } });
    fireEvent.change(passwordInput, { target: { value: "securepass123" } });
    fireEvent.change(roleSelect, { target: { value: "Administrator" } });

    mockedApiFetch.mockResolvedValueOnce({
      id: 2,
      email: "newadmin@company.com",
      role: "Administrator",
    });

    fireEvent.click(screen.getByText("Create account"));

    await waitFor(() => {
      expect(screen.getByText("newadmin@company.com")).toBeInTheDocument();
    });

    const postCall = mockedApiFetch.mock.calls.find(
      (call) => (call[1] as any)?.method === "POST",
    );
    const body = JSON.parse((postCall![1] as any).body);
    expect(body.role).toBe("Administrator");
  });

  // ── Credentials: apiFetch is called (credentials handled in api.ts) ─────────
  it("calls apiFetch for GET /users on initial render", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith("/users");
    });
  });
});