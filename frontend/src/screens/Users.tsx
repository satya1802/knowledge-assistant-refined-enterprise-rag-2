// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { apiFetch } from "@/lib/api";

const { Table } = UI;
const { Plus, Search, X, User, Users, AlertCircle, CheckCircle } = Icons;

const NOW = new Date();

// Normalize the API UserResponse {id, email, role} into the richer shape the
// table was designed against. Fields not returned by the backend default to
// safe values so sorting and rendering do not crash.
function normalizeUser(u) {
  return {
    id: u.id,
    email: u.email,
    role: u.role,
    failed_login_count: u.failed_login_count || 0,
    locked_until: u.locked_until || null,
    created_at: u.created_at || null,
    updated_at: u.updated_at || null,
  };
}

export default function Screen() {
  const [users, setUsers] = React.useState([]);
  const [search, setSearch] = React.useState("");
  const [roleFilter, setRoleFilter] = React.useState("all");
  const [sortField, setSortField] = React.useState("created_at");
  const [sortDir, setSortDir] = React.useState("desc");
  const [formOpen, setFormOpen] = React.useState(false);

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [role, setRole] = React.useState("Regular User");
  const [errors, setErrors] = React.useState({});
  const [successMsg, setSuccessMsg] = React.useState("");
  const [newUserId, setNewUserId] = React.useState(null);

  // API state
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(null);
  const [forbidden, setForbidden] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [retryCount, setRetryCount] = React.useState(0);

  const newUserBtnRef = React.useRef(null);
  const emailInputRef = React.useRef(null);

  // ── Fetch users from GET /users on mount and on retry ────────────────────
  React.useEffect(
    function () {
      var cancelled = false;
      async function load() {
        setLoading(true);
        setLoadError(null);
        setForbidden(false);
        try {
          var data = await apiFetch("/users");
          if (!cancelled) setUsers(data.map(normalizeUser));
        } catch (err) {
          if (cancelled) return;
          if (err && err.status === 403) {
            setForbidden(true);
          } else {
            setLoadError("Failed to load users. Please check your connection and try again.");
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

  var handleRetry = function () {
    setRetryCount(function (c) {
      return c + 1;
    });
  };

  var tint = function (hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
  };

  var borderColor = tint(brand.neutralColor, 0.2);
  var lightBorder = tint(brand.neutralColor, 0.12);
  var hoverBg = tint(brand.neutralColor, 0.04);
  var headingColor = "#0f172a";

  var isLocked = function (u) {
    return u.locked_until && new Date(u.locked_until) > NOW;
  };

  var stats = {
    total: users.length,
    admins: users.filter(function (u) {
      return u.role === "Administrator";
    }).length,
    regular: users.filter(function (u) {
      return u.role === "Regular User";
    }).length,
    locked: users.filter(isLocked).length,
  };

  var filtered = users.filter(function (u) {
    var matchesSearch = u.email.toLowerCase().indexOf(search.toLowerCase()) !== -1;
    var matchesRole = roleFilter === "all" || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  var sorted = filtered.slice().sort(function (a, b) {
    var cmp = 0;
    if (sortField === "email") cmp = a.email.localeCompare(b.email);
    else if (sortField === "role") cmp = a.role.localeCompare(b.role);
    else if (sortField === "created_at")
      cmp = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
    else if (sortField === "updated_at")
      cmp = new Date(a.updated_at || 0).getTime() - new Date(b.updated_at || 0).getTime();
    return sortDir === "asc" ? cmp : -cmp;
  });

  var handleSort = function (field) {
    if (sortField === field) {
      setSortDir(function (d) {
        return d === "asc" ? "desc" : "asc";
      });
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  var validate = function () {
    var e = {};
    if (!email.trim()) {
      e.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      e.email = "Enter a valid email address";
    }
    if (!password) {
      e.password = "Password is required";
    } else if (password.length < 8) {
      e.password = "Password must be at least 8 characters";
    }
    if (
      users.some(function (u) {
        return u.email.toLowerCase() === email.trim().toLowerCase();
      })
    ) {
      e.email = "A user with this email already exists";
    }
    return e;
  };

  var handleSubmit = async function (ev) {
    ev.preventDefault();
    var e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    setSubmitting(true);
    setErrors({});
    try {
      var newUser = await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password: password, role: role }),
      });
      var nowIso = new Date().toISOString();
      var normalized = normalizeUser(newUser);
      if (!normalized.created_at) normalized.created_at = nowIso;
      if (!normalized.updated_at) normalized.updated_at = nowIso;
      setUsers(function (prev) {
        return prev.concat([normalized]);
      });
      setNewUserId(normalized.id);
      setSuccessMsg("Account created for " + normalized.email);
      setEmail("");
      setPassword("");
      setRole("Regular User");
      setFormOpen(false);
      setTimeout(function () {
        newUserBtnRef.current && newUserBtnRef.current.focus();
      }, 0);
      setTimeout(function () {
        setNewUserId(null);
      }, 4000);
      setTimeout(function () {
        setSuccessMsg("");
      }, 5000);
    } catch (err) {
      if (err && err.status === 409) {
        setErrors({ email: "A user with this email already exists" });
      } else if (err && err.status === 403) {
        setErrors({ form: "You do not have permission to create users." });
      } else {
        setErrors({ form: "Failed to create user. Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  };

  var handleCancel = function () {
    setEmail("");
    setPassword("");
    setRole("Regular User");
    setErrors({});
    setFormOpen(false);
    setTimeout(function () {
      newUserBtnRef.current && newUserBtnRef.current.focus();
    }, 0);
  };

  var openForm = function () {
    setFormOpen(true);
    setErrors({});
    setTimeout(function () {
      var el = document.getElementById("new-email");
      if (el) el.focus();
    }, 50);
  };

  var formatDate = function (iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  };

  var formatTime = function (iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "UTC",
    });
  };

  var SortButton = function (props) {
    var field = props.field;
    var label = props.label;
    var isActive = sortField === field;
    var ariaLabel =
      "Sort by " +
      label +
      ", currently " +
      (isActive ? (sortDir === "asc" ? "ascending" : "descending") : "unsorted");
    return React.createElement(
      "button",
      {
        type: "button",
        onClick: function () {
          handleSort(field);
        },
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          fontSize: "inherit",
          fontWeight: "inherit",
          color: "inherit",
          textTransform: "inherit",
          letterSpacing: "inherit",
        },
        "aria-label": ariaLabel,
      },
      label,
      isActive &&
        React.createElement(
          "span",
          { "aria-hidden": "true", style: { fontSize: "0.7rem" } },
          sortDir === "asc" ? "↑" : "↓",
        ),
    );
  };

  var thStyle = {
    textAlign: "left",
    padding: "9px 14px",
    fontSize: "0.7rem",
    fontWeight: 600,
    color: brand.neutralColor,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    borderBottom: "1px solid " + borderColor,
    whiteSpace: "nowrap",
  };

  var thRightStyle = Object.assign({}, thStyle, { textAlign: "right" });

  var tdStyle = {
    padding: "10px 14px",
    fontSize: "0.8125rem",
    color: headingColor,
    borderBottom: "1px solid " + lightBorder,
  };

  var numStyle = Object.assign({}, tdStyle, {
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  });

  // ── Loading state ────────────────────────────────────────────────────────
  var loadingView = React.createElement(
    "div",
    {
      className: "flex items-center justify-center",
      style: { padding: "64px 24px" },
    },
    React.createElement("span", {
      className: "inline-block w-6 h-6 border-2 rounded-full",
      style: {
        borderColor: tint(brand.neutralColor, 0.2),
        borderTopColor: brand.primaryColor,
        animation: "kaSpin 0.6s linear infinite",
      },
      "aria-hidden": true,
    }),
    React.createElement(
      "span",
      { className: "ml-3 text-sm", style: { color: brand.neutralColor } },
      "Loading users…",
    ),
  );

  // ── Forbidden (403) state ─────────────────────────────────────────────────
  var forbiddenView = React.createElement(
    "div",
    {
      className: "rounded-lg text-center",
      style: {
        backgroundColor: "#fff",
        border: "1px solid " + lightBorder,
        padding: "48px 24px",
      },
    },
    React.createElement(Icons.AlertCircle, {
      size: 36,
      "aria-hidden": true,
      style: { color: "#b91c1c", marginBottom: "12px" },
    }),
    React.createElement(
      "p",
      {
        className: "text-base font-semibold",
        style: { color: headingColor, margin: "0 0 4px 0" },
      },
      "Administrator access required",
    ),
    React.createElement(
      "p",
      {
        className: "text-sm",
        style: { color: brand.neutralColor, margin: 0 },
      },
      "You do not have permission to manage users. Contact an administrator if you need access.",
    ),
  );

  // ── Error state ───────────────────────────────────────────────────────────
  var errorView = React.createElement(
    "div",
    {
      className: "rounded-lg text-center",
      style: {
        backgroundColor: "#fff",
        border: "1px solid " + lightBorder,
        padding: "48px 24px",
      },
    },
    React.createElement(Icons.AlertCircle, {
      size: 36,
      "aria-hidden": true,
      style: { color: "#b91c1c", marginBottom: "12px" },
    }),
    React.createElement(
      "p",
      {
        className: "text-base font-semibold",
        style: { color: headingColor, margin: "0 0 4px 0" },
      },
      "Failed to load users",
    ),
    React.createElement(
      "p",
      {
        className: "text-sm",
        style: { color: brand.neutralColor, margin: "0 0 16px 0" },
      },
      loadError,
    ),
    React.createElement(
      "button",
      {
        type: "button",
        onClick: handleRetry,
        className: "px-4 py-2 text-sm font-medium",
        style: {
          backgroundColor: "transparent",
          color: brand.primaryColor,
          border: "1px solid " + tint(brand.primaryColor, 0.3),
          borderRadius: brand.radius,
          cursor: "pointer",
        },
      },
      "Try again",
    ),
  );

  var ready = !loading && !forbidden && !loadError;

  return React.createElement(
    "div",
    { style: { fontFamily: brand.fontBody, color: headingColor } },
    React.createElement(
      "style",
      null,
      "@keyframes slideDown { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } } " +
        "@keyframes highlightRow { 0% { background-color: " +
        tint(brand.accentColor, 0.15) +
        "; } 100% { background-color: transparent; } } " +
        "@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } } " +
        "@keyframes kaSpin { to { transform: rotate(360deg); } } " +
        ".form-panel { animation: slideDown 0.2s ease-out; } " +
        ".row-highlight { animation: highlightRow 4s ease-out; } " +
        ".success-banner { animation: fadeIn 0.2s ease-out; } " +
        ".kb-row:hover { background-color: " +
        hoverBg +
        "; } " +
        ".kb-row { transition: background-color 0.15s ease; } " +
        "@media (prefers-reduced-motion: reduce) { " +
        ".form-panel, .row-highlight, .success-banner { animation: none; } " +
        ".form-panel { opacity: 1; transform: none; } " +
        ".kb-row { transition: none; } " +
        "}",
    ),

    /* Header */
    React.createElement(
      "div",
      { className: "flex items-start justify-between mb-5" },
      React.createElement(
        "div",
        null,
        React.createElement(
          "h1",
          {
            className: "text-2xl font-semibold tracking-tight",
            style: { color: headingColor, fontFamily: brand.fontHeading, margin: 0 },
          },
          "User Management",
        ),
        React.createElement(
          "p",
          {
            className: "text-sm mt-1",
            style: { color: brand.neutralColor },
          },
          "Provision access and review who can use the Knowledge Assistant",
        ),
      ),
      ready &&
        React.createElement(
          "button",
          {
            ref: newUserBtnRef,
            type: "button",
            onClick: function () {
              if (formOpen) handleCancel();
              else openForm();
            },
            className:
              "inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium transition-opacity hover:opacity-90",
            style: {
              backgroundColor: formOpen ? "transparent" : brand.primaryColor,
              color: formOpen ? brand.neutralColor : "#fff",
              border: formOpen ? "1px solid " + borderColor : "1px solid " + brand.primaryColor,
              borderRadius: brand.radius,
              cursor: "pointer",
            },
            "aria-expanded": formOpen,
            "aria-controls": "create-user-form",
          },
          formOpen
            ? [React.createElement(Icons.X, { key: "x", size: 16, "aria-hidden": true }), "Close"]
            : [
                React.createElement(Icons.Plus, { key: "plus", size: 16, "aria-hidden": true }),
                "New User",
              ],
        ),
    ),

    /* Conditional states */
    loading
      ? loadingView
      : forbidden
        ? forbiddenView
        : loadError
          ? errorView
          : React.createElement(
              React.Fragment,
              null,
              /* Stats strip */
              React.createElement(
                "div",
                { className: "grid grid-cols-4 gap-3 mb-5" },
                ["Total Users", "Administrators", "Regular Users", "Locked Accounts"].map(
                  function (label, i) {
                    var value = [stats.total, stats.admins, stats.regular, stats.locked][i];
                    var valColor = [
                      headingColor,
                      brand.primaryColor,
                      headingColor,
                      stats.locked > 0 ? "#b45309" : headingColor,
                    ][i];
                    return React.createElement(
                      "div",
                      {
                        key: label,
                        className: "rounded-lg",
                        style: {
                          backgroundColor: "#fff",
                          border: "1px solid " + lightBorder,
                          padding: "12px 14px",
                        },
                      },
                      React.createElement(
                        "div",
                        {
                          className: "text-xs font-medium uppercase tracking-wide",
                          style: { color: brand.neutralColor },
                        },
                        label,
                      ),
                      React.createElement(
                        "div",
                        {
                          className: "text-2xl font-semibold mt-1",
                          style: { color: valColor, fontVariantNumeric: "tabular-nums" },
                        },
                        String(value),
                      ),
                    );
                  },
                ),
              ),

              /* Success banner */
              successMsg &&
                React.createElement(
                  "div",
                  {
                    className: "success-banner mb-4 flex items-center gap-2 px-4 py-3 rounded-lg",
                    style: {
                      backgroundColor: tint(brand.accentColor, 0.08),
                      border: "1px solid " + tint(brand.accentColor, 0.25),
                    },
                    role: "status",
                    "aria-live": "polite",
                  },
                  React.createElement(Icons.CheckCircle, {
                    size: 16,
                    "aria-hidden": true,
                    style: { color: brand.accentColor, flexShrink: 0 },
                  }),
                  React.createElement(
                    "span",
                    { className: "text-sm font-medium", style: { color: brand.accentColor } },
                    successMsg,
                  ),
                  React.createElement(
                    "button",
                    {
                      type: "button",
                      onClick: function () {
                        setSuccessMsg("");
                      },
                      "aria-label": "Dismiss notification",
                      style: {
                        marginLeft: "auto",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: brand.neutralColor,
                        padding: 0,
                        display: "flex",
                      },
                    },
                    React.createElement(Icons.X, { size: 14, "aria-hidden": true }),
                  ),
                ),

              /* Form panel */
              formOpen &&
                React.createElement(
                  "div",
                  { className: "form-panel mb-5", id: "create-user-form" },
                  React.createElement(
                    "form",
                    { onSubmit: handleSubmit },
                    React.createElement(
                      "div",
                      {
                        className: "rounded-lg",
                        style: {
                          backgroundColor: "#fff",
                          border: "1px solid " + tint(brand.primaryColor, 0.2),
                        },
                      },
                      /* Form header */
                      React.createElement(
                        "div",
                        { style: { padding: "14px 16px 0 16px" } },
                        React.createElement(
                          "div",
                          {
                            className: "text-base font-semibold",
                            style: { color: headingColor },
                          },
                          "Create New User Account",
                        ),
                        React.createElement(
                          "p",
                          {
                            className: "text-sm mt-0.5",
                            style: { color: brand.neutralColor },
                          },
                          "The user can change their password after first sign-in. Passwords are stored as bcrypt hashes.",
                        ),
                      ),
                      /* Form-level error */
                      errors.form &&
                        React.createElement(
                          "div",
                          {
                            className: "flex items-center gap-2 mx-4 mt-3 px-3 py-2 rounded-md",
                            style: {
                              backgroundColor: "#fef2f2",
                              border: "1px solid #fecaca",
                            },
                            role: "alert",
                          },
                          React.createElement(Icons.AlertCircle, {
                            size: 14,
                            "aria-hidden": true,
                            style: { color: "#b91c1c", flexShrink: 0 },
                          }),
                          React.createElement(
                            "span",
                            { className: "text-sm", style: { color: "#991b1b" } },
                            errors.form,
                          ),
                        ),
                      /* Form fields */
                      React.createElement(
                        "div",
                        {
                          className: "grid grid-cols-1 sm:grid-cols-3 gap-4",
                          style: { padding: "14px 16px" },
                        },
                        /* Email */
                        React.createElement(
                          "div",
                          null,
                          React.createElement(
                            "label",
                            {
                              htmlFor: "new-email",
                              className: "text-xs font-medium block mb-1",
                              style: { color: brand.neutralColor },
                            },
                            "Email",
                          ),
                          React.createElement("input", {
                            id: "new-email",
                            type: "email",
                            value: email,
                            onChange: function (e) {
                              setEmail(e.target.value);
                              if (errors.email)
                                setErrors(function (p) {
                                  var c = Object.assign({}, p);
                                  delete c.email;
                                  return c;
                                });
                            },
                            ref: emailInputRef,
                            className: "w-full px-3 py-2 text-sm rounded-md outline-none transition-colors",
                            style: {
                              border: "1px solid " + (errors.email ? "#b91c1c" : borderColor),
                              borderRadius: brand.radius,
                              backgroundColor: "#fff",
                              color: headingColor,
                            },
                            "aria-invalid": !!errors.email,
                            "aria-describedby": errors.email ? "email-error" : undefined,
                            autoComplete: "off",
                          }),
                          errors.email &&
                            React.createElement(
                              "p",
                              {
                                id: "email-error",
                                className: "text-xs mt-1 flex items-center gap-1",
                                style: { color: "#b91c1c" },
                                role: "alert",
                              },
                              React.createElement(Icons.AlertCircle, {
                                size: 12,
                                "aria-hidden": true,
                              }),
                              errors.email,
                            ),
                        ),
                        /* Password */
                        React.createElement(
                          "div",
                          null,
                          React.createElement(
                            "label",
                            {
                              htmlFor: "new-password",
                              className: "text-xs font-medium block mb-1",
                              style: { color: brand.neutralColor },
                            },
                            "Password",
                          ),
                          React.createElement("input", {
                            id: "new-password",
                            type: "password",
                            value: password,
                            onChange: function (e) {
                              setPassword(e.target.value);
                              if (errors.password)
                                setErrors(function (p) {
                                  var c = Object.assign({}, p);
                                  delete c.password;
                                  return c;
                                });
                            },
                            className: "w-full px-3 py-2 text-sm rounded-md outline-none transition-colors",
                            style: {
                              border: "1px solid " + (errors.password ? "#b91c1c" : borderColor),
                              borderRadius: brand.radius,
                              backgroundColor: "#fff",
                              color: headingColor,
                            },
                            "aria-invalid": !!errors.password,
                            "aria-describedby": errors.password
                              ? "password-error"
                              : "password-hint",
                            autoComplete: "new-password",
                          }),
                          errors.password
                            ? React.createElement(
                                "p",
                                {
                                  id: "password-error",
                                  className: "text-xs mt-1 flex items-center gap-1",
                                  style: { color: "#b91c1c" },
                                  role: "alert",
                                },
                                React.createElement(Icons.AlertCircle, {
                                  size: 12,
                                  "aria-hidden": true,
                                }),
                                errors.password,
                              )
                            : React.createElement(
                                "p",
                                {
                                  id: "password-hint",
                                  className: "text-xs mt-1",
                                  style: { color: brand.neutralColor },
                                },
                                "Minimum 8 characters",
                              ),
                        ),
                        /* Role */
                        React.createElement(
                          "div",
                          null,
                          React.createElement(
                            "label",
                            {
                              htmlFor: "new-role",
                              className: "text-xs font-medium block mb-1",
                              style: { color: brand.neutralColor },
                            },
                            "Role",
                          ),
                          React.createElement(
                            "select",
                            {
                              id: "new-role",
                              value: role,
                              onChange: function (e) {
                                setRole(e.target.value);
                              },
                              className: "w-full px-3 py-2 text-sm rounded-md outline-none",
                              style: {
                                border: "1px solid " + borderColor,
                                borderRadius: brand.radius,
                                backgroundColor: "#fff",
                                color: headingColor,
                              },
                            },
                            React.createElement("option", { value: "Regular User" }, "Regular User"),
                            React.createElement(
                              "option",
                              { value: "Administrator" },
                              "Administrator",
                            ),
                          ),
                          React.createElement(
                            "p",
                            {
                              className: "text-xs mt-1",
                              style: { color: brand.neutralColor },
                            },
                            role === "Administrator"
                              ? "Full access: upload, delete, manage users and settings"
                              : "Can chat with the Knowledge Base and view documents",
                          ),
                        ),
                      ),
                      /* Form footer */
                      React.createElement(
                        "div",
                        {
                          className: "flex items-center gap-2",
                          style: { padding: "0 16px 14px 16px" },
                        },
                        React.createElement(
                          "button",
                          {
                            type: "submit",
                            disabled: submitting,
                            className:
                              "px-4 py-2 text-sm font-medium transition-opacity hover:opacity-90",
                            style: {
                              backgroundColor: brand.primaryColor,
                              color: "#fff",
                              border: "1px solid " + brand.primaryColor,
                              borderRadius: brand.radius,
                              cursor: submitting ? "not-allowed" : "pointer",
                              opacity: submitting ? 0.6 : 1,
                            },
                          },
                          submitting ? "Creating…" : "Create account",
                        ),
                        React.createElement(
                          "button",
                          {
                            type: "button",
                            onClick: handleCancel,
                            disabled: submitting,
                            className: "px-4 py-2 text-sm font-medium transition-colors",
                            style: {
                              backgroundColor: "transparent",
                              color: brand.neutralColor,
                              border: "1px solid " + borderColor,
                              borderRadius: brand.radius,
                              cursor: submitting ? "not-allowed" : "pointer",
                              opacity: submitting ? 0.6 : 1,
                            },
                          },
                          "Cancel",
                        ),
                      ),
                    ),
                  ),
                ),

              /* Toolbar */
              React.createElement(
                "div",
                { className: "flex items-center gap-3 mb-3 flex-wrap" },
                React.createElement(
                  "div",
                  { className: "relative flex-1", style: { maxWidth: "360px" } },
                  React.createElement(Icons.Search, {
                    size: 16,
                    "aria-hidden": true,
                    style: {
                      position: "absolute",
                      left: "10px",
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: brand.neutralColor,
                      pointerEvents: "none",
                    },
                  }),
                  React.createElement(
                    "label",
                    { htmlFor: "user-search", className: "sr-only" },
                    "Search users by email",
                  ),
                  React.createElement("input", {
                    id: "user-search",
                    type: "text",
                    value: search,
                    onChange: function (e) {
                      setSearch(e.target.value);
                    },
                    placeholder: "Search by email…",
                    className: "w-full pl-9 pr-3 py-2 text-sm rounded-md outline-none",
                    style: {
                      border: "1px solid " + borderColor,
                      borderRadius: brand.radius,
                      backgroundColor: "#fff",
                      color: headingColor,
                    },
                  }),
                ),
                React.createElement(
                  "div",
                  { className: "flex items-center gap-2" },
                  React.createElement(
                    "label",
                    {
                      htmlFor: "role-filter",
                      className: "text-xs font-medium",
                      style: { color: brand.neutralColor },
                    },
                    "Role",
                  ),
                  React.createElement(
                    "select",
                    {
                      id: "role-filter",
                      value: roleFilter,
                      onChange: function (e) {
                        setRoleFilter(e.target.value);
                      },
                      className: "px-3 py-2 text-sm rounded-md outline-none",
                      style: {
                        border: "1px solid " + borderColor,
                        borderRadius: brand.radius,
                        backgroundColor: "#fff",
                        color: headingColor,
                      },
                    },
                    React.createElement("option", { value: "all" }, "All roles"),
                    React.createElement("option", { value: "Administrator" }, "Administrator"),
                    React.createElement("option", { value: "Regular User" }, "Regular User"),
                  ),
                ),
                React.createElement(
                  "div",
                  {
                    className: "text-sm",
                    style: {
                      color: brand.neutralColor,
                      fontVariantNumeric: "tabular-nums",
                      marginLeft: "auto",
                    },
                  },
                  sorted.length + " of " + users.length + " users",
                ),
              ),

              /* Table or empty state */
              sorted.length === 0
                ? React.createElement(
                    "div",
                    {
                      className: "rounded-lg text-center",
                      style: {
                        backgroundColor: "#fff",
                        border: "1px solid " + lightBorder,
                        padding: "48px 24px",
                      },
                    },
                    React.createElement(Icons.Users, {
                      size: 36,
                      "aria-hidden": true,
                      style: { color: tint(brand.neutralColor, 0.5), marginBottom: "12px" },
                    }),
                    React.createElement(
                      "p",
                      {
                        className: "text-sm font-semibold",
                        style: { color: headingColor, margin: "0 0 4px 0" },
                      },
                      users.length === 0 ? "No users yet" : "No users match your search",
                    ),
                    React.createElement(
                      "p",
                      {
                        className: "text-sm",
                        style: { color: brand.neutralColor, margin: "0 0 16px 0" },
                      },
                      users.length === 0
                        ? "Create your first user account to get started."
                        : "Try a different email or role filter.",
                    ),
                    users.length > 0 &&
                      React.createElement(
                        "button",
                        {
                          type: "button",
                          onClick: function () {
                            setSearch("");
                            setRoleFilter("all");
                          },
                          className: "px-4 py-2 text-sm font-medium",
                          style: {
                            backgroundColor: "transparent",
                            color: brand.primaryColor,
                            border: "1px solid " + tint(brand.primaryColor, 0.3),
                            borderRadius: brand.radius,
                            cursor: "pointer",
                          },
                        },
                        "Clear filters",
                      ),
                  )
                : React.createElement(
                    "div",
                    {
                      className: "rounded-lg overflow-hidden",
                      style: { backgroundColor: "#fff", border: "1px solid " + lightBorder },
                    },
                    React.createElement(
                      "div",
                      { style: { overflowX: "auto" } },
                      React.createElement(
                        "table",
                        {
                          style: {
                            width: "100%",
                            borderCollapse: "collapse",
                            fontVariantNumeric: "tabular-nums",
                          },
                        },
                        React.createElement(
                          "thead",
                          null,
                          React.createElement(
                            "tr",
                            null,
                            React.createElement(
                              "th",
                              { style: thStyle },
                              React.createElement(SortButton, { field: "email", label: "Email" }),
                            ),
                            React.createElement(
                              "th",
                              { style: thStyle },
                              React.createElement(SortButton, { field: "role", label: "Role" }),
                            ),
                            React.createElement("th", { style: thStyle }, "Status"),
                            React.createElement("th", { style: thRightStyle }, "Failed Logins"),
                            React.createElement(
                              "th",
                              { style: thStyle },
                              React.createElement(SortButton, {
                                field: "created_at",
                                label: "Created",
                              }),
                            ),
                            React.createElement(
                              "th",
                              { style: thStyle },
                              React.createElement(SortButton, {
                                field: "updated_at",
                                label: "Last Updated",
                              }),
                            ),
                          ),
                        ),
                        React.createElement(
                          "tbody",
                          null,
                          sorted.map(function (u) {
                            var locked = isLocked(u);
                            return React.createElement(
                              "tr",
                              {
                                key: u.id,
                                className: "kb-row" + (u.id === newUserId ? " row-highlight" : ""),
                              },
                              /* Email */
                              React.createElement(
                                "td",
                                {
                                  style: Object.assign({}, tdStyle, { fontWeight: 500 }),
                                },
                                u.email,
                              ),
                              /* Role */
                              React.createElement(
                                "td",
                                { style: tdStyle },
                                React.createElement(
                                  "span",
                                  {
                                    style: {
                                      display: "inline-block",
                                      padding: "2px 8px",
                                      borderRadius: "0.375rem",
                                      fontSize: "0.75rem",
                                      fontWeight: 500,
                                      backgroundColor:
                                        u.role === "Administrator"
                                          ? tint(brand.primaryColor, 0.1)
                                          : tint(brand.neutralColor, 0.1),
                                      color:
                                        u.role === "Administrator"
                                          ? brand.primaryColor
                                          : brand.neutralColor,
                                    },
                                  },
                                  u.role,
                                ),
                              ),
                              /* Status */
                              React.createElement(
                                "td",
                                { style: tdStyle },
                                locked
                                  ? React.createElement(
                                      "div",
                                      {
                                        style: {
                                          display: "flex",
                                          flexDirection: "column",
                                          gap: "2px",
                                        },
                                      },
                                      React.createElement(
                                        "span",
                                        {
                                          style: {
                                            display: "inline-flex",
                                            alignItems: "center",
                                            gap: "4px",
                                            padding: "2px 8px",
                                            borderRadius: "0.375rem",
                                            fontSize: "0.75rem",
                                            fontWeight: 500,
                                            backgroundColor: tint("#b45309", 0.1),
                                            color: "#b45309",
                                            width: "fit-content",
                                          },
                                        },
                                        React.createElement(Icons.AlertCircle, {
                                          size: 12,
                                          "aria-hidden": true,
                                        }),
                                        "Locked",
                                      ),
                                      React.createElement(
                                        "span",
                                        {
                                          className: "text-xs",
                                          style: { color: brand.neutralColor },
                                        },
                                        "Unlocks at " + formatTime(u.locked_until) + " UTC",
                                      ),
                                    )
                                  : React.createElement(
                                      "span",
                                      {
                                        style: {
                                          display: "inline-flex",
                                          alignItems: "center",
                                          gap: "4px",
                                          padding: "2px 8px",
                                          borderRadius: "0.375rem",
                                          fontSize: "0.75rem",
                                          fontWeight: 500,
                                          backgroundColor: tint(brand.accentColor, 0.1),
                                          color: brand.accentColor,
                                        },
                                      },
                                      React.createElement(Icons.CheckCircle, {
                                        size: 12,
                                        "aria-hidden": true,
                                      }),
                                      "Active",
                                    ),
                              ),
                              /* Failed logins */
                              React.createElement(
                                "td",
                                {
                                  style: Object.assign({}, numStyle, {
                                    color:
                                      u.failed_login_count > 0 ? "#b45309" : brand.neutralColor,
                                    fontWeight: u.failed_login_count >= 3 ? 600 : 400,
                                  }),
                                },
                                String(u.failed_login_count),
                              ),
                              /* Created */
                              React.createElement(
                                "td",
                                { style: Object.assign({}, tdStyle, { color: brand.neutralColor }) },
                                formatDate(u.created_at),
                              ),
                              /* Last updated */
                              React.createElement(
                                "td",
                                { style: Object.assign({}, tdStyle, { color: brand.neutralColor }) },
                                formatDate(u.updated_at),
                              ),
                            );
                          }),
                        ),
                      ),
                    ),
                  ),
            ),
  );
}