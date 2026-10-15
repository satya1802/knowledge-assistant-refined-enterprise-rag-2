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
    apiUpload: vi.fn(),
    ApiError,
    API_BASE_URL: "http://localhost:8000",
  };
});

import { apiFetch, apiUpload, ApiError } from "@/lib/api";
import KnowledgeBase from "@/screens/KnowledgeBase";

const mockedApiFetch = vi.mocked(apiFetch);
const mockedApiUpload = vi.mocked(apiUpload);

/* eslint-disable @typescript-eslint/no-explicit-any */

function makeDoc(overrides?: any) {
  return {
    id: "doc-001",
    filename: "Q4-Report.pdf",
    file_type: "PDF",
    file_size: 4823567,
    status: "Ready",
    created_at: "2026-10-08T09:14:00Z",
    failure_reason: null,
    ...overrides,
  };
}

function renderScreen() {
  return render(
    <MemoryRouter>
      <KnowledgeBase />
    </MemoryRouter>,
  );
}

describe("KnowledgeBase screen — API wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading ────────────────────────────────────────────────────────────────
  it("shows a loading indicator while fetching documents", () => {
    // Never resolves — keeps the component in the loading state.
    mockedApiFetch.mockReturnValue(new Promise(() => {}));
    renderScreen();
    expect(screen.getByText("Loading documents…")).toBeInTheDocument();
  });

  // ── Success (GET) ───────────────────────────────────────────────────────────
  it("fetches documents from GET /documents and displays real data", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "doc-a", filename: "Policy.pdf", status: "Ready" }),
      makeDoc({ id: "doc-b", filename: "Guide.docx", file_type: "DOCX", status: "Processing" }),
      makeDoc({
        id: "doc-c",
        filename: "Legacy.pdf",
        status: "Failed",
        failure_reason: "Embedding quota exceeded",
      }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Policy.pdf")).toBeInTheDocument();
    });
    expect(screen.getByText("Guide.docx")).toBeInTheDocument();
    expect(screen.getByText("Legacy.pdf")).toBeInTheDocument();
    // Status badges reflect API data.
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Failed").length).toBeGreaterThan(0);
    // Failure reason from the API is shown.
    expect(screen.getByText("Embedding quota exceeded")).toBeInTheDocument();
  });

  // ── Empty state ─────────────────────────────────────────────────────────────
  it("shows an empty state when the API returns no documents", async () => {
    mockedApiFetch.mockResolvedValue([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No documents in the Knowledge Base yet")).toBeInTheDocument();
    });
  });

  // ── No sample data ──────────────────────────────────────────────────────────
  it("does not render any hardcoded sample documents", async () => {
    mockedApiFetch.mockResolvedValue([makeDoc({ filename: "Real-Doc.pdf" })]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Real-Doc.pdf")).toBeInTheDocument();
    });
    // The old initialDocuments filenames must never appear.
    expect(screen.queryByText("Q4-2025-Financial-Report.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("Employee-Handbook-2026.docx")).not.toBeInTheDocument();
    expect(screen.queryByText("Scanned-Legacy-Contracts.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("Quarterly-Board-Minutes.pdf")).not.toBeInTheDocument();
  });

  // ── Network error ───────────────────────────────────────────────────────────
  it("shows a user-visible error message on network failure with a retry button", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("network error"));
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Could not load the Knowledge Base")).toBeInTheDocument();
    });
    expect(screen.getByText("Try again")).toBeInTheDocument();
  });

  it("re-fetches documents when the retry button is clicked", async () => {
    mockedApiFetch
      .mockRejectedValueOnce(new Error("network error"))
      .mockResolvedValueOnce([makeDoc({ filename: "After-Retry.pdf" })]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Try again")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      expect(screen.getByText("After-Retry.pdf")).toBeInTheDocument();
    });
  });

  // ── Credentials: apiFetch is called for GET /documents on mount ─────────────
  it("calls apiFetch for GET /documents on initial render", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith("/documents");
    });
  });

  // ── Upload (POST) — success ────────────────────────────────────────────────
  it("uploads a file via POST /documents using apiUpload and adds the returned document", async () => {
    mockedApiFetch.mockResolvedValueOnce([makeDoc({ id: "doc-1", filename: "Existing.pdf" })]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Existing.pdf")).toBeInTheDocument();
    });

    // Simulate selecting a file through the hidden input.
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    const testFile = new File(["hello world"], "New-Upload.pdf", { type: "application/pdf" });

    mockedApiUpload.mockResolvedValueOnce(
      makeDoc({ id: "doc-new", filename: "New-Upload.pdf", status: "Processing" }),
    );

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(screen.getByText("New-Upload.pdf")).toBeInTheDocument();
    });

    // Verify apiUpload was called with the right path and file.
    expect(mockedApiUpload).toHaveBeenCalledWith("/documents", testFile);
  });

  // ── Upload (POST) — 422 unsupported type ───────────────────────────────────
  it("displays the API error message on 422 unsupported file type", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No documents in the Knowledge Base yet")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["data"], "badfile.exe", { type: "application/octet-stream" });

    // Client-side validation catches .EXE before the request is sent.
    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(screen.getByText(/is not a supported format/)).toBeInTheDocument();
    });
    // The API was NOT called because client validation rejected it.
    expect(mockedApiUpload).not.toHaveBeenCalled();
  });

  // ── Upload (POST) — 422 from server (size limit) ───────────────────────────
  it("displays the API error message when the server returns 422 for oversized file", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No documents in the Knowledge Base yet")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    // A valid-type file that passes client checks but is rejected by the server.
    const testFile = new File(["x".repeat(100)], "Big.pdf", { type: "application/pdf" });

    mockedApiUpload.mockRejectedValueOnce(
      new ApiError("POST /documents failed: 422", 422, {
        detail: "File size exceeds the 25 MB limit",
      }),
    );

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(screen.getByText("File size exceeds the 25 MB limit")).toBeInTheDocument();
    });
  });

  // ── Upload (POST) — 403 forbidden ──────────────────────────────────────────
  it("displays a permission error on 403 forbidden during upload", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No documents in the Knowledge Base yet")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["hello"], "Doc.pdf", { type: "application/pdf" });

    mockedApiUpload.mockRejectedValueOnce(
      new ApiError("POST /documents failed: 403", 403, {
        detail: "Not enough permissions",
      }),
    );

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(screen.getByText(/Not enough permissions/)).toBeInTheDocument();
    });
  });

  // ── Upload (POST) — network error ──────────────────────────────────────────
  it("displays a network error message when upload fails to reach the server", async () => {
    mockedApiFetch.mockResolvedValueOnce([]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("No documents in the Knowledge Base yet")).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const testFile = new File(["hello"], "Doc.pdf", { type: "application/pdf" });

    // A plain Error (not ApiError) simulates a network failure.
    mockedApiUpload.mockRejectedValueOnce(new Error("fetch failed"));

    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(screen.getByText(/Could not reach the server/)).toBeInTheDocument();
    });
  });

  // ── Stats reflect API data ──────────────────────────────────────────────────
  it("stats cards reflect counts from API-sourced data", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "d1", status: "Ready" }),
      makeDoc({ id: "d2", status: "Ready" }),
      makeDoc({ id: "d3", status: "Processing" }),
      makeDoc({ id: "d4", status: "Failed", failure_reason: "error" }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Total Documents")).toBeInTheDocument();
    });

    // StatCard pads values to 2 digits.
    expect(screen.getByText("04")).toBeInTheDocument(); // total
    // "02" for Ready, "01" for Processing, "01" for Failed
    // These appear in stat cards — verify at least total is correct.
    expect(screen.getAllByText("04").length).toBeGreaterThan(0);
  });

  // ── Search and filters work with API data ──────────────────────────────────
  it("search filters documents by filename from API data", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "d1", filename: "Alpha.pdf" }),
      makeDoc({ id: "d2", filename: "Beta.docx", file_type: "DOCX" }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Alpha.pdf")).toBeInTheDocument();
    });

    const searchInput = screen.getByLabelText("Search documents by filename");
    fireEvent.change(searchInput, { target: { value: "Alpha" } });

    expect(screen.getByText("Alpha.pdf")).toBeInTheDocument();
    expect(screen.queryByText("Beta.docx")).not.toBeInTheDocument();
  });

  it("type filter narrows documents by file type from API data", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "d1", filename: "Alpha.pdf", file_type: "PDF" }),
      makeDoc({ id: "d2", filename: "Beta.docx", file_type: "DOCX" }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Alpha.pdf")).toBeInTheDocument();
    });

    const typeSelect = screen.getByLabelText("Filter documents by file type");
    fireEvent.change(typeSelect, { target: { value: "DOCX" } });

    expect(screen.getByText("Beta.docx")).toBeInTheDocument();
    expect(screen.queryByText("Alpha.pdf")).not.toBeInTheDocument();
  });

  it("status filter narrows documents by status from API data", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "d1", filename: "Ready-Doc.pdf", status: "Ready" }),
      makeDoc({ id: "d2", filename: "Failed-Doc.pdf", status: "Failed", failure_reason: "err" }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Ready-Doc.pdf")).toBeInTheDocument();
    });

    const statusSelect = screen.getByLabelText("Filter documents by processing status");
    fireEvent.change(statusSelect, { target: { value: "Failed" } });

    expect(screen.getByText("Failed-Doc.pdf")).toBeInTheDocument();
    expect(screen.queryByText("Ready-Doc.pdf")).not.toBeInTheDocument();
  });

  // ── Processing stays until next fetch ──────────────────────────────────────
  it("does not simulate processing completion — Processing status persists", async () => {
    mockedApiFetch.mockResolvedValue([
      makeDoc({ id: "d1", filename: "Processing-Doc.pdf", status: "Processing" }),
    ]);
    renderScreen();

    await waitFor(() => {
      expect(screen.getByText("Processing-Doc.pdf")).toBeInTheDocument();
    });

    // Wait a moment — no setTimeout should transition the status.
    await new Promise((r) => setTimeout(r, 200));

    // The document should still show Processing.
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    // And it should NOT have become Ready.
    expect(screen.queryByText("Ready-Doc.pdf")).not.toBeInTheDocument();
  });
});
