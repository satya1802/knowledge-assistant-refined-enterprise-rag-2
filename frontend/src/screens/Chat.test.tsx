import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// Mock the api module so tests don't hit the network (same pattern as the
// other screens' tests).
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

import { apiFetch, ApiError } from "@/lib/api";
import Chat from "@/screens/Chat";

const mockedApiFetch = vi.mocked(apiFetch);

// The exact wording the backend returns for a Gemini API error or quota
// failure (app/errors.py — CHAT_GEMINI_UNAVAILABLE.detail), and the wording
// Chat.tsx falls back to when a failure carries no such detail.
const GEMINI_UNAVAILABLE_MESSAGE =
  "The AI service is temporarily unavailable or has reached its quota. " +
  "Your question and chat history have been saved -- please try again shortly.";

const CHAT_PLACEHOLDER = "Ask a question about your Knowledge Base documents…";

function renderScreen() {
  return render(<Chat />);
}

function typeAndSend(question: string) {
  const textarea = screen.getByPlaceholderText(CHAT_PLACEHOLDER);
  fireEvent.change(textarea, { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  return textarea;
}

beforeEach(() => {
  // jsdom does not implement scrollIntoView; the screen calls it to keep the
  // latest message in view whenever the message list changes.
  Element.prototype.scrollIntoView = vi.fn();
  mockedApiFetch.mockReset();
});

describe("Chat screen — citation display", () => {
  // The screen opens on the first seeded conversation ("Q3 Information
  // Security Review"), whose second assistant answer (msg-002) carries two
  // citations. This is the fixture every test below exercises.

  it("[AC-066] shows each citation alongside the grounded answer it supports", () => {
    renderScreen();

    // The grounded answer itself is on screen.
    expect(
      screen.getByText(/Service accounts must use passwords of at least 20 characters/),
    ).toBeInTheDocument();

    // Its citations render right alongside it, inside the same message.
    const message = screen.getByTestId("chat-message-msg-002");
    const citations = within(message).getAllByTestId("citation");
    expect(citations).toHaveLength(2);
  });

  it("[AC-066] clearly references the source document, page/section, and chunk for each citation", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-002");
    const [firstCitation, secondCitation] = within(message).getAllByTestId("citation");

    // Document (filename), page/section, and chunk are all present, in that
    // order, for every citation — not just a bare filename.
    expect(firstCitation).toHaveTextContent("InfoSec_Policy_v3.2.pdf");
    expect(firstCitation).toHaveTextContent("Page 14, §4.3");
    expect(firstCitation).toHaveTextContent("Chunk chunk-047");

    expect(secondCitation).toHaveTextContent("InfoSec_Policy_v3.2.pdf");
    expect(secondCitation).toHaveTextContent("Page 15, §4.5");
    expect(secondCitation).toHaveTextContent("Chunk chunk-049");
  });

  it("[AC-066] shows a single citation clearly for an answer grounded in one chunk", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-004");
    const citations = within(message).getAllByTestId("citation");
    expect(citations).toHaveLength(1);
    expect(citations[0]).toHaveTextContent("InfoSec_Policy_v3.2.pdf");
    expect(citations[0]).toHaveTextContent("Page 18, §5.2");
    expect(citations[0]).toHaveTextContent("Chunk chunk-058");
  });

  it("[AC-066] shows no citation for a fallback answer with no grounded source", () => {
    renderScreen();

    // msg-006 is a fallback answer (no relevant chunks found) and carries no
    // citations — none should be fabricated or shown.
    const message = screen.getByTestId("chat-message-msg-006");
    expect(within(message).queryAllByTestId("citation")).toHaveLength(0);
  });
});

describe("Chat screen — 'Not from your documents' fallback badge", () => {
  // msg-006 (in the seeded "Q3 Information Security Review" conversation,
  // selected by default) is a fallback answer: no relevant chunks were found,
  // so Gemini answered from general knowledge.

  it("[AC-070] shows the 'Not from your documents' badge alongside the fallback answer", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-006");
    expect(within(message).getByText("Not from your documents")).toBeInTheDocument();
  });

  it("[AC-070] renders the badge as a visually distinct, clearly visible element rather than plain text", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-006");
    const badgeText = within(message).getByText("Not from your documents");
    const badge = badgeText.closest("div");

    // Visible to the user...
    expect(badge).toBeVisible();
    // ...and set apart from the surrounding answer text by its own bordered,
    // colored container, not just inline wording within the answer.
    expect(badge?.style.border).toBeTruthy();
    expect(badge?.style.backgroundColor).toBeTruthy();
    expect(badge).not.toBe(message);
  });

  it("[AC-070] does not show the fallback badge alongside a grounded answer", () => {
    renderScreen();

    // msg-002 is a grounded answer backed by real citations — it must not
    // carry the fallback badge.
    const message = screen.getByTestId("chat-message-msg-002");
    expect(within(message).queryByText("Not from your documents")).not.toBeInTheDocument();
  });

  it("[AC-071] shows no citations alongside the fallback answer carrying the badge", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-006");
    expect(within(message).getByText("Not from your documents")).toBeInTheDocument();
    expect(within(message).queryAllByTestId("citation")).toHaveLength(0);
  });

  it("[AC-071] still shows real citations for a grounded answer, unaffected by fallback handling", () => {
    renderScreen();

    const message = screen.getByTestId("chat-message-msg-004");
    expect(within(message).getAllByTestId("citation")).toHaveLength(1);
    expect(within(message).queryByText("Not from your documents")).not.toBeInTheDocument();
  });
});

describe("Chat screen — create conversation (AC-074)", () => {
  // Clicking "New" must create the conversation on the server (POST
  // /conversations) rather than only adding it to local state, so the
  // thread is actually associated with the authenticated user's ID.

  it("[AC-074] calls POST /conversations when 'New' is clicked", async () => {
    mockedApiFetch.mockResolvedValueOnce({
      id: "11111111-1111-1111-1111-111111111111",
      title: null,
      created_at: "2026-11-27T12:00:00Z",
    });

    renderScreen();
    fireEvent.click(screen.getByRole("button", { name: "New" }));

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "/conversations",
      expect.objectContaining({ method: "POST" }),
    );

    // Let the resolved promise's state updates settle before the test ends.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "New" })).not.toBeDisabled();
    });
  });

  it("[AC-074] adds the conversation detail the server returns and selects it", async () => {
    const newId = crypto.randomUUID();
    mockedApiFetch.mockResolvedValueOnce({
      id: newId,
      title: null,
      created_at: "2026-11-27T12:00:00Z",
    });

    renderScreen();
    fireEvent.click(screen.getByRole("button", { name: "New" }));

    const list = screen.getByLabelText("Conversation list");
    const newItem = await within(list).findByRole("button", {
      name: /Open conversation: New Conversation, 0 messages/,
    });

    // The newly created conversation (identified by the server-returned id
    // via its aria-current state) becomes the selected conversation.
    expect(newItem).toHaveAttribute("aria-current", "true");
  });

  it("[AC-074] shows a clear error and leaves the composer usable when creation fails", async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError("POST /conversations failed: 500", 500, {}));

    renderScreen();
    fireEvent.click(screen.getByRole("button", { name: "New" }));

    expect(
      await screen.findByText("Failed to create conversation. Please try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).not.toBeDisabled();
  });
});

describe("Chat screen — Gemini API error handling (AC-072)", () => {
  // POST /chat is the only endpoint this story adds error handling around.
  // Every test below sends through the default conversation ("Q3 Information
  // Security Review") unless a different one is selected explicitly.

  it("[AC-072] shows a clear error message when the backend reports a Gemini API or quota failure", async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError("POST /chat failed: 503", 503, { detail: GEMINI_UNAVAILABLE_MESSAGE }),
    );

    renderScreen();
    typeAndSend("What is our disaster recovery RTO?");

    expect(await screen.findByText(GEMINI_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
  });

  it("[AC-072] falls back to a clear generic message when the failure carries no server detail", async () => {
    mockedApiFetch.mockRejectedValueOnce(new Error("network error"));

    renderScreen();
    typeAndSend("Will this still work?");

    expect(await screen.findByText(GEMINI_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
  });

  it("[AC-072] does not blank the page or drop prior messages when a Gemini error is shown", async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError("POST /chat failed: 503", 503, {}));

    renderScreen();
    typeAndSend("What is our disaster recovery RTO?");

    await screen.findByText(GEMINI_UNAVAILABLE_MESSAGE);

    // The screen (and the whole prior conversation) is still rendered, not
    // blanked, and the question the user just asked is preserved too.
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(
      screen.getByText(/Service accounts must use passwords of at least 20 characters/),
    ).toBeInTheDocument();
    expect(screen.getByText("What is our disaster recovery RTO?")).toBeInTheDocument();
  });

  it("[AC-072] re-enables the composer after a Gemini error instead of hanging on 'Sending…'", async () => {
    mockedApiFetch.mockRejectedValueOnce(new ApiError("POST /chat failed: 503", 503, {}));

    renderScreen();
    const textarea = typeAndSend("What is our disaster recovery RTO?") as HTMLTextAreaElement;

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
    });
    expect(textarea).not.toBeDisabled();
  });

  it("[AC-072] a retry after a Gemini error succeeds and replaces the error message in place", async () => {
    mockedApiFetch.mockResolvedValueOnce({
      answer: "Custom rate limits are configured per client in the gateway admin panel.",
      is_fallback: false,
      citations: [
        {
          document_id: "doc-099",
          filename: "API_Gateway_Config.pdf",
          page_section: "Page 9, §3.4",
          chunk_id: "chunk-099",
        },
      ],
    });

    renderScreen();

    // conv-003 ("API Gateway Rate Limiting") already ends on a persisted
    // Gemini error message (msg-014) with a "Retry question" affordance.
    fireEvent.click(
      screen.getByRole("button", { name: /Open conversation: API Gateway Rate Limiting/ }),
    );
    expect(screen.getByText(/The Gemini API returned an error/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry question" }));

    const messageList = screen.getByLabelText("Chat messages");
    expect(
      await within(messageList).findByText(
        "Custom rate limits are configured per client in the gateway admin panel.",
      ),
    ).toBeInTheDocument();
    expect(
      within(messageList).queryByText(/The Gemini API returned an error/),
    ).not.toBeInTheDocument();
  });
});
