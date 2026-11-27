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
