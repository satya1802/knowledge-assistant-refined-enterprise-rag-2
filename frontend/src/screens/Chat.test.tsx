import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

import Chat from "@/screens/Chat";

function renderScreen() {
  return render(<Chat />);
}

beforeEach(() => {
  // jsdom does not implement scrollIntoView; the screen calls it to keep the
  // latest message in view whenever the message list changes.
  Element.prototype.scrollIntoView = vi.fn();
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
