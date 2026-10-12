/**
 * Shared-secret token plumbing for the API client.
 *
 * The backend accepts a token on every money-spending route via the
 * `X-SpendSlicer-Token` header or a `?token=` query parameter.
 *
 * Both launchers mint a random token per run or preserve a configured token.
 * The desktop hands `/app?token=...` to its webview; the web launcher prints
 * the protected link in the terminal. That closes a hole the
 * loopback bind alone does not — the server's CSRF check only guards
 * state-changing methods, so any page in the user's browser could otherwise
 * fire cross-origin GETs at the local port and spend real Cost Explorer money.
 * (CORS stops it reading the reply; it does not stop the request.)
 *
 * The token is captured once on load, kept in sessionStorage so a reload
 * inside the app window keeps working, then stripped from the visible URL so
 * it does not linger in history or in any copied link.
 */

const STORAGE_KEY = "spendslicer.token";

const readStored = () => {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || "";
  } catch {
    // Private mode / blocked storage: fall back to the in-memory value.
    return "";
  }
};

const captureFromUrl = () => {
  let found = "";
  try {
    const url = new URL(window.location.href);
    found = url.searchParams.get("token") || "";
    if (found) {
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    }
  } catch {
    /* non-browser context (tests) — nothing to capture */
  }
  return found;
};

let token = "";
if (typeof window !== "undefined") {
  token = captureFromUrl() || readStored();
  if (token) {
    try {
      sessionStorage.setItem(STORAGE_KEY, token);
    } catch {
      /* keep the in-memory copy */
    }
  }
}

/** Headers to merge into every API request. Empty when no token is in play. */
export const authHeaders = () => (token ? { "X-SpendSlicer-Token": token } : {});

let reconnecting = null;

/** Share one local-browser handshake across simultaneous expired requests. */
export const reconnectLocal = () => {
  if (!reconnecting) {
    reconnecting = (async () => {
      try {
        // A foreign website cannot send this header without a CORS preflight.
        // The backend also checks the browser's own Sec-Fetch-Site header.
        const res = await fetch("/api/auth/local", {
          headers: { "X-SpendSlicer-Local-UI": "1" },
          cache: "no-store",
        });
        if (!res.ok) return false;
        const data = await res.json();
        if (typeof data.token !== "string" || !data.token) return false;
        token = data.token;
        try { sessionStorage.setItem(STORAGE_KEY, token); } catch { /* in-memory fallback */ }
        return true;
      } catch {
        return false;
      } finally {
        reconnecting = null;
      }
    })();
  }
  return reconnecting;
};
