// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Select, Switch } = UI;
const { Settings, AlertCircle, CheckCircle } = Icons;

const initialSettings = {
  id: 1,
  gemini_answer_model: "gemini-2.0-flash",
  gemini_embedding_model: "text-embedding-004",
  cosine_threshold: 0.62,
  cookie_secure_flag: true,
  updated_at: "2026-10-14T09:22:00Z",
  updated_by: "satya.ganaraju@quorq.ai"
};

const modelOptions = [
  { value: "gemini-2.0-flash", label: "gemini-2.0-flash — fast, low cost" },
  { value: "gemini-2.0-flash-lite", label: "gemini-2.0-flash-lite — lightest, cheapest" },
  { value: "gemini-1.5-pro", label: "gemini-1.5-pro — highest quality" },
  { value: "gemini-1.5-flash", label: "gemini-1.5-flash — balanced" },
];

const embeddingOptions = [
  { value: "text-embedding-004", label: "text-embedding-004 — 768-dim (recommended)" },
  { value: "text-embedding-003", label: "text-embedding-003 — 768-dim (legacy)" },
];

const thresholdPresets = [
  { label: "Strict (0.75)", value: 0.75, hint: "Fewer but more precise matches" },
  { label: "Default (0.62)", value: 0.62, hint: "Balanced retrieval" },
  { label: "Permissive (0.50)", value: 0.50, hint: "More matches, lower relevance" },
];

export default function Screen() {
  const navigate = useNavigate();
  const [settings, setSettings] = React.useState(initialSettings);
  const [draft, setDraft] = React.useState(initialSettings);
  const [dirty, setDirty] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [savedAt, setSavedAt] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [isAdmin, setIsAdmin] = React.useState(true);

  function updateDraft(field, value) {
    setDraft(prev => {
      const next = { ...prev, [field]: value };
      const changed = Object.keys(next).some(
        k => next[k] !== settings[k] && k !== "updated_at" && k !== "updated_by" && k !== "id"
      );
      setDirty(changed);
      return next;
    });
    setError(null);
  }

  function handleSave(e) {
    e.preventDefault();
    if (draft.cosine_threshold < 0 || draft.cosine_threshold > 1) {
      setError("Cosine similarity threshold must be between 0.00 and 1.00.");
      return;
    }
    setSaving(true);
    setError(null);
    // Simulate async save
    setTimeout(() => {
      const now = new Date().toISOString();
      const updated = {
        ...draft,
        updated_at: now,
        updated_by: "satya.ganaraju@quorq.ai",
      };
      setSettings(updated);
      setDraft(updated);
      setDirty(false);
      setSaving(false);
      setSavedAt(now);
    }, 700);
  }

  function handleReset() {
    setDraft(settings);
    setDirty(false);
    setError(null);
  }

  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  const thresholdChanged = draft.cosine_threshold !== settings.cosine_threshold;
  const modelChanged = draft.gemini_answer_model !== settings.gemini_answer_model;
  const embeddingChanged = draft.gemini_embedding_model !== settings.gemini_embedding_model;
  const cookieChanged = draft.cookie_secure_flag !== settings.cookie_secure_flag;

  const accentStyle = { color: brand.primaryColor };
  const cardStyle = {
    borderRadius: brand.radius,
    backgroundColor: "#ffffff",
    border: "1px solid #e2e8f0",
  };
  const labelStyle = {
    fontFamily: brand.fontBody,
    fontSize: "0.8125rem",
    fontWeight: 600,
    color: "#334155",
    marginBottom: "0.25rem",
    display: "block",
  };
  const helpStyle = {
    fontFamily: brand.fontBody,
    fontSize: "0.75rem",
    color: brand.neutralColor,
    marginTop: "0.25rem",
    lineHeight: 1.5,
  };

  if (!isAdmin) {
    return (
      <div style={{ maxWidth: "640px", margin: "0 auto", paddingTop: "3rem" }}>
        <div style={cardStyle} className="p-8 text-center">
          <div className="flex items-center justify-center mb-4">
            <span
              className="inline-flex items-center justify-center"
              style={{
                width: "48px",
                height: "48px",
                borderRadius: brand.radius,
                backgroundColor: "#fef2f2",
              }}
            >
              <AlertCircle style={{ width: "24px", height: "24px", color: "#dc2626" }} aria-hidden="true" />
            </span>
          </div>
          <h1 className="text-lg font-semibold mb-2" style={{ fontFamily: brand.fontHeading, color: "#1e293b" }}>
            Settings are admin-only
          </h1>
          <p className="text-sm mb-6" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
            Only administrators can view and change application settings. If you need a model or threshold
            change, ask an administrator to update it from this page.
          </p>
          <Button onClick={() => navigate("chat")} style={{ fontFamily: brand.fontBody }}>
            Back to Chat
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ fontFamily: brand.fontBody, color: "#1e293b", maxWidth: "880px", margin: "0 auto" }}>
      {/* Heading */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold"
            style={{ fontFamily: brand.fontHeading, color: "#0f172a", letterSpacing: "-0.01em" }}
          >
            Settings
          </h1>
          <p className="text-sm mt-1" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
            Configure Gemini models, retrieval threshold, and session security for all users.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
          <Settings style={{ width: "14px", height: "14px" }} aria-hidden="true" />
          <span>Administrator</span>
        </div>
      </div>

      {/* Last updated bar */}
      <div
        className="flex items-center justify-between mb-4 px-3 py-2 rounded-md"
        style={{
          backgroundColor: "#f1f5f9",
          borderRadius: brand.radius,
          fontFamily: brand.fontBody,
        }}
      >
        <span className="text-xs" style={{ color: brand.neutralColor }}>
          Last saved {formatTime(settings.updated_at)} by {settings.updated_by}
        </span>
        {savedAt && !dirty && (
          <span
            className="flex items-center gap-1 text-xs font-medium"
            style={{ color: brand.accentColor }}
          >
            <CheckCircle style={{ width: "14px", height: "14px" }} aria-hidden="true" />
            Changes saved
          </span>
        )}
        {dirty && (
          <span className="flex items-center gap-1 text-xs font-medium" style={{ color: brand.neutralColor }}>
            <span
              className="inline-block"
              style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: brand.primaryColor }}
              aria-hidden="true"
            />
            Unsaved changes
          </span>
        )}
      </div>

      <form onSubmit={handleSave}>
        {/* Model configuration */}
        <div style={cardStyle} className="mb-4">
          <div className="px-5 py-4" style={{ borderBottom: "1px solid #e2e8f0" }}>
            <h2
              className="text-sm font-semibold"
              style={{ fontFamily: brand.fontHeading, color: "#0f172a" }}
            >
              Gemini Model Configuration
            </h2>
            <p className="text-xs mt-0.5" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
              Google Gemini is the sole AI provider for answer generation and embeddings.
            </p>
          </div>

          <div className="px-5 py-4 grid grid-cols-1 gap-5">
            {/* Answer model */}
            <div>
              <label htmlFor="answer-model" style={labelStyle}>
                Answer Generation Model
              </label>
              <Select
                id="answer-model"
                value={draft.gemini_answer_model}
                onChange={(e) => updateDraft("gemini_answer_model", e.target.value)}
                className="w-full"
                style={{ fontFamily: brand.fontBody, fontSize: "0.8125rem" }}
              >
                {modelOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <p style={helpStyle}>
                Used for generating answers in chat. Changing this affects new responses immediately.
              </p>
              {modelChanged && (
                <p className="text-xs mt-1 font-medium" style={{ color: brand.primaryColor, fontFamily: brand.fontBody }}>
                  Pending: {settings.gemini_answer_model} → {draft.gemini_answer_model}
                </p>
              )}
            </div>

            {/* Embedding model */}
            <div>
              <label htmlFor="embedding-model" style={labelStyle}>
                Embedding Model
              </label>
              <Select
                id="embedding-model"
                value={draft.gemini_embedding_model}
                onChange={(e) => updateDraft("gemini_embedding_model", e.target.value)}
                className="w-full"
                style={{ fontFamily: brand.fontBody, fontSize: "0.8125rem" }}
              >
                {embeddingOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <p style={helpStyle}>
                Generates 768-dimensional vectors for Knowledge Base chunks. Changing the embedding model
                requires re-indexing existing documents.
              </p>
              {embeddingChanged && (
                <div
                  className="flex items-start gap-2 mt-2 px-3 py-2 rounded-md"
                  style={{
                    backgroundColor: "#fffbeb",
                    borderRadius: brand.radius,
                    fontFamily: brand.fontBody,
                  }}
                >
                  <AlertCircle
                    style={{ width: "14px", height: "14px", color: "#d97706", marginTop: "1px", flexShrink: 0 }}
                    aria-hidden="true"
                  />
                  <span className="text-xs" style={{ color: "#92400e" }}>
                    After saving, re-index all documents from the Knowledge Base page so embeddings match the new model.
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Retrieval configuration */}
        <div style={cardStyle} className="mb-4">
          <div className="px-5 py-4" style={{ borderBottom: "1px solid #e2e8f0" }}>
            <h2
              className="text-sm font-semibold"
              style={{ fontFamily: brand.fontHeading, color: "#0f172a" }}
            >
              Retrieval Configuration
            </h2>
            <p className="text-xs mt-0.5" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
              Controls how strictly the Knowledge Base matches questions to document chunks.
            </p>
          </div>

          <div className="px-5 py-4">
            <label htmlFor="cosine-threshold" style={labelStyle}>
              Cosine Similarity Threshold
            </label>
            <div className="flex items-center gap-3 mb-3">
              <input
                id="cosine-threshold"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={draft.cosine_threshold}
                onChange={(e) => updateDraft("cosine_threshold", parseFloat(e.target.value) || 0)}
                className="w-24 px-3 py-1.5 text-sm border rounded-md"
                style={{
                  fontFamily: brand.fontBody,
                  fontSize: "0.8125rem",
                  borderColor: "#cbd5e1",
                  borderRadius: brand.radius,
                  fontVariantNumeric: "tabular-nums",
                }}
                aria-describedby="threshold-help"
              />
              <span className="text-sm" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
                Chunks with similarity ≥ threshold are used for grounded answers.
              </span>
            </div>

            {/* Preset buttons */}
            <div className="flex items-center gap-2 mb-3" role="group" aria-label="Threshold presets">
              {thresholdPresets.map((preset) => {
                const isExact = Math.abs(draft.cosine_threshold - preset.value) < 0.001;
                return (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => updateDraft("cosine_threshold", preset.value)}
                    className="text-xs px-3 py-1 rounded-md transition-all"
                    style={{
                      fontFamily: brand.fontBody,
                      fontWeight: 500,
                      borderRadius: brand.radius,
                      border: isExact ? "1px solid " + brand.primaryColor : "1px solid #cbd5e1",
                      backgroundColor: isExact ? brand.primaryColor : "#ffffff",
                      color: isExact ? "#ffffff" : "#475569",
                      cursor: "pointer",
                      transition: "background-color 150ms ease, color 150ms ease, border-color 150ms ease",
                    }}
                    title={preset.hint}
                    aria-pressed={isExact}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>

            {/* Visual indicator */}
            <div
              className="relative h-2 rounded-full overflow-hidden"
              style={{ backgroundColor: "#e2e8f0", borderRadius: brand.radius }}
              aria-hidden="true"
            >
              <div
                style={{
                  width: (draft.cosine_threshold * 100) + "%",
                  height: "100%",
                  backgroundColor: brand.primaryColor,
                  transition: "width 200ms ease",
                }}
              />
            </div>
            <div className="flex justify-between text-xs mt-1" style={{ color: brand.neutralColor, fontFamily: brand.fontBody, fontVariantNumeric: "tabular-nums" }}>
              <span>0.00 — match everything</span>
              <span>1.00 — exact only</span>
            </div>

            <p id="threshold-help" style={{ ...helpStyle, marginTop: "0.75rem" }}>
              Below this threshold, the system falls back to Gemini general knowledge with a
              "Not from your documents" badge instead of returning low-relevance chunks.
            </p>
            {thresholdChanged && (
              <p className="text-xs mt-1 font-medium" style={{ color: brand.primaryColor, fontFamily: brand.fontBody, fontVariantNumeric: "tabular-nums" }}>
                Pending: {settings.cosine_threshold.toFixed(2)} → {draft.cosine_threshold.toFixed(2)}
              </p>
            )}
          </div>
        </div>

        {/* Security configuration */}
        <div style={cardStyle} className="mb-4">
          <div className="px-5 py-4" style={{ borderBottom: "1px solid #e2e8f0" }}>
            <h2
              className="text-sm font-semibold"
              style={{ fontFamily: brand.fontHeading, color: "#0f172a" }}
            >
              Session Security
            </h2>
            <p className="text-xs mt-0.5" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
              Controls the Secure flag on HTTP-only session cookies.
            </p>
          </div>

          <div className="px-5 py-4">
            <div className="flex items-center justify-between">
              <div className="flex-1 pr-4">
                <label
                  htmlFor="cookie-secure"
                  className="text-sm font-semibold"
                  style={{ fontFamily: brand.fontBody, color: "#334155", display: "block", marginBottom: "0.25rem" }}
                >
                  Secure Cookie Flag
                </label>
                <p style={helpStyle}>
                  When enabled, session cookies are sent only over HTTPS. Disable for local HTTP development.
                  {cookieChanged && (
                    <span className="block mt-1 font-medium" style={{ color: brand.primaryColor }}>
                      Pending: {settings.cookie_secure_flag ? "Enabled" : "Disabled"} →{" "}
                      {draft.cookie_secure_flag ? "Enabled" : "Disabled"}
                    </span>
                  )}
                </p>
              </div>
              <Switch
                id="cookie-secure"
                checked={draft.cookie_secure_flag}
                onChange={(e) => updateDraft("cookie_secure_flag", e.target.checked)}
                aria-label="Toggle secure cookie flag"
              />
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            className="flex items-start gap-2 px-4 py-3 rounded-md mb-4"
            style={{
              backgroundColor: "#fef2f2",
              borderRadius: brand.radius,
              border: "1px solid #fecaca",
            }}
            role="alert"
          >
            <AlertCircle style={{ width: "16px", height: "16px", color: "#dc2626", flexShrink: 0, marginTop: "1px" }} aria-hidden="true" />
            <span className="text-sm" style={{ color: "#991b1b", fontFamily: brand.fontBody }}>
              {error}
            </span>
          </div>
        )}

        {/* Action bar */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-3">
            <Button
              type="submit"
              disabled={saving || !dirty}
              style={{
                fontFamily: brand.fontBody,
                backgroundColor: dirty && !saving ? brand.primaryColor : "#cbd5e1",
                color: "#ffffff",
                borderRadius: brand.radius,
                border: "none",
                cursor: dirty && !saving ? "pointer" : "not-allowed",
                opacity: saving ? 0.7 : 1,
                transition: "background-color 150ms ease, opacity 150ms ease",
                padding: "0.5rem 1.25rem",
                fontSize: "0.8125rem",
                fontWeight: 600,
              }}
            >
              {saving ? "Saving…" : "Save Settings"}
            </Button>
            {dirty && !saving && (
              <button
                type="button"
                onClick={handleReset}
                className="text-sm font-medium"
                style={{
                  fontFamily: brand.fontBody,
                  color: brand.neutralColor,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  borderRadius: brand.radius,
                  padding: "0.5rem 0.75rem",
                  transition: "color 150ms ease",
                }}
              >
                Discard changes
              </button>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs" style={{ color: brand.neutralColor, fontFamily: brand.fontBody }}>
            <button
              type="button"
              onClick={() => navigate("account")}
              className="hover:underline"
              style={{ fontFamily: brand.fontBody, color: brand.neutralColor, background: "none", border: "none", cursor: "pointer" }}
            >
              Change my password
            </button>
            <span aria-hidden="true">·</span>
            <button
              type="button"
              onClick={() => navigate("knowledge-base")}
              className="hover:underline"
              style={{ fontFamily: brand.fontBody, color: brand.neutralColor, background: "none", border: "none", cursor: "pointer" }}
            >
              Knowledge Base
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
