// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";
import { apiFetch, apiUpload, ApiError, API_BASE_URL } from "@/lib/api";

const { Button, Input, Select, Table, THead, TBody, TR, TH, TD, Stat } = UI;
const { Search, Check, User, FileText, Trash, Edit, Filter, Download, Upload, AlertCircle } = Icons;

// DocumentListItem from GET /documents:
//   {id, filename, file_type, file_size, status, created_at, failure_reason|null}
// DocumentResponse from POST /documents:
//   {id, filename, file_type, file_size, status, created_at}  (no failure_reason)
//
// Normalize either shape into the row model the table renders against.
// `failure_reason` defaults to null for freshly-uploaded documents.
function normalizeDocument(d) {
  return {
    id: d.id,
    filename: d.filename,
    file_type: d.file_type,
    file_size: d.file_size,
    status: d.status,
    failure_reason: d.failure_reason || null,
    created_at: d.created_at,
  };
}

// Extract a human-readable message from an ApiError body. FastAPI returns
// {"detail": "string"} or {"detail": [{msg: "..."}]} on 422/403/etc.
function extractApiMessage(err, fallback) {
  if (err && err.body && typeof err.body === "object") {
    var detail = err.body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      if (typeof detail[0] === "string") return detail[0];
      if (detail[0] && detail[0].msg) return detail[0].msg;
    }
    if (typeof err.body.message === "string") return err.body.message;
  }
  if (err && err.status === 403) {
    return "You do not have permission to delete documents. Administrator access is required.";
  }
  if (err && err.status === 404) {
    return "The document could not be found. It may have already been deleted.";
  }
  return fallback;
}

// Parse the filename from a Content-Disposition header. Returns null when
// the header is absent or doesn't contain a filename token. Handles the
// RFC 5987 extended form (filename*=UTF-8''encoded), quoted, and unquoted
// forms.
function parseFilenameFromDisposition(disposition) {
  if (!disposition) return null;
  // RFC 5987 extended: filename*=UTF-8''encoded-name
  var starMatch = disposition.match(/filename\*=UTF-8''([^;\s]+)/i);
  if (starMatch) {
    try {
      return decodeURIComponent(starMatch[1]);
    } catch (e) {
      return starMatch[1];
    }
  }
  // Quoted: filename="name.pdf"
  var quotedMatch = disposition.match(/filename="([^"]+)"/i);
  if (quotedMatch) return quotedMatch[1];
  // Unquoted: filename=name.pdf
  var unquotedMatch = disposition.match(/filename=([^;\s]+)/i);
  if (unquotedMatch) return unquotedMatch[1];
  return null;
}

export default function Screen() {
  const navigate = useNavigate();
  const brand = {
    primaryColor: "#1d4ed8",
    accentColor: "#059669",
    neutralColor: "#64748b",
    backgroundColor: "#f8fafc",
    radius: "0.5rem",
    fontHeading: "Inter, system-ui, sans-serif",
    fontBody: "Inter, system-ui, sans-serif",
  };

  // Current user (admin)
  const currentUser = {
    email: "satya.ganaraju@quorq.ai",
    role: "Administrator",
    name: "Satya Ganaraju",
  };
  const isAdmin = currentUser.role === "Administrator";

  // Documents are loaded from GET /documents — never initialized from a
  // hardcoded array (AC-047).
  const [documents, setDocuments] = React.useState([]);
  const [searchTerm, setSearchTerm] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("all");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [uploadError, setUploadError] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState(null);
  const [recentlyUploaded, setRecentlyUploaded] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [retryingId, setRetryingId] = React.useState(null);
  const [retryCount, setRetryCount] = React.useState(0);
  const [downloadError, setDownloadError] = React.useState(null);
  const [downloadingId, setDownloadingId] = React.useState(null);
  const [deletingId, setDeletingId] = React.useState(null);
  const [deleteError, setDeleteError] = React.useState(null);

  // ── Fetch documents from GET /documents on mount and on retry ────────────
  React.useEffect(
    function () {
      var cancelled = false;
      async function load() {
        setLoading(true);
        setLoadError(null);
        try {
          var data = await apiFetch("/documents");
          if (!cancelled) setDocuments((data || []).map(normalizeDocument));
        } catch (err) {
          if (!cancelled) {
            setLoadError(
              "Could not load the Knowledge Base. Please check your connection and try again.",
            );
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      }
      load();
      return function () {
        cancelled = true;
      };
    },
    [retryCount],
  );

  // Counts for statistics
  const stats = {
    total: documents.length,
    ready: documents.filter((d) => d.status === "Ready").length,
    processing: documents.filter((d) => d.status === "Processing").length,
    failed: documents.filter((d) => d.status === "Failed").length,
  };

  // Filtered documents
  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      searchTerm === "" || doc.filename.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === "all" || doc.file_type === typeFilter;
    const matchesStatus = statusFilter === "all" || doc.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

  // Helper: format file size
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  // Helper: format date
  function formatDate(iso) {
    const d = new Date(iso);
    const opts = {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    };
    return d.toLocaleDateString("en-US", opts);
  }

  // Handle file upload — POST /documents as multipart/form-data (AC: upload)
  async function handleFileUpload(file) {
    setUploadError(null);

    if (!file) return;

    // Client-side pre-validation for instant feedback; the server also
    // enforces these and its 422 message is surfaced on rejection.
    const ext = file.name.split(".").pop().toUpperCase();
    const allowedTypes = ["PDF", "DOCX", "TXT", "MD"];
    if (!allowedTypes.includes(ext)) {
      setUploadError(
        file.name + " is not a supported format. Only PDF, DOCX, TXT, and MD files are accepted.",
      );
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setUploadError(
        file.name + " is " + formatSize(file.size) + " — exceeds the 25 MB upload limit.",
      );
      return;
    }

    setUploading(true);

    try {
      var newDoc = await apiUpload("/documents", file);
      var normalized = normalizeDocument(newDoc);
      setDocuments((prev) => [normalized, ...prev]);
      setRecentlyUploaded((prev) => [...prev, normalized.id]);
    } catch (err) {
      // Surface the server-provided message for 422 (size/type), 403
      // (forbidden), and other errors.
      if (err instanceof ApiError || (err && err.status)) {
        setUploadError(
          extractApiMessage(
            err,
            "Upload failed. The file could not be processed. Please try again.",
          ),
        );
      } else {
        // Network error — fetch never reached the server.
        setUploadError(
          "Could not reach the server to upload " +
            file.name +
            ". Please check your connection and try again.",
        );
      }
    } finally {
      setUploading(false);
    }
  }

  function handleFileInputChange(e) {
    const file = e.target.files && e.target.files[0];
    if (file) handleFileUpload(file);
    e.target.value = "";
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    if (isAdmin) setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (!isAdmin) return;
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }

  // Delete a document via DELETE /documents/{id}. The document is removed
  // from local state ONLY after a successful API response (200/204). On
  // failure (403, 404, network error) the document remains in the table
  // and a user-visible error is shown inside the confirmation dialog.
  async function handleDelete(docId) {
    setDeletingId(docId);
    setDeleteError(null);
    try {
      await apiFetch("/documents/" + docId, { method: "DELETE" });
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setConfirmDeleteId(null);
      setRecentlyUploaded((prev) => prev.filter((id) => id !== docId));
    } catch (err) {
      setDeleteError(
        extractApiMessage(
          err,
          "Could not delete the document. Please check your connection and try again.",
        ),
      );
    } finally {
      setDeletingId(null);
    }
  }

  // Re-index a failed/ready document via POST /documents/{id}/reindex.
  // No setTimeout simulation — the API response drives the status update.
  async function handleReindex(docId) {
    setRetryingId(docId);
    var prevDoc = documents.find((d) => d.id === docId);
    // Optimistically set to Processing.
    setDocuments((prev) =>
      prev.map((d) => (d.id === docId ? { ...d, status: "Processing", failure_reason: null } : d)),
    );

    try {
      var result = await apiFetch("/documents/" + docId + "/reindex", { method: "POST" });
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === docId
            ? { ...d, status: (result && result.status) || d.status, failure_reason: null }
            : d,
        ),
      );
    } catch (err) {
      // Revert to the previous status on failure.
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === docId
            ? {
                ...d,
                status: prevDoc ? prevDoc.status : d.status,
                failure_reason: prevDoc ? prevDoc.failure_reason : null,
              }
            : d,
        ),
      );
      setUploadError(
        extractApiMessage(
          err,
          "Re-index failed. The document could not be reprocessed. Please try again.",
        ),
      );
    } finally {
      setRetryingId(null);
    }
  }

  // Download a document's original file via GET /documents/{id}/download.
  // The response is a file stream (Content-Disposition: attachment). We
  // request it as a blob, then trigger a programmatic download via a
  // temporary anchor element with a blob URL. Visible to all authenticated
  // users (admin and non-admin), matching the backend contract.
  async function handleDownload(doc) {
    setDownloadError(null);
    setDownloadingId(doc.id);
    try {
      var response = await fetch(API_BASE_URL + "/documents/" + doc.id + "/download", {
        credentials: "include",
      });
      if (!response.ok) {
        var body;
        try {
          body = await response.json();
        } catch (e) {
          body = undefined;
        }
        throw new ApiError(
          "GET /documents/" + doc.id + "/download failed: " + response.status,
          response.status,
          body,
        );
      }
      var blob = await response.blob();
      // Prefer the filename from Content-Disposition; fall back to the
      // document record's filename so the downloaded file retains its
      // original name.
      var filename =
        parseFilenameFromDisposition(response.headers.get("Content-Disposition")) || doc.filename;
      var url = window.URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError || (err && err.status)) {
        setDownloadError(
          extractApiMessage(
            err,
            "Download failed. The file could not be retrieved. Please try again.",
          ),
        );
      } else {
        // Network error — fetch never reached the server.
        setDownloadError(
          "Could not reach the server to download " +
            doc.filename +
            ". Please check your connection and try again.",
        );
      }
    } finally {
      setDownloadingId(null);
    }
  }

  // Status badge component
  function StatusBadge({ status }) {
    const config = {
      Ready: {
        bg: "rgba(5, 150, 105, 0.08)",
        color: brand.accentColor,
        label: "Ready",
        dot: brand.accentColor,
      },
      Processing: {
        bg: "rgba(29, 78, 216, 0.08)",
        color: brand.primaryColor,
        label: "Processing",
        dot: brand.primaryColor,
      },
      Failed: {
        bg: "rgba(220, 38, 38, 0.08)",
        color: "#dc2626",
        label: "Failed",
        dot: "#dc2626",
      },
    };
    const c = config[status] || config.Processing;
    return React.createElement(
      "span",
      {
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          padding: "2px 10px",
          borderRadius: "9999px",
          fontSize: "12px",
          fontWeight: 500,
          backgroundColor: c.bg,
          color: c.color,
          whiteSpace: "nowrap",
          fontVariantNumeric: "tabular-nums",
        },
      },
      React.createElement("span", {
        style: {
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: c.dot,
          animation: status === "Processing" ? "kaPulse 1.5s ease-in-out infinite" : "none",
        },
        "aria-hidden": "true",
      }),
      c.label,
    );
  }

  // Stat card
  function StatCard({ label, value, tone }) {
    const tones = {
      total: { color: "#0f172a", bg: "#ffffff", border: "#e2e8f0" },
      ready: {
        color: brand.accentColor,
        bg: "rgba(5, 150, 105, 0.04)",
        border: "rgba(5, 150, 105, 0.2)",
      },
      processing: {
        color: brand.primaryColor,
        bg: "rgba(29, 78, 216, 0.04)",
        border: "rgba(29, 78, 216, 0.2)",
      },
      failed: { color: "#dc2626", bg: "rgba(220, 38, 38, 0.04)", border: "rgba(220, 38, 38, 0.2)" },
    };
    const t = tones[tone] || tones.total;
    return React.createElement(
      "div",
      {
        style: {
          flex: "1 1 0",
          minWidth: "140px",
          backgroundColor: t.bg,
          border: "1px solid " + t.border,
          borderRadius: brand.radius,
          padding: "14px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "4px",
        },
      },
      React.createElement(
        "span",
        {
          style: {
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: brand.neutralColor,
          },
        },
        label,
      ),
      React.createElement(
        "span",
        {
          style: {
            fontSize: "28px",
            fontWeight: 700,
            color: t.color,
            lineHeight: 1.1,
            fontVariantNumeric: "tabular-nums",
          },
        },
        String(value).padStart(2, "0"),
      ),
    );
  }

  const fileInputRef = React.useRef(null);

  // Inline styles for keyframes
  const styleElement = React.createElement(
    "style",
    null,
    `
    @keyframes kaPulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    @keyframes kaSlideIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes kaShimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { animation: none !important; transition: none !important; }
    }
    .ka-row-enter { animation: kaSlideIn 0.3s ease-out; }
    .ka-link:hover { text-decoration: underline; }
    .ka-action-btn:focus-visible {
      outline: 2px solid ${brand.primaryColor};
      outline-offset: 2px;
    }
    .ka-search:focus-visible, .ka-select:focus-visible {
      outline: 2px solid ${brand.primaryColor};
      outline-offset: 1px;
    }
  `,
  );

  // Dropzone (admin only)
  const dropzone = isAdmin
    ? React.createElement(
        "div",
        {
          onDragOver: handleDragOver,
          onDragLeave: handleDragLeave,
          onDrop: handleDrop,
          style: {
            border: "2px dashed " + (isDragging ? brand.primaryColor : "#cbd5e1"),
            borderRadius: brand.radius,
            backgroundColor: isDragging ? "rgba(29, 78, 216, 0.04)" : "#ffffff",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
            transition: "all 0.2s ease",
            cursor: "pointer",
          },
          onClick: () => fileInputRef.current && fileInputRef.current.click(),
          role: "button",
          tabIndex: 0,
          "aria-label":
            "Upload a document to the Knowledge Base. Supported formats: PDF, DOCX, TXT, MD. Maximum size 25 megabytes.",
          onKeyDown: (e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current && fileInputRef.current.click();
            }
          },
        },
        React.createElement(
          "div",
          {
            style: { display: "flex", alignItems: "center", gap: "14px" },
          },
          React.createElement(Icons.Upload, {
            size: 24,
            "aria-hidden": "true",
            style: { color: brand.primaryColor },
          }),
          React.createElement(
            "div",
            null,
            React.createElement(
              "p",
              {
                style: { fontSize: "14px", fontWeight: 600, color: "#0f172a", margin: 0 },
              },
              uploading
                ? "Uploading and starting processing…"
                : "Drop a file here or click to browse",
            ),
            React.createElement(
              "p",
              {
                style: { fontSize: "12px", color: brand.neutralColor, margin: "2px 0 0 0" },
              },
              "Supported: PDF, DOCX, TXT, MD — up to 25 MB. Files are stored permanently until explicitly deleted.",
            ),
          ),
        ),
        uploading &&
          React.createElement(
            "div",
            {
              style: {
                fontSize: "12px",
                color: brand.primaryColor,
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: "8px",
              },
            },
            React.createElement("span", {
              style: {
                width: "10px",
                height: "10px",
                border: "2px solid rgba(29, 78, 216, 0.2)",
                borderTopColor: brand.primaryColor,
                borderRadius: "50%",
                display: "inline-block",
                animation: "kaPulse 0.8s linear infinite",
              },
              "aria-hidden": "true",
            }),
            "Processing upload…",
          ),
        React.createElement("input", {
          ref: fileInputRef,
          type: "file",
          accept: ".pdf,.docx,.txt,.md",
          onChange: handleFileInputChange,
          style: { display: "none" },
          "aria-hidden": "true",
          tabIndex: -1,
        }),
      )
    : null;

  // Upload error
  const uploadErrorEl = uploadError
    ? React.createElement(
        "div",
        {
          style: {
            marginTop: "8px",
            padding: "10px 14px",
            borderRadius: brand.radius,
            backgroundColor: "rgba(220, 38, 38, 0.06)",
            border: "1px solid rgba(220, 38, 38, 0.2)",
            fontSize: "13px",
            color: "#dc2626",
            display: "flex",
            alignItems: "flex-start",
            gap: "8px",
          },
          role: "alert",
        },
        React.createElement(Icons.AlertCircle, {
          size: 16,
          "aria-hidden": "true",
          style: { flexShrink: 0, marginTop: "1px" },
        }),
        React.createElement("span", null, uploadError),
      )
    : null;

  // Download error (visible to all authenticated users)
  const downloadErrorEl = downloadError
    ? React.createElement(
        "div",
        {
          style: {
            marginBottom: "12px",
            padding: "10px 14px",
            borderRadius: brand.radius,
            backgroundColor: "rgba(220, 38, 38, 0.06)",
            border: "1px solid rgba(220, 38, 38, 0.2)",
            fontSize: "13px",
            color: "#dc2626",
            display: "flex",
            alignItems: "flex-start",
            gap: "8px",
          },
          role: "alert",
        },
        React.createElement(Icons.AlertCircle, {
          size: 16,
          "aria-hidden": "true",
          style: { flexShrink: 0, marginTop: "1px" },
        }),
        React.createElement("span", null, downloadError),
      )
    : null;

  // ── Loading state ────────────────────────────────────────────────────────
  const loadingView = React.createElement(
    "div",
    {
      style: { padding: "64px 24px", textAlign: "center" },
    },
    React.createElement("span", {
      style: {
        display: "inline-block",
        width: "24px",
        height: "24px",
        border: "2px solid rgba(100,116,139,0.2)",
        borderTopColor: brand.primaryColor,
        borderRadius: "50%",
        animation: "kaPulse 0.8s linear infinite",
        verticalAlign: "middle",
        marginRight: "12px",
      },
      "aria-hidden": "true",
    }),
    React.createElement(
      "span",
      {
        style: { fontSize: "14px", color: brand.neutralColor },
      },
      "Loading documents…",
    ),
  );

  // Document table
  const tableContent = (function () {
    if (loading) {
      return loadingView;
    }

    if (loadError) {
      return React.createElement(
        "div",
        {
          style: { padding: "40px 24px", textAlign: "center" },
        },
        React.createElement(Icons.AlertCircle, {
          size: 32,
          "aria-hidden": "true",
          style: { color: "#dc2626", marginBottom: "12px" },
        }),
        React.createElement(
          "p",
          {
            style: { fontSize: "14px", fontWeight: 600, color: "#0f172a", margin: "0 0 4px 0" },
          },
          "Could not load the Knowledge Base",
        ),
        React.createElement(
          "p",
          {
            style: { fontSize: "13px", color: brand.neutralColor, margin: "0 0 16px 0" },
          },
          loadError,
        ),
        React.createElement(
          UI.Button,
          {
            variant: "outline",
            onClick: () => {
              setRetryCount((c) => c + 1);
            },
          },
          "Try again",
        ),
      );
    }

    if (filteredDocuments.length === 0 && documents.length === 0) {
      // First use / empty state
      return React.createElement(
        "div",
        {
          style: { padding: "48px 24px", textAlign: "center" },
        },
        React.createElement(Icons.FileText, {
          size: 36,
          "aria-hidden": "true",
          style: { color: "#cbd5e1", marginBottom: "12px" },
        }),
        React.createElement(
          "p",
          {
            style: { fontSize: "15px", fontWeight: 600, color: "#0f172a", margin: "0 0 6px 0" },
          },
          isAdmin ? "No documents in the Knowledge Base yet" : "No documents have been uploaded",
        ),
        React.createElement(
          "p",
          {
            style: {
              fontSize: "13px",
              color: brand.neutralColor,
              margin: "0 0 16px 0",
              maxWidth: "380px",
              marginLeft: "auto",
              marginRight: "auto",
            },
          },
          isAdmin
            ? "Upload your first document using the dropzone above. Files are indexed and become searchable in chat."
            : "An administrator needs to upload documents before they appear here. Check back shortly.",
        ),
      );
    }

    if (filteredDocuments.length === 0) {
      // No results from filters
      return React.createElement(
        "div",
        {
          style: { padding: "40px 24px", textAlign: "center" },
        },
        React.createElement(Icons.Search, {
          size: 28,
          "aria-hidden": "true",
          style: { color: "#cbd5e1", marginBottom: "10px" },
        }),
        React.createElement(
          "p",
          {
            style: { fontSize: "14px", fontWeight: 600, color: "#0f172a", margin: "0 0 4px 0" },
          },
          "No documents match your filters",
        ),
        React.createElement(
          "p",
          {
            style: { fontSize: "13px", color: brand.neutralColor, margin: "0 0 14px 0" },
          },
          "Try adjusting the search term or clearing the type and status filters.",
        ),
        React.createElement(
          UI.Button,
          {
            variant: "outline",
            onClick: () => {
              setSearchTerm("");
              setTypeFilter("all");
              setStatusFilter("all");
            },
          },
          "Clear all filters",
        ),
      );
    }

    return React.createElement(
      UI.Table,
      null,
      React.createElement(
        UI.THead,
        null,
        React.createElement(
          UI.TR,
          null,
          React.createElement(
            UI.TH,
            { style: { textAlign: "left", whiteSpace: "nowrap" } },
            "Filename",
          ),
          React.createElement(
            UI.TH,
            { style: { textAlign: "left", whiteSpace: "nowrap" } },
            "Type",
          ),
          React.createElement(
            UI.TH,
            { style: { textAlign: "right", whiteSpace: "nowrap" } },
            "Size",
          ),
          React.createElement(
            UI.TH,
            { style: { textAlign: "left", whiteSpace: "nowrap" } },
            "Uploaded",
          ),
          React.createElement(
            UI.TH,
            { style: { textAlign: "left", whiteSpace: "nowrap" } },
            "Status",
          ),
          // Actions column is always rendered — download is available to all
          // authenticated users (admin and non-admin).
          React.createElement(
            UI.TH,
            { style: { textAlign: "right", whiteSpace: "nowrap" } },
            "Actions",
          ),
        ),
      ),
      React.createElement(
        UI.TBody,
        null,
        filteredDocuments.map((doc) =>
          React.createElement(
            UI.TR,
            {
              key: doc.id,
              className: recentlyUploaded.includes(doc.id) ? "ka-row-enter" : "",
              style: { cursor: "pointer" },
              onClick: () => navigate("chat"),
            },
            // Filename
            React.createElement(
              UI.TD,
              {
                style: {
                  maxWidth: "280px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                },
              },
              React.createElement(
                "div",
                {
                  style: { display: "flex", alignItems: "center", gap: "8px" },
                },
                React.createElement(Icons.FileText, {
                  size: 14,
                  "aria-hidden": "true",
                  style: { color: brand.neutralColor, flexShrink: 0 },
                }),
                React.createElement(
                  "span",
                  {
                    style: { fontSize: "13px", fontWeight: 500, color: "#0f172a" },
                    title: doc.filename,
                  },
                  doc.filename,
                ),
              ),
            ),
            // Type
            React.createElement(
              UI.TD,
              {
                style: {
                  fontSize: "12px",
                  color: brand.neutralColor,
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                },
              },
              doc.file_type,
            ),
            // Size
            React.createElement(
              UI.TD,
              {
                style: {
                  fontSize: "12px",
                  color: brand.neutralColor,
                  textAlign: "right",
                  whiteSpace: "nowrap",
                  fontVariantNumeric: "tabular-nums",
                },
              },
              formatSize(doc.file_size),
            ),
            // Upload date
            React.createElement(
              UI.TD,
              {
                style: {
                  fontSize: "12px",
                  color: brand.neutralColor,
                  whiteSpace: "nowrap",
                  fontVariantNumeric: "tabular-nums",
                },
              },
              formatDate(doc.created_at),
            ),
            // Status
            React.createElement(
              UI.TD,
              {
                style: { whiteSpace: "nowrap" },
              },
              React.createElement(
                "div",
                {
                  style: { display: "flex", flexDirection: "column", gap: "4px" },
                },
                React.createElement(StatusBadge, { status: doc.status }),
                doc.status === "Failed" && doc.failure_reason
                  ? React.createElement(
                      "span",
                      {
                        style: {
                          fontSize: "11px",
                          color: "#991b1b",
                          maxWidth: "320px",
                          lineHeight: "1.4",
                        },
                      },
                      doc.failure_reason,
                    )
                  : null,
              ),
            ),
            // Actions — download for all authenticated users; re-index &
            // delete are admin-only.
            React.createElement(
              UI.TD,
              {
                style: { textAlign: "right", whiteSpace: "nowrap" },
                onClick: (e) => e.stopPropagation(),
              },
              React.createElement(
                "div",
                {
                  style: { display: "inline-flex", alignItems: "center", gap: "4px" },
                },
                // Download (all authenticated users)
                React.createElement(
                  "button",
                  {
                    className: "ka-action-btn",
                    onClick: () => handleDownload(doc),
                    "aria-label": "Download " + doc.filename,
                    title: "Download",
                    disabled: downloadingId === doc.id,
                    style: {
                      border: "none",
                      backgroundColor: "transparent",
                      padding: "6px",
                      borderRadius: "6px",
                      cursor: downloadingId === doc.id ? "wait" : "pointer",
                      color: brand.neutralColor,
                      display: "inline-flex",
                      alignItems: "center",
                      opacity: downloadingId === doc.id ? 0.5 : 1,
                      transition: "background-color 0.15s, color 0.15s",
                    },
                    onMouseEnter: (e) => {
                      if (downloadingId !== doc.id) {
                        e.currentTarget.style.backgroundColor = "#f1f5f9";
                        e.currentTarget.style.color = brand.primaryColor;
                      }
                    },
                    onMouseLeave: (e) => {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = brand.neutralColor;
                    },
                  },
                  downloadingId === doc.id
                    ? React.createElement("span", {
                        style: {
                          width: "15px",
                          height: "15px",
                          border: "2px solid rgba(29,78,216,0.2)",
                          borderTopColor: brand.primaryColor,
                          borderRadius: "50%",
                          display: "inline-block",
                          animation: "kaPulse 0.8s linear infinite",
                        },
                        "aria-hidden": "true",
                      })
                    : React.createElement(Icons.Download, { size: 15, "aria-hidden": "true" }),
                ),
                // Re-index (admin only, only for failed or ready)
                isAdmin && doc.status !== "Processing"
                  ? React.createElement(
                      "button",
                      {
                        className: "ka-action-btn",
                        onClick: () => handleReindex(doc.id),
                        "aria-label": "Re-index " + doc.filename,
                        title: "Re-index",
                        disabled: retryingId === doc.id,
                        style: {
                          border: "none",
                          backgroundColor: "transparent",
                          padding: "6px",
                          borderRadius: "6px",
                          cursor: retryingId === doc.id ? "wait" : "pointer",
                          color: brand.neutralColor,
                          display: "inline-flex",
                          alignItems: "center",
                          opacity: retryingId === doc.id ? 0.5 : 1,
                          transition: "background-color 0.15s, color 0.15s",
                        },
                        onMouseEnter: (e) => {
                          if (retryingId !== doc.id) {
                            e.currentTarget.style.backgroundColor = "#f1f5f9";
                            e.currentTarget.style.color = brand.primaryColor;
                          }
                        },
                        onMouseLeave: (e) => {
                          e.currentTarget.style.backgroundColor = "transparent";
                          e.currentTarget.style.color = brand.neutralColor;
                        },
                      },
                      retryingId === doc.id
                        ? React.createElement("span", {
                            style: {
                              width: "15px",
                              height: "15px",
                              border: "2px solid rgba(29,78,216,0.2)",
                              borderTopColor: brand.primaryColor,
                              borderRadius: "50%",
                              display: "inline-block",
                              animation: "kaPulse 0.8s linear infinite",
                            },
                            "aria-hidden": "true",
                          })
                        : React.createElement(Icons.Edit, { size: 15, "aria-hidden": "true" }),
                    )
                  : null,
                // Delete (admin only)
                isAdmin
                  ? React.createElement(
                      "button",
                      {
                        className: "ka-action-btn",
                        onClick: () => {
                          setConfirmDeleteId(doc.id);
                          setDeleteError(null);
                        },
                        "aria-label": "Delete " + doc.filename,
                        title: "Delete",
                        style: {
                          border: "none",
                          backgroundColor: "transparent",
                          padding: "6px",
                          borderRadius: "6px",
                          cursor: "pointer",
                          color: brand.neutralColor,
                          display: "inline-flex",
                          alignItems: "center",
                          transition: "background-color 0.15s, color 0.15s",
                        },
                        onMouseEnter: (e) => {
                          e.currentTarget.style.backgroundColor = "rgba(220,38,38,0.08)";
                          e.currentTarget.style.color = "#dc2626";
                        },
                        onMouseLeave: (e) => {
                          e.currentTarget.style.backgroundColor = "transparent";
                          e.currentTarget.style.color = brand.neutralColor;
                        },
                      },
                      React.createElement(Icons.Trash, { size: 15, "aria-hidden": "true" }),
                    )
                  : null,
              ),
            ),
          ),
        ),
      ),
    );
  })();

  // Delete confirmation dialog
  const deleteDialog = confirmDeleteId
    ? (function () {
        const doc = documents.find((d) => d.id === confirmDeleteId);
        if (!doc) return null;
        var isDeleting = deletingId === confirmDeleteId;
        return React.createElement(
          "div",
          {
            style: {
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(15, 23, 42, 0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 50,
              animation: "kaSlideIn 0.15s ease-out",
            },
            onClick: () => {
              if (!isDeleting) setConfirmDeleteId(null);
            },
            onKeyDown: (e) => {
              if (e.key === "Escape" && !isDeleting) setConfirmDeleteId(null);
            },
          },
          React.createElement(
            "div",
            {
              role: "dialog",
              "aria-modal": "true",
              "aria-labelledby": "delete-dialog-title",
              onClick: (e) => e.stopPropagation(),
              style: {
                backgroundColor: "#ffffff",
                borderRadius: brand.radius,
                padding: "24px",
                maxWidth: "420px",
                width: "90%",
                boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
              },
            },
            React.createElement(
              "h2",
              {
                id: "delete-dialog-title",
                style: {
                  fontSize: "16px",
                  fontWeight: 700,
                  color: "#0f172a",
                  margin: "0 0 8px 0",
                  fontFamily: brand.fontHeading,
                },
              },
              "Delete document?",
            ),
            React.createElement(
              "p",
              {
                style: {
                  fontSize: "14px",
                  color: "#334155",
                  margin: "0 0 20px 0",
                  lineHeight: 1.5,
                },
              },
              React.createElement("strong", null, doc.filename) +
                " will be permanently removed along with all extracted chunks, embeddings, and index metadata. This cannot be undone.",
            ),
            // Delete error — shown inside the dialog when the DELETE
            // request fails (403, 404, network error). The document is
            // NOT removed from the table.
            deleteError
              ? React.createElement(
                  "div",
                  {
                    style: {
                      marginBottom: "16px",
                      padding: "10px 14px",
                      borderRadius: brand.radius,
                      backgroundColor: "rgba(220, 38, 38, 0.06)",
                      border: "1px solid rgba(220, 38, 38, 0.2)",
                      fontSize: "13px",
                      color: "#dc2626",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                    },
                    role: "alert",
                  },
                  React.createElement(Icons.AlertCircle, {
                    size: 16,
                    "aria-hidden": "true",
                    style: { flexShrink: 0, marginTop: "1px" },
                  }),
                  React.createElement("span", null, deleteError),
                )
              : null,
            React.createElement(
              "div",
              {
                style: { display: "flex", justifyContent: "flex-end", gap: "10px" },
              },
              React.createElement(
                UI.Button,
                {
                  variant: "outline",
                  onClick: () => setConfirmDeleteId(null),
                  disabled: isDeleting,
                  style: {
                    opacity: isDeleting ? 0.5 : 1,
                    cursor: isDeleting ? "not-allowed" : "pointer",
                  },
                },
                "Cancel",
              ),
              React.createElement(
                "button",
                {
                  onClick: () => handleDelete(confirmDeleteId),
                  disabled: isDeleting,
                  "aria-busy": isDeleting,
                  style: {
                    backgroundColor: "#dc2626",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: brand.radius,
                    padding: "8px 16px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: isDeleting ? "not-allowed" : "pointer",
                    opacity: isDeleting ? 0.7 : 1,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                  },
                },
                isDeleting
                  ? [
                      React.createElement("span", {
                        key: "spinner",
                        style: {
                          width: "14px",
                          height: "14px",
                          border: "2px solid rgba(255,255,255,0.3)",
                          borderTopColor: "#ffffff",
                          borderRadius: "50%",
                          display: "inline-block",
                          animation: "kaPulse 0.8s linear infinite",
                        },
                        "aria-hidden": "true",
                      }),
                      React.createElement("span", { key: "label" }, "Deleting…"),
                    ]
                  : "Delete permanently",
              ),
            ),
          ),
        );
      })()
    : null;

  return React.createElement(
    "div",
    {
      style: {
        fontFamily: brand.fontBody,
        color: "#0f172a",
        backgroundColor: brand.backgroundColor,
        minHeight: "100%",
        padding: "24px 28px",
      },
    },
    styleElement,

    // Screen heading
    React.createElement(
      "div",
      {
        style: { marginBottom: "20px" },
      },
      React.createElement(
        "div",
        {
          style: {
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          },
        },
        React.createElement(
          "div",
          null,
          React.createElement(
            "h1",
            {
              style: {
                fontSize: "22px",
                fontWeight: 700,
                color: "#0f172a",
                margin: 0,
                fontFamily: brand.fontHeading,
                letterSpacing: "-0.01em",
              },
            },
            "Knowledge Base",
          ),
          React.createElement(
            "p",
            {
              style: { fontSize: "13px", color: brand.neutralColor, margin: "4px 0 0 0" },
            },
            documents.length +
              " documents indexed — answers cite these sources before falling back to Gemini general knowledge",
          ),
        ),
        // Account link
        React.createElement(
          "button",
          {
            onClick: () => navigate("account"),
            className: "ka-link",
            style: {
              border: "none",
              backgroundColor: "transparent",
              fontSize: "13px",
              color: brand.neutralColor,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              textDecoration: "none",
            },
            "aria-label": "Go to account settings for " + currentUser.email,
          },
          React.createElement(Icons.User, { size: 14, "aria-hidden": "true" }),
          currentUser.email,
        ),
      ),
    ),

    // Statistics
    React.createElement(
      "div",
      {
        style: { display: "flex", gap: "12px", marginBottom: "20px", flexWrap: "wrap" },
      },
      React.createElement(StatCard, {
        label: "Total Documents",
        value: stats.total,
        tone: "total",
      }),
      React.createElement(StatCard, { label: "Ready", value: stats.ready, tone: "ready" }),
      React.createElement(StatCard, {
        label: "Processing",
        value: stats.processing,
        tone: "processing",
      }),
      React.createElement(StatCard, { label: "Failed", value: stats.failed, tone: "failed" }),
    ),

    // Upload dropzone (admin only)
    isAdmin &&
      React.createElement(
        "div",
        {
          style: { marginBottom: "20px" },
        },
        dropzone,
        uploadErrorEl,
      ),

    // Search + filters bar
    React.createElement(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: "12px",
          flexWrap: "wrap",
        },
      },
      // Search
      React.createElement(
        "div",
        {
          style: { position: "relative", flex: "1 1 240px", minWidth: "200px" },
        },
        React.createElement(Icons.Search, {
          size: 15,
          "aria-hidden": "true",
          style: {
            position: "absolute",
            left: "10px",
            top: "50%",
            transform: "translateY(-50%)",
            color: brand.neutralColor,
            pointerEvents: "none",
          },
        }),
        React.createElement(UI.Input, {
          className: "ka-search",
          type: "text",
          placeholder: "Search by filename…",
          value: searchTerm,
          onChange: (e) => setSearchTerm(e.target.value),
          "aria-label": "Search documents by filename",
          style: {
            paddingLeft: "32px",
            fontSize: "13px",
            height: "34px",
            borderRadius: brand.radius,
            border: "1px solid #cbd5e1",
            backgroundColor: "#ffffff",
            width: "100%",
          },
        }),
      ),
      // Type filter
      React.createElement(
        "div",
        null,
        React.createElement(
          "label",
          {
            htmlFor: "type-filter",
            style: {
              fontSize: "11px",
              fontWeight: 600,
              color: brand.neutralColor,
              display: "block",
              marginBottom: "2px",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            },
          },
          "Type",
        ),
        React.createElement(
          UI.Select,
          {
            id: "type-filter",
            className: "ka-select",
            value: typeFilter,
            onChange: (e) => setTypeFilter(e.target.value),
            "aria-label": "Filter documents by file type",
            style: {
              fontSize: "13px",
              height: "34px",
              borderRadius: brand.radius,
              border: "1px solid #cbd5e1",
              backgroundColor: "#ffffff",
              cursor: "pointer",
            },
          },
          React.createElement("option", { value: "all" }, "All types"),
          React.createElement("option", { value: "PDF" }, "PDF"),
          React.createElement("option", { value: "DOCX" }, "DOCX"),
          React.createElement("option", { value: "TXT" }, "TXT"),
          React.createElement("option", { value: "MD" }, "MD"),
        ),
      ),
      // Status filter
      React.createElement(
        "div",
        null,
        React.createElement(
          "label",
          {
            htmlFor: "status-filter",
            style: {
              fontSize: "11px",
              fontWeight: 600,
              color: brand.neutralColor,
              display: "block",
              marginBottom: "2px",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            },
          },
          "Status",
        ),
        React.createElement(
          UI.Select,
          {
            id: "status-filter",
            className: "ka-select",
            value: statusFilter,
            onChange: (e) => setStatusFilter(e.target.value),
            "aria-label": "Filter documents by processing status",
            style: {
              fontSize: "13px",
              height: "34px",
              borderRadius: brand.radius,
              border: "1px solid #cbd5e1",
              backgroundColor: "#ffffff",
              cursor: "pointer",
            },
          },
          React.createElement("option", { value: "all" }, "All statuses"),
          React.createElement("option", { value: "Ready" }, "Ready"),
          React.createElement("option", { value: "Processing" }, "Processing"),
          React.createElement("option", { value: "Failed" }, "Failed"),
        ),
      ),
      // Results count
      React.createElement(
        "span",
        {
          style: {
            fontSize: "12px",
            color: brand.neutralColor,
            marginLeft: "auto",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          },
        },
        filteredDocuments.length + " of " + documents.length + " documents",
      ),
    ),

    // Download error (visible to all authenticated users)
    downloadErrorEl,

    // Document table
    React.createElement(
      "div",
      {
        style: {
          backgroundColor: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: brand.radius,
          overflow: "hidden",
        },
      },
      React.createElement(
        "div",
        {
          style: { overflowX: "auto" },
        },
        React.createElement(
          "div",
          {
            style: { minWidth: "720px" },
          },
          tableContent,
        ),
      ),
    ),

    // Processing note
    stats.processing > 0 &&
      !loading &&
      React.createElement(
        "div",
        {
          style: {
            marginTop: "12px",
            fontSize: "12px",
            color: brand.neutralColor,
            display: "flex",
            alignItems: "center",
            gap: "8px",
          },
        },
        React.createElement("span", {
          style: {
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            backgroundColor: brand.primaryColor,
            animation: "kaPulse 1.5s ease-in-out infinite",
          },
          "aria-hidden": "true",
        }),
        stats.processing +
          " document" +
          (stats.processing > 1 ? "s are" : " is") +
          " being indexed — status will update on the next refresh.",
      ),

    // Delete confirmation dialog
    deleteDialog,
  );
}