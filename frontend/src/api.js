import { authHeaders, reconnectLocal } from "./lib/auth";

const toParams = (params) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  return q.toString();
};

// Every launch mints a new token, so a 401 almost always means this tab holds
// the previous run's token (or none). Say how to recover instead of "401".
const AUTH_HELP =
  "This tab is not signed in to the running server. Each launch creates a new access token: " +
  "open the \u201cOpen SpendSlicer\u201d link printed in the terminal.";
const authError = () => Object.assign(new Error(AUTH_HELP), { auth: true });

const fetchWithAuth = async (url, options = {}) => {
  const request = () => fetch(url, {
    ...options,
    headers: { ...options.headers, ...authHeaders() },
  });
  let res = await request();
  if (res.status === 401 && await reconnectLocal()) res = await request();
  return res;
};

const getJson = async (path, params = {}, opts = {}) => {
  // The backend's persistent cache saves CE calls. Always reach it so a
  // changed credential helper or expired session cannot reuse old-account data.
  const qs = toParams(params);
  try {
    const res = await fetchWithAuth(`${path}${qs ? `?${qs}` : ""}`, {
      signal: opts.signal,
      headers: authHeaders(),
    });
    if (res.status === 401) throw authError();
    if (!res.ok) {
      let message = `Request failed: ${res.status}`;
      try { const body = await res.json(); message = body.detail || body.error || message; } catch { /* non-JSON error */ }
      throw Object.assign(new Error(message), { status: res.status });
    }
    const data = await res.json();
    // Sanitize header-derived numbers: a malformed header (proxy mangling,
    // "0,01") would yield NaN, which then poisons the session cost meter
    // permanently (NaN propagates through every later accumulation).
    const finite = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
    // Backend ctx builders report failures as HTTP 200 + {error: "..."} —
    // surface that instead of rendering zeroed figures as if they were real.
    const backendError = data && typeof data === "object" && typeof data.error === "string" && data.error
      ? data.error
      : null;
    const meta = {
      ceCalls: finite(res.headers.get("X-CE-Calls-Spent") || 0),
      ceCostUsd: finite(res.headers.get("X-CE-Estimated-Cost-USD") || 0),
      fromCache: null,
      backendError,
    };
    return { data, meta };
  } catch (err) {
    if (err?.name === "AbortError" || err?.auth || (err?.status >= 400 && err.status < 500)) throw err;
    throw err;
  }
};

export const api = {
  context: (profile, period, opts) => getJson("/api/ui/context", { profile, period }, opts),
  summary: (profile, period, opts) => getJson("/api/cost/summary/data", { profile, period }, opts),
  services: (profile, period, limit = 0, opts) =>
    getJson("/api/cost/services/data", { profile, period, limit }, opts),
  trend: (profile, period, opts) => getJson("/api/cost/trend/data", { profile, period }, opts),
  servicesComposition: (profile, period, opts) =>
    getJson("/api/cost/services/composition/data", { profile, period }, opts),
  resources: (profile, period, region = "all", service = "", limit = 0, opts) =>
    getJson("/api/resources/data", { profile, period, region, service, limit }, opts),
  resourcesTop: (profile, period, region = "all", limit = 10, opts) =>
    getJson("/api/resources/top/data", { profile, period, region, limit }, opts),
  audit: (profile, region = "all", opts) =>
    getJson("/api/audit/summary/data", { profile, region }, opts),
  budgets: (profile, opts) => getJson("/api/budgets/data", { profile }, opts),
  downloadExport: async (profile, period, fmt, name = "") => {
    const qs = toParams({ profile, period, fmt, name });
    const res = await fetchWithAuth(`/api/export/download?${qs}`);
    if (res.status === 401) throw authError();
    if (!res.ok) {
      let msg = `Export failed: ${res.status}`;
      try {
        const err = await res.json();
        if (err?.error) msg = err.error;
      } catch (_) {}
      throw new Error(msg);
    }
    const blob = await res.blob();
    const cd = res.headers.get("content-disposition") || "";
    const m = cd.match(/filename="?([^"]+)"?/i);
    const filename = m?.[1] || `spendslicer_${Date.now()}.${fmt}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return { filename };
  },
  runExport: async (profile, period, fmt, outputDir = "./exports") => {
    const qs = toParams({ profile, period, fmt, output_dir: outputDir });
    const res = await fetchWithAuth(`/api/export/run?${qs}`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (res.status === 401) throw authError();
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    return res.json();
  },
};
