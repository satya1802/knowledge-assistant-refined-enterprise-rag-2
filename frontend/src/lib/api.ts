/// <reference types="vite/client" />
// Without the reference above, `import.meta.env` is not typed and `tsc --noEmit` fails --
// which `vite build` does not catch, because it tree-shakes this module out when no screen
// imports it yet.
//
// Where the generated API lives.
//
// Set at build time: the platform bakes the deployed API URL into the frontend build. The
// fallback is the local backend so a bare `npm run dev` still points somewhere real.
//
// The generated screens do NOT use this yet -- they render seeded sample data, exactly as
// they were approved. This is the seam to replace that with real calls, one screen at a time.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * Error thrown by `apiFetch` when the response is not ok. Carries the HTTP
 * status code so calling code can branch on specific codes (409 conflict,
 * 403 forbidden, etc.) rather than parsing a string.
 */
export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw new ApiError(
      `${init?.method ?? "GET"} ${path} failed: ${response.status}`,
      response.status,
      body,
    );
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/**
 * Upload a file as `multipart/form-data`. Unlike `apiFetch`, this does NOT set
 * a `Content-Type` header -- the browser must set it so the multipart boundary
 * is generated automatically. Credentials (session cookie) are included.
 *
 * On a non-ok response the parsed JSON body is carried on the thrown
 * `ApiError` so calling code can surface a server-provided message (e.g. a
 * 422 "file too large" detail).
 */
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw new ApiError(`POST ${path} failed: ${response.status}`, response.status, body);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
