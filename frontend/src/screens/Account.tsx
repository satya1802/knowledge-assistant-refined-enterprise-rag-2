// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Button, Card, CardHeader, CardContent, Input, Label, Badge, Table, THead, TBody, TR, TH, TD, Avatar } = UI;
const { X, ChevronRight, User, Users, Settings, Home, FileText, AlertCircle, CheckCircle } = Icons;

export default function Screen() {
  const navigate = useNavigate();
  // ── Current user (would come from GET /auth/me in production) ──────────────
  const currentUser = {
    id: "a1f3c2e0-7b4d-4e2a-9c1f-6d8e0b2a5f31",
    email: "satya.ganaraju@quorq.ai",
    role: "Administrator",
    created_at: "2026-09-28T10:15:00Z",
    last_login: "2026-10-15T08:42:17Z",
  };

  // ── Brand ──────────────────────────────────────────────────────────────────
  const fontStack = brand.fontBody;
  const headingStack = brand.fontHeading;

  // ── State ──────────────────────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [errors, setErrors] = React.useState({});
  const [submitState, setSubmitState] = React.useState("idle"); // idle | success | error
  const [submitMessage, setSubmitMessage] = React.useState("");
  const [showCurrent, setShowCurrent] = React.useState(false);
  const [showNew, setShowNew] = React.useState(false);
  const [showConfirm, setShowConfirm] = React.useState(false);
  const [loggingOut, setLoggingOut] = React.useState(false);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function validate() {
    const e = {};
    if (!currentPassword) {
      e.current = "Enter your current password to continue.";
    }
    if (!newPassword) {
      e.new = "Choose a new password.";
    } else if (newPassword.length < 8) {
      e.new = "New password must be at least 8 characters.";
    } else if (newPassword === currentPassword) {
      e.new = "New password must differ from your current one.";
    }
    if (!confirmPassword) {
      e.confirm = "Re-enter the new password to confirm.";
    } else if (confirmPassword !== newPassword) {
      e.confirm = "The two passwords do not match.";
    }
    return e;
  }

  function handleSubmit(ev) {
    ev.preventDefault();
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) {
      setSubmitState("error");
      setSubmitMessage("Please correct the fields below before submitting.");
      return;
    }
    // Simulate the POST /auth/change-password round-trip
    // AC-013: current password matches → hash replaced → success
    // AC-014: current password incorrect → error
    setSubmitState("idle");
    setSubmitMessage("");

    // Simulate a wrong-current-password scenario for realism is not needed;
    // in the prototype we assume the correct password was entered.
    setTimeout(function() {
      setSubmitState("success");
      setSubmitMessage("Password updated. Use your new password the next time you sign in.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    }, 350);
  }

  function handleLogout() {
    setLoggingOut(true);
    // POST /auth/logout invalidates the session server-side (AC-007, AC-008)
    setTimeout(function() {
      navigate("login");
    }, 400);
  }

  function clearFieldError(field) {
    if (errors[field]) {
      setErrors(function(prev) {
        var next = {};
        Object.keys(prev).forEach(function(k) { next[k] = prev[k]; });
        delete next[field];
        return next;
      });
    }
  }

  // ── Password strength (simple heuristic for the indicator) ─────────────────
  function passwordStrength(pw) {
    if (!pw) return 0;
    var score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    return Math.min(score, 4);
  }

  var strength = passwordStrength(newPassword);
  var strengthLabels = ["", "Weak", "Fair", "Good", "Strong"];
  var strengthColors = [
    "transparent",
    "#dc2626",
    "#d97706",
    brand.accentColor,
    brand.primaryColor,
  ];

  // ── Style objects ──────────────────────────────────────────────────────────
  const pageStyle = {
    fontFamily: fontStack,
    backgroundColor: brand.backgroundColor,
    color: "#0f172a",
  };

  const cardBase = {
    borderRadius: brand.radius,
    backgroundColor: "#ffffff",
    border: "1px solid #e2e8f0",
  };

  const labelStyle = {
    fontSize: "0.75rem",
    fontWeight: 600,
    color: "#334155",
    letterSpacing: "0.01em",
    display: "block",
    marginBottom: "0.375rem",
  };

  const inputBase = {
    fontFamily: fontStack,
    fontSize: "0.875rem",
    padding: "0.5rem 0.75rem",
    borderRadius: brand.radius,
    border: "1px solid #cbd5e1",
    width: "100%",
    outline: "none",
    transition: "border-color 0.15s ease, box-shadow 0.15s ease",
  };

  function inputWithError(hasError) {
    return Object.assign({}, inputBase, {
      borderColor: hasError ? "#dc2626" : "#cbd5e1",
    });
  }

  const errorTextStyle = {
    fontSize: "0.75rem",
    color: "#dc2626",
    marginTop: "0.25rem",
    lineHeight: 1.4,
  };

  // ── Inline input focus handler ─────────────────────────────────────────────
  function focusBorder(ev, isError) {
    if (isError) {
      ev.target.style.borderColor = "#dc2626";
      ev.target.style.boxShadow = "0 0 0 3px rgba(220,38,38,0.12)";
    } else {
      ev.target.style.borderColor = brand.primaryColor;
      ev.target.style.boxShadow = "0 0 0 3px rgba(29,78,216,0.12)";
    }
  }
  function blurBorder(ev, isError) {
    ev.target.style.boxShadow = "none";
    ev.target.style.borderColor = isError ? "#dc2626" : "#cbd5e1";
  }

  // ── Recent login attempts (sample data that looks real) ────────────────────
  const recentLogins = [
    { id: 1, email: currentUser.email, success: true, attempted_at: "2026-10-15T08:42:17Z", ip: "10.4.12.38" },
    { id: 2, email: currentUser.email, success: true, attempted_at: "2026-10-14T17:05:41Z", ip: "10.4.12.38" },
    { id: 3, email: currentUser.email, success: false, attempted_at: "2026-10-14T16:58:02Z", ip: "10.4.12.38" },
    { id: 4, email: currentUser.email, success: true, attempted_at: "2026-10-13T09:21:03Z", ip: "192.168.1.104" },
    { id: 5, email: currentUser.email, success: true, attempted_at: "2026-10-11T14:33:55Z", ip: "10.4.12.38" },
  ];

  function formatDate(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function formatDateTime(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      ", " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  function relativeTime(iso) {
    var now = new Date("2026-10-15T09:00:00Z");
    var then = new Date(iso);
    var diff = Math.round((now - then) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.round(diff / 60) + " min ago";
    if (diff < 86400) return Math.round(diff / 3600) + " hr ago";
    return Math.round(diff / 86400) + " days ago";
  }

  // ── Nav items for quick links ──────────────────────────────────────────────
  const quickLinks = [
    { label: "Knowledge Base", route: "knowledge-base", icon: Icons.FileText },
    { label: "Chat", route: "chat", icon: Icons.Home },
    { label: "User Management", route: "users", icon: Icons.Users },
    { label: "Settings", route: "settings", icon: Icons.Settings },
  ];

  return React.createElement("div", {
    style: pageStyle,
    className: "min-h-full",
  },

  // ── Heading ────────────────────────────────────────────────────────────────
  React.createElement("div", { className: "mb-6" },
    React.createElement("h1", {
      style: { fontFamily: headingStack, fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", margin: 0, letterSpacing: "-0.01em" },
    }, "Account"),
    React.createElement("p", {
      style: { fontSize: "0.875rem", color: brand.neutralColor, marginTop: "0.25rem", margin: 0 },
    }, "Your profile, password, and session controls."),
  ),

  // ── Two-column layout: profile + password ─────────────────────────────────
  React.createElement("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-4" },

    // ── Left: Profile card (spans 1) ────────────────────────────────────────
    React.createElement("div", { className: "lg:col-span-1" },
      React.createElement(Card, { style: cardBase, className: "overflow-hidden" },
        React.createElement(CardHeader, { style: { padding: "1rem 1.25rem", borderBottom: "1px solid #e2e8f0" } },
          React.createElement("h2", {
            style: { fontFamily: headingStack, fontSize: "0.875rem", fontWeight: 700, color: "#0f172a", margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" },
          }, "Profile"),
        ),
        React.createElement(CardContent, { style: { padding: "1.25rem" } },
          // Avatar + name
          React.createElement("div", { className: "flex items-center gap-3 mb-4" },
            React.createElement(Avatar, {
              style: {
                width: "3rem",
                height: "3rem",
                borderRadius: brand.radius,
                backgroundColor: brand.primaryColor,
                color: "#ffffff",
                fontSize: "1rem",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              },
            }, currentUser.email.charAt(0).toUpperCase()),
            React.createElement("div", null,
              React.createElement("div", {
                style: { fontSize: "0.9375rem", fontWeight: 600, color: "#0f172a", lineHeight: 1.3 },
              }, currentUser.email.split("@")[0].replace(/\./g, " ").replace(/\b\w/g, function(c) { return c.toUpperCase(); })),
              React.createElement("div", {
                style: { fontSize: "0.8125rem", color: brand.neutralColor, marginTop: "0.125rem" },
              }, currentUser.email),
            ),
          ),

          // Role badge
          React.createElement("div", { className: "mb-4" },
            React.createElement(Badge, {
              style: {
                backgroundColor: currentUser.role === "Administrator" ? "rgba(29,78,216,0.08)" : "rgba(5,150,105,0.08)",
                color: currentUser.role === "Administrator" ? brand.primaryColor : brand.accentColor,
                border: "1px solid " + (currentUser.role === "Administrator" ? "rgba(29,78,216,0.2)" : "rgba(5,150,105,0.2)"),
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "0.25rem 0.625rem",
                borderRadius: brand.radius,
              },
            }, currentUser.role === "Administrator" ? "Administrator" : "Regular User"),
          ),

          // Profile details
          React.createElement("div", { className: "space-y-3" },
            React.createElement("div", null,
              React.createElement("div", { style: { fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" } }, "User ID"),
              React.createElement("div", {
                style: { fontSize: "0.8125rem", color: "#334155", fontFamily: fontStack, fontVariantNumeric: "tabular-nums", wordBreak: "break-all" },
              }, currentUser.id),
            ),
            React.createElement("div", null,
              React.createElement("div", { style: { fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" } }, "Account created"),
              React.createElement("div", {
                style: { fontSize: "0.8125rem", color: "#334155", fontVariantNumeric: "tabular-nums" },
              }, formatDate(currentUser.created_at)),
            ),
            React.createElement("div", null,
              React.createElement("div", { style: { fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" } }, "Last sign-in"),
              React.createElement("div", {
                style: { fontSize: "0.8125rem", color: "#334155", fontVariantNumeric: "tabular-nums" },
              }, formatDateTime(currentUser.last_login) + " · " + relativeTime(currentUser.last_login)),
            ),
          ),
        ),

        // Logout action
        React.createElement("div", {
          style: { padding: "1rem 1.25rem", borderTop: "1px solid #e2e8f0" },
        },
          React.createElement(Button, {
            type: "button",
            onClick: handleLogout,
            disabled: loggingOut,
            "aria-label": "Log out of your account",
            style: {
              width: "100%",
              fontFamily: fontStack,
              fontSize: "0.875rem",
              fontWeight: 600,
              padding: "0.625rem 1rem",
              borderRadius: brand.radius,
              border: "1px solid #dc2626",
              backgroundColor: loggingOut ? "#fef2f2" : "#ffffff",
              color: "#dc2626",
              cursor: loggingOut ? "default" : "pointer",
              transition: "background-color 0.15s ease, color 0.15s ease",
            },
            onMouseEnter: function(e) { if (!loggingOut) { e.target.style.backgroundColor = "#dc2626"; e.target.style.color = "#ffffff"; } },
            onMouseLeave: function(e) { if (!loggingOut) { e.target.style.backgroundColor = "#ffffff"; e.target.style.color = "#dc2626"; } },
          },
            loggingOut ? "Signing out…" : "Log out",
          ),
        ),
      ),

      // Quick links card
      React.createElement(Card, {
        style: Object.assign({}, cardBase, { marginTop: "1rem" }),
      },
        React.createElement(CardHeader, { style: { padding: "1rem 1.25rem", borderBottom: "1px solid #e2e8f0" } },
          React.createElement("h2", {
            style: { fontFamily: headingStack, fontSize: "0.875rem", fontWeight: 700, color: "#0f172a", margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" },
          }, "Quick navigation"),
        ),
        React.createElement(CardContent, { style: { padding: "0.5rem 0" } },
          quickLinks.map(function(link) {
            return React.createElement("button", {
              key: link.route,
              type: "button",
              onClick: function() { navigate(link.route); },
              style: {
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "0.625rem",
                padding: "0.625rem 1.25rem",
                fontFamily: fontStack,
                fontSize: "0.875rem",
                color: "#334155",
                backgroundColor: "transparent",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                transition: "background-color 0.12s ease",
              },
              onMouseEnter: function(e) { e.target.style.backgroundColor = "#f1f5f9"; },
              onMouseLeave: function(e) { e.target.style.backgroundColor = "transparent"; },
            },
              React.createElement(link.icon, { size: 16, style: { color: brand.neutralColor }, "aria-hidden": true }),
              React.createElement("span", null, link.label),
              React.createElement(Icons.ChevronRight, { size: 14, style: { marginLeft: "auto", color: "#cbd5e1" }, "aria-hidden": true }),
            );
          }),
        ),
      ),
    ),

    // ── Right: Password change + recent activity (spans 2) ──────────────────
    React.createElement("div", { className: "lg:col-span-2 space-y-4" },

      // ── Change password card ──────────────────────────────────────────────
      React.createElement(Card, { style: cardBase },
        React.createElement(CardHeader, { style: { padding: "1rem 1.25rem", borderBottom: "1px solid #e2e8f0" } },
          React.createElement("h3", {
            style: { fontFamily: headingStack, fontSize: "1rem", fontWeight: 700, color: "#0f172a", margin: 0 },
          }, "Change password"),
          React.createElement("p", {
            style: { fontSize: "0.8125rem", color: brand.neutralColor, marginTop: "0.25rem" },
          }, "Use a password known only to you. After changing it, your old password will no longer work on any device."),
        ),
        React.createElement(CardContent, { style: { padding: "1.25rem" } },

          // Success / error banner
          submitState !== "idle" && React.createElement("div", {
            role: submitState === "error" ? "alert" : "status",
            "aria-live": "polite",
            style: {
              display: "flex",
              alignItems: "flex-start",
              gap: "0.5rem",
              padding: "0.75rem 1rem",
              borderRadius: brand.radius,
              marginBottom: "1rem",
              fontSize: "0.8125rem",
              lineHeight: 1.5,
              backgroundColor: submitState === "success" ? "rgba(5,150,105,0.06)" : "rgba(220,38,38,0.06)",
              border: "1px solid " + (submitState === "success" ? "rgba(5,150,105,0.2)" : "rgba(220,38,38,0.2)"),
              color: submitState === "success" ? "#065f46" : "#991b1b",
              animation: "fadeSlide 0.25s ease-out",
            },
          },
            submitState === "success"
              ? React.createElement(Icons.CheckCircle, { size: 16, style: { flexShrink: 0, marginTop: "0.0625rem", color: brand.accentColor }, "aria-hidden": true })
              : React.createElement(Icons.AlertCircle, { size: 16, style: { flexShrink: 0, marginTop: "0.0625rem", color: "#dc2626" }, "aria-hidden": true }),
            React.createElement("span", null, submitMessage),
          ),

          React.createElement("form", { onSubmit: handleSubmit, noValidate: true },
            React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4" },

              // Current password
              React.createElement("div", { className: "md:col-span-2" },
                React.createElement(Label, { htmlFor: "currentPassword", style: labelStyle }, "Current password"),
                React.createElement("div", { className: "relative" },
                  React.createElement(Input, {
                    id: "currentPassword",
                    name: "currentPassword",
                    type: showCurrent ? "text" : "password",
                    value: currentPassword,
                    onChange: function(e) { setCurrentPassword(e.target.value); clearFieldError("current"); setSubmitState("idle"); },
                    onFocus: function(e) { focusBorder(e, !!errors.current); },
                    onBlur: function(e) { blurBorder(e, !!errors.current); },
                    autoComplete: "current-password",
                    "aria-invalid": !!errors.current,
                    "aria-describedby": errors.current ? "currentPassword-error" : undefined,
                    style: inputWithError(!!errors.current),
                  }),
                  React.createElement("button", {
                    type: "button",
                    onClick: function() { setShowCurrent(!showCurrent); },
                    "aria-label": showCurrent ? "Hide current password" : "Show current password",
                    style: {
                      position: "absolute",
                      right: "0.5rem",
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "0.25rem",
                      color: brand.neutralColor,
                      fontSize: "0.6875rem",
                      fontWeight: 600,
                    },
                  }, showCurrent ? "Hide" : "Show"),
                ),
                errors.current && React.createElement("p", { id: "currentPassword-error", style: errorTextStyle }, errors.current),
              ),

              // New password
              React.createElement("div", null,
                React.createElement(Label, { htmlFor: "newPassword", style: labelStyle }, "New password"),
                React.createElement("div", { className: "relative" },
                  React.createElement(Input, {
                    id: "newPassword",
                    name: "newPassword",
                    type: showNew ? "text" : "password",
                    value: newPassword,
                    onChange: function(e) { setNewPassword(e.target.value); clearFieldError("new"); setSubmitState("idle"); },
                    onFocus: function(e) { focusBorder(e, !!errors.new); },
                    onBlur: function(e) { blurBorder(e, !!errors.new); },
                    autoComplete: "new-password",
                    "aria-invalid": !!errors.new,
                    "aria-describedby": errors.new ? "newPassword-error" : (newPassword ? "password-strength" : undefined),
                    style: inputWithError(!!errors.new),
                  }),
                  React.createElement("button", {
                    type: "button",
                    onClick: function() { setShowNew(!showNew); },
                    "aria-label": showNew ? "Hide new password" : "Show new password",
                    style: {
                      position: "absolute",
                      right: "0.5rem",
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "0.25rem",
                      color: brand.neutralColor,
                      fontSize: "0.6875rem",
                      fontWeight: 600,
                    },
                  }, showNew ? "Hide" : "Show"),
                ),
                errors.new
                  ? React.createElement("p", { id: "newPassword-error", style: errorTextStyle }, errors.new)
                  : newPassword && React.createElement("div", { id: "password-strength", className: "mt-2" },
                      React.createElement("div", { style: { display: "flex", gap: "0.25rem", marginBottom: "0.25rem" } },
                        [1,2,3,4].map(function(i) {
                          return React.createElement("div", {
                            key: i,
                            style: {
                              height: "0.25rem",
                              flex: 1,
                              borderRadius: "0.125rem",
                              backgroundColor: i <= strength ? strengthColors[strength] : "#e2e8f0",
                              transition: "background-color 0.2s ease",
                            },
                          });
                        }),
                      ),
                      React.createElement("span", {
                        style: { fontSize: "0.6875rem", fontWeight: 600, color: strength > 0 ? strengthColors[strength] : brand.neutralColor },
                      }, strengthLabels[strength] || " "),
                    ),
              ),

              // Confirm password
              React.createElement("div", null,
                React.createElement(Label, { htmlFor: "confirmPassword", style: labelStyle }, "Confirm new password"),
                React.createElement("div", { className: "relative" },
                  React.createElement(Input, {
                    id: "confirmPassword",
                    name: "confirmPassword",
                    type: showConfirm ? "text" : "password",
                    value: confirmPassword,
                    onChange: function(e) { setConfirmPassword(e.target.value); clearFieldError("confirm"); setSubmitState("idle"); },
                    onFocus: function(e) { focusBorder(e, !!errors.confirm); },
                    onBlur: function(e) { blurBorder(e, !!errors.confirm); },
                    autoComplete: "new-password",
                    "aria-invalid": !!errors.confirm,
                    "aria-describedby": errors.confirm ? "confirmPassword-error" : undefined,
                    style: inputWithError(!!errors.confirm),
                  }),
                  React.createElement("button", {
                    type: "button",
                    onClick: function() { setShowConfirm(!showConfirm); },
                    "aria-label": showConfirm ? "Hide confirm password" : "Show confirm password",
                    style: {
                      position: "absolute",
                      right: "0.5rem",
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "0.25rem",
                      color: brand.neutralColor,
                      fontSize: "0.6875rem",
                      fontWeight: 600,
                    },
                  }, showConfirm ? "Hide" : "Show"),
                ),
                errors.confirm && React.createElement("p", { id: "confirmPassword-error", style: errorTextStyle }, errors.confirm),
              ),
            ),

            // Password requirements hint
            React.createElement("div", {
              style: {
                marginTop: "1rem",
                padding: "0.75rem 1rem",
                borderRadius: brand.radius,
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                fontSize: "0.75rem",
                color: brand.neutralColor,
                lineHeight: 1.6,
              },
            },
              React.createElement("span", { style: { fontWeight: 600, color: "#334155" } }, "Password requirements: "),
              "at least 8 characters, a mix of letters and numbers recommended. Your new password must be different from the current one.",
            ),

            // Submit button
            React.createElement("div", { style: { marginTop: "1.25rem", display: "flex", justifyContent: "flex-end" } },
              React.createElement(Button, {
                type: "submit",
                style: {
                  fontFamily: fontStack,
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  padding: "0.625rem 1.5rem",
                  borderRadius: brand.radius,
                  backgroundColor: brand.primaryColor,
                  color: "#ffffff",
                  border: "1px solid " + brand.primaryColor,
                  cursor: "pointer",
                  transition: "background-color 0.15s ease",
                },
                onMouseEnter: function(e) { e.target.style.backgroundColor = "#1741b5"; },
                onMouseLeave: function(e) { e.target.style.backgroundColor = brand.primaryColor; },
              }, "Update password"),
            ),
          ),
        ),
      ),

      // ── Recent login activity ─────────────────────────────────────────────
      React.createElement(Card, { style: cardBase },
        React.createElement(CardHeader, { style: { padding: "1rem 1.25rem", borderBottom: "1px solid #e2e8f0" } },
          React.createElement("h2", {
            style: { fontFamily: headingStack, fontSize: "0.875rem", fontWeight: 700, color: "#0f172a", margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" },
          }, "Recent sign-in activity"),
        ),
        React.createElement(CardContent, { style: { padding: 0 } },
          React.createElement(Table, { style: { width: "100%", borderCollapse: "collapse", fontVariantNumeric: "tabular-nums" } },
            React.createElement(THead, null,
              React.createElement(TR, { style: { borderBottom: "1px solid #e2e8f0" } },
                React.createElement(TH, { style: { textAlign: "left", fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", padding: "0.625rem 1.25rem" } }, "Result"),
                React.createElement(TH, { style: { textAlign: "left", fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", padding: "0.625rem 1.25rem" } }, "Time"),
                React.createElement(TH, { style: { textAlign: "left", fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", padding: "0.625rem 1.25rem" } }, "IP address"),
                React.createElement(TH, { style: { textAlign: "right", fontSize: "0.6875rem", fontWeight: 600, color: brand.neutralColor, textTransform: "uppercase", letterSpacing: "0.05em", padding: "0.625rem 1.25rem" } }, "Relative"),
              ),
            ),
            React.createElement(TBody, null,
              recentLogins.map(function(attempt) {
                return React.createElement(TR, {
                  key: attempt.id,
                  style: { borderBottom: "1px solid #f1f5f9", transition: "background-color 0.12s ease" },
                  onMouseEnter: function(e) { e.currentTarget.style.backgroundColor = "#f8fafc"; },
                  onMouseLeave: function(e) { e.currentTarget.style.backgroundColor = "transparent"; },
                },
                  React.createElement(TD, { style: { padding: "0.625rem 1.25rem", fontSize: "0.8125rem" } },
                    React.createElement("span", { style: { display: "inline-flex", alignItems: "center", gap: "0.375rem" } },
                      attempt.success
                        ? React.createElement(Icons.CheckCircle, { size: 14, style: { color: brand.accentColor }, "aria-hidden": true })
                        : React.createElement(Icons.X, { size: 14, style: { color: "#dc2626" }, "aria-hidden": true }),
                      React.createElement("span", {
                        style: {
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          color: attempt.success ? brand.accentColor : "#dc2626",
                        },
                      }, attempt.success ? "Success" : "Failed"),
                    ),
                  ),
                  React.createElement(TD, { style: { padding: "0.625rem 1.25rem", fontSize: "0.8125rem", color: "#334155" } }, formatDateTime(attempt.attempted_at)),
                  React.createElement(TD, { style: { padding: "0.625rem 1.25rem", fontSize: "0.8125rem", color: "#334155", fontFamily: fontStack } }, attempt.ip),
                  React.createElement(TD, { style: { padding: "0.625rem 1.25rem", fontSize: "0.75rem", color: brand.neutralColor, textAlign: "right" } }, relativeTime(attempt.attempted_at)),
                );
              }),
            ),
          ),
          React.createElement("div", {
            style: { padding: "0.625rem 1.25rem", fontSize: "0.75rem", color: brand.neutralColor, borderTop: "1px solid #f1f5f9" },
          }, "Showing last 5 sign-in attempts. Sessions are HTTP-only and invalidated on logout."),
        ),
      ),
    ),
  ),

  // ── Keyframes ──────────────────────────────────────────────────────────────
  React.createElement("style", null,
    "@keyframes fadeSlide { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }" +
    "@media (prefers-reduced-motion: reduce) { * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }"
  ),
  );
}
