// @ts-nocheck -- generated from the approved design under its JS runtime contract; not hand-written TypeScript.
/* eslint-disable @typescript-eslint/no-unused-vars */
import React from "react";

import * as UI from "@/lib/ui";
import { Icons } from "@/lib/icons";
import { brand } from "@/lib/brand";
import { useNavigate } from "@/lib/navigate";

const { Search, Check, X, User, Settings, Bell, FileText, AlertCircle, CheckCircle } = Icons;

const SEED_USERS = [
  { id: 1, email: "satya.ganaraju@quorq.ai", password: "admin@123", role: "Administrator", name: "Satya Ganaraju" },
  { id: 2, email: "priya.sharma@quorq.ai", password: "quorq2026", role: "Regular User", name: "Priya Sharma" },
  { id: 3, email: "arjun.mehta@quorq.ai", password: "arjun!kb", role: "Regular User", name: "Arjun Mehta" },
];

const LOCKOUT_THRESHOLD = 5;
const LOCKOUT_MINUTES = 15;

export default function Screen() {
  const navigate = useNavigate();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [status, setStatus] = React.useState("idle"); // idle | loading | error | locked | success
  const [errorMessage, setErrorMessage] = React.useState("");
  const [failedAttempts, setFailedAttempts] = React.useState(0);
  const [lockedUntil, setLockedUntil] = React.useState(null);
  const [countdown, setCountdown] = React.useState(null);
  const [lockedEmail, setLockedEmail] = React.useState("");
  const [rememberEmail, setRememberEmail] = React.useState(false);
  const [lastFailedEmail, setLastFailedEmail] = React.useState("");

  // Countdown timer for lockout
  React.useEffect(() => {
    if (status !== "locked" || !lockedUntil) return;
    function tick() {
      const remaining = Math.max(0, lockedUntil - Date.now());
      if (remaining <= 0) {
        setStatus("idle");
        setFailedAttempts(0);
        setLockedUntil(null);
        setLockedEmail("");
        setCountdown(null);
        return;
      }
      const mins = Math.floor(remaining / 60000);
      const secs = Math.floor((remaining % 60000) / 1000);
      setCountdown(String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0"));
    }
    tick();
    const interval = setInterval(tick, 1000);
    return function () { clearInterval(interval); };
  }, [status, lockedUntil]);

  // Respect reduced motion
  const prefersReducedMotion = React.useMemo(function () {
    return typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  function handleSubmit(e) {
    e.preventDefault();

    // If already locked for this email, block submission
    if (lockedEmail && email.toLowerCase() === lockedEmail.toLowerCase() && lockedUntil && Date.now() < lockedUntil) {
      setStatus("locked");
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    // Simulate async auth check
    setTimeout(function () {
      const user = SEED_USERS.find(function (u) {
        return u.email.toLowerCase() === email.trim().toLowerCase() && u.password === password;
      });

      if (user) {
        // Clear any previous failed attempts for this email
        setFailedAttempts(0);
        setLastFailedEmail("");
        setStatus("success");
        // Navigate based on role after brief confirmation
        setTimeout(function () {
          if (user.role === "Administrator") {
            navigate("knowledge-base");
          } else {
            navigate("chat");
          }
        }, 600);
      } else {
        const newFailedCount = failedAttempts + 1;
        setFailedAttempts(newFailedCount);
        setLastFailedEmail(email.trim().toLowerCase());

        if (newFailedCount >= LOCKOUT_THRESHOLD) {
          setLockedEmail(email.trim());
          setLockedUntil(Date.now() + LOCKOUT_MINUTES * 60 * 1000);
          setStatus("locked");
          setErrorMessage("");
        } else {
          setStatus("error");
          setErrorMessage(
            "Email or password is incorrect. " +
            (LOCKOUT_THRESHOLD - newFailedCount) +
            " attempt" +
            ((LOCKOUT_THRESHOLD - newFailedCount) === 1 ? "" : "s") +
            " remaining before this account is temporarily locked."
          );
        }
      }
    }, 750);
  }

  function handleEmailChange(e) {
    setEmail(e.target.value);
    // Reset error state when user starts editing again
    if (status === "error") setStatus("idle");
  }

  function handlePasswordChange(e) {
    setPassword(e.target.value);
    if (status === "error") setStatus("idle");
  }

  function fillAdminCreds() {
    setEmail("satya.ganaraju@quorq.ai");
    setPassword("admin@123");
    setStatus("idle");
    setErrorMessage("");
  }

  const remainingAttempts = LOCKOUT_THRESHOLD - failedAttempts;
  const isAdminEmail = email.trim().toLowerCase() === "satya.ganaraju@quorq.ai";

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8" style={{ backgroundColor: brand.backgroundColor, fontFamily: brand.fontBody }}>
      <div className="w-full max-w-md">
        {/* Brand header */}
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-12 h-12 rounded-lg mb-4"
            style={{ backgroundColor: brand.primaryColor, borderRadius: brand.radius }}
            aria-hidden="true"
          >
            <Icons.FileText style={{ color: "#ffffff", width: 24, height: 24 }} />
          </div>
          <h1
            className="text-2xl font-semibold tracking-tight"
            style={{ color: "#0f172a", fontFamily: brand.fontHeading }}
          >
            Knowledge Assistant
          </h1>
          <p className="text-sm mt-1.5" style={{ color: brand.neutralColor }}>
            Enterprise RAG Console — sign in to continue
          </p>
        </div>

        {/* Login card */}
        <div
          className="bg-white shadow-sm border"
          style={{
            borderRadius: brand.radius,
            borderColor: "#e2e8f0",
            transition: prefersReducedMotion ? "none" : "box-shadow 0.2s ease",
          }}
        >
          {/* Status banner area */}
          {status === "locked" && (
            <div
              className="flex items-start gap-3 px-5 pt-4 pb-3 border-b"
              style={{
                backgroundColor: "#fef2f2",
                borderColor: "#fecaca",
                animation: prefersReducedMotion ? "none" : "kaSlideIn 0.2s ease",
              }}
              role="alert"
              aria-live="assertive"
            >
              <Icons.AlertCircle
                style={{ color: "#dc2626", width: 20, height: 20, flexShrink: 0, marginTop: 1 }}
                aria-hidden="true"
              />
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: "#991b1b" }}>
                  Account temporarily locked
                </p>
                <p className="text-xs mt-0.5" style={{ color: "#7f1d1d" }}>
                  Too many failed attempts for{" "}
                  <span style={{ fontWeight: 600 }}>{lockedEmail}</span>. Try again in{" "}
                  <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                    {countdown || "15:00"}
                  </span>
                  , or contact your administrator.
                </p>
              </div>
            </div>
          )}

          {status === "success" && (
            <div
              className="flex items-center gap-3 px-5 pt-4 pb-3 border-b"
              style={{
                backgroundColor: "#ecfdf5",
                borderColor: "#a7f3d0",
                animation: prefersReducedMotion ? "none" : "kaSlideIn 0.2s ease",
              }}
              role="status"
              aria-live="polite"
            >
              <Icons.CheckCircle
                style={{ color: brand.accentColor, width: 20, height: 20, flexShrink: 0 }}
                aria-hidden="true"
              />
              <p className="text-sm font-medium" style={{ color: "#065f46" }}>
                Authenticated — redirecting to your workspace…
              </p>
            </div>
          )}

          {status === "error" && (
            <div
              className="flex items-start gap-3 px-5 pt-4 pb-3 border-b"
              style={{
                backgroundColor: "#fef2f2",
                borderColor: "#fecaca",
                animation: prefersReducedMotion ? "none" : "kaSlideIn 0.2s ease",
              }}
              role="alert"
              aria-live="assertive"
            >
              <Icons.AlertCircle
                style={{ color: "#dc2626", width: 20, height: 20, flexShrink: 0, marginTop: 1 }}
                aria-hidden="true"
              />
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: "#991b1b" }}>
                  Sign-in failed
                </p>
                <p className="text-xs mt-0.5" style={{ color: "#7f1d1d" }}>
                  {errorMessage}
                </p>
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="px-5 py-5" noValidate>
            <div className="space-y-4">
              {/* Email field */}
              <div>
                <label
                  htmlFor="login-email"
                  className="block text-xs font-semibold mb-1.5"
                  style={{ color: "#334155", textTransform: "uppercase", letterSpacing: "0.04em" }}
                >
                  Email Address
                </label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={handleEmailChange}
                  disabled={status === "loading" || status === "locked"}
                  className="w-full px-3 py-2 text-sm border outline-none transition-colors"
                  style={{
                    borderRadius: brand.radius,
                    borderColor: status === "error" ? "#fca5a5" : "#cbd5e1",
                    fontFamily: brand.fontBody,
                  }}
                  aria-required="true"
                  aria-invalid={status === "error"}
                  aria-describedby={status === "error" ? "login-error-desc" : undefined}
                  placeholder="you@company.com"
                />
              </div>

              {/* Password field */}
              <div>
                <label
                  htmlFor="login-password"
                  className="block text-xs font-semibold mb-1.5"
                  style={{ color: "#334155", textTransform: "uppercase", letterSpacing: "0.04em" }}
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={handlePasswordChange}
                    disabled={status === "loading" || status === "locked"}
                    className="w-full px-3 py-2 pr-10 text-sm border outline-none transition-colors"
                    style={{
                      borderRadius: brand.radius,
                      borderColor: status === "error" ? "#fca5a5" : "#cbd5e1",
                      fontFamily: brand.fontBody,
                    }}
                    aria-required="true"
                    aria-invalid={status === "error"}
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={function () { setShowPassword(function (v) { return !v; }); }}
                    disabled={status === "loading" || status === "locked"}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded"
                    style={{ color: brand.neutralColor }}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <Icons.X style={{ width: 16, height: 16 }} aria-hidden="true" />
                    ) : (
                      <Icons.Search style={{ width: 16, height: 16 }} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              {/* Remember email checkbox */}
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    id="login-remember"
                    type="checkbox"
                    checked={rememberEmail}
                    onChange={function (e) { setRememberEmail(e.target.checked); }}
                    disabled={status === "loading" || status === "locked"}
                    className="w-4 h-4"
                    style={{ accentColor: brand.primaryColor }}
                  />
                  <span className="text-xs" style={{ color: brand.neutralColor }}>
                    Remember my email on this device
                  </span>
                </label>
              </div>

              {/* Submit button */}
              <button
                type="submit"
                disabled={status === "loading" || status === "locked" || status === "success"}
                className="w-full py-2.5 text-sm font-semibold text-white transition-opacity"
                style={{
                  backgroundColor: brand.primaryColor,
                  borderRadius: brand.radius,
                  opacity: (status === "loading" || status === "locked" || status === "success") ? 0.6 : 1,
                  fontFamily: brand.fontBody,
                }}
                aria-busy={status === "loading"}
              >
                {status === "loading" ? (
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="inline-block w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full"
                      style={{
                        animation: prefersReducedMotion ? "none" : "kaSpin 0.6s linear infinite",
                      }}
                      aria-hidden="true"
                    />
                    Verifying credentials…
                  </span>
                ) : status === "success" ? (
                  <span className="inline-flex items-center gap-2">
                    <Icons.Check style={{ width: 16, height: 16 }} aria-hidden="true" />
                    Signed in
                  </span>
                ) : (
                  "Sign in"
                )}
              </button>
            </div>
          </form>

          {/* Footer info */}
          <div className="px-5 pb-4 pt-1">
            <div className="flex items-center gap-2 pt-3 border-t" style={{ borderColor: "#f1f5f9" }}>
              <Icons.Settings style={{ width: 14, height: 14, color: brand.neutralColor }} aria-hidden="true" />
              <p className="text-xs" style={{ color: brand.neutralColor }}>
                Accounts are provisioned by your administrator. No self-registration.
              </p>
            </div>
          </div>
        </div>

        {/* Security note + admin hint */}
        <div className="mt-5 space-y-3">
          {/* Attempt indicator */}
          {failedAttempts > 0 && status === "idle" && lastFailedEmail === email.trim().toLowerCase() && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
              style={{
                backgroundColor: "#fffbeb",
                border: "1px solid #fde68a",
                color: "#92400e",
                animation: prefersReducedMotion ? "none" : "kaSlideIn 0.2s ease",
              }}
              role="status"
            >
              <Icons.AlertCircle style={{ width: 14, height: 14, flexShrink: 0 }} aria-hidden="true" />
              <span style={{ fontVariantNumeric: "tabular-nums" }}>
                {remainingAttempts} of {LOCKOUT_THRESHOLD} attempts remaining before lockout.
              </span>
            </div>
          )}

          {/* Lockout policy info */}
          <div
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg"
            style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0" }}
          >
            <Icons.Bell style={{ width: 14, height: 14, color: brand.neutralColor, flexShrink: 0 }} aria-hidden="true" />
            <p className="text-xs leading-relaxed" style={{ color: brand.neutralColor }}>
              After {LOCKOUT_THRESHOLD} failed attempts, the account is locked for{" "}
              <span style={{ fontWeight: 600 }}>{LOCKOUT_MINUTES} minutes</span> to protect against brute-force access.
            </p>
          </div>

          {/* Admin quick-fill for first-run convenience */}
          <div
            className="flex items-center justify-between px-3 py-2.5 rounded-lg"
            style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0" }}
          >
            <div className="flex items-center gap-2">
              <Icons.User style={{ width: 14, height: 14, color: brand.neutralColor, flexShrink: 0 }} aria-hidden="true" />
              <p className="text-xs" style={{ color: brand.neutralColor }}>
                First-time admin login? Use the seeded credentials.
              </p>
            </div>
            <button
              type="button"
              onClick={fillAdminCreds}
              disabled={status === "loading" || status === "locked"}
              className="text-xs font-semibold px-2.5 py-1 rounded transition-colors"
              style={{
                color: brand.primaryColor,
                backgroundColor: "#eff6ff",
              }}
            >
              Fill admin login
            </button>
          </div>
        </div>

        {/* Copyright */}
        <p className="text-center text-xs mt-6" style={{ color: brand.neutralColor }}>
          Knowledge Assistant · QuorQ AI · Gemini-powered RAG
        </p>
      </div>

      <style>{`
        @keyframes kaSpin {
          to { transform: rotate(360deg); }
        }
        @keyframes kaSlideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        input:focus-visible, button:focus-visible {
          outline: 2px solid ${brand.primaryColor};
          outline-offset: 1px;
        }
        input:focus {
          border-color: ${brand.primaryColor};
        }
        button:focus-visible {
          outline: 2px solid ${brand.primaryColor};
          outline-offset: 2px;
        }
      `}</style>
    </div>
  );
}
