import { describe, it, expect, vi, beforeEach } from "vitest";

// Auth storage in the node test environment.
const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  key: (i) => [...store.keys()][i] ?? null,
  get length() { return store.size; },
};

const jsonResponse = (body) => ({
  ok: true,
  status: 200,
  headers: { get: () => "0" },
  json: async () => body,
});

describe("getJson backend-error handling", () => {
  beforeEach(() => { store.clear(); vi.restoreAllMocks(); });

  it("exposes data.error as meta.backendError and does not cache it", async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ error: "ExpiredToken: please re-auth", total_mtd: 0 }))
      .mockResolvedValueOnce(jsonResponse({ total_mtd: 42 }));
    const { api } = await import("./api");

    const first = await api.summary("default", "mtd");
    expect(first.meta.backendError).toBe("ExpiredToken: please re-auth");

    // Second call must NOT be served from cache (error payload was not cached).
    const second = await api.summary("default", "mtd");
    expect(second.data.total_mtd).toBe(42);
    expect(second.meta.backendError).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it("explains a 401 and does not hide it behind stale cache", async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ total_mtd: 7 }))
      .mockResolvedValueOnce({ ok: false, status: 401, headers: { get: () => "0" } })
      .mockResolvedValueOnce({ ok: false, status: 403 });
    const { api } = await import("./api");
    await api.summary("q", "mtd");
    // Credentials must be checked even just after a successful response.
    await expect(api.summary("q", "mtd")).rejects.toThrow(/link printed in the terminal/);
  });

  it("revalidates even fresh data against current server credentials", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ total_mtd: 7 }));
    const { api } = await import("./api");
    await api.summary("p", "mtd");
    const again = await api.summary("p", "mtd");
    expect(again.data.total_mtd).toBe(7);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it("does not cache profile detection, and invalidates figures after config changes", async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ profiles: ["prod"], config_revision: "one" }))
      .mockResolvedValueOnce(jsonResponse({ total_mtd: 7 }))
      .mockResolvedValueOnce(jsonResponse({ profiles: ["prod", "new"], config_revision: "two" }))
      .mockResolvedValueOnce(jsonResponse({ total_mtd: 99 }));
    const { api } = await import("./api");
    await api.context("prod", "mtd");
    await api.summary("prod", "mtd");
    const changed = await api.context("prod", "mtd");
    expect(changed.data.profiles).toContain("new");
    expect((await api.summary("prod", "mtd")).data.total_mtd).toBe(99);
    expect(globalThis.fetch).toHaveBeenCalledTimes(4);
  });

  it("surfaces credential errors instead of silently serving an old account's cache", async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce(jsonResponse({ total_mtd: 7 }))
      .mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({ detail: "AWS SSO session expired. Run aws sso login." }) });
    const { api } = await import("./api");
    await api.summary("expired", "mtd");
    await expect(api.summary("expired", "mtd")).rejects.toThrow(/aws sso login/);
  });

  it("reconnects a bare dashboard and loads the account choices", async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce(jsonResponse({ token: "new-run-token" }))
      .mockResolvedValueOnce(jsonResponse({ profiles: ["default", "prod"], profile_choices: [{ profile: "prod", label: "Production" }] }))
      .mockResolvedValueOnce(jsonResponse({ total_mtd: 42 }));
    const { api } = await import("./api");
    const context = await api.context("default", "mtd");
    expect(context.data.profiles).toContain("prod");
    expect(globalThis.fetch.mock.calls[1][0]).toBe("/api/auth/local");
    expect(globalThis.fetch.mock.calls[1][1].headers).toEqual({ "X-SpendSlicer-Local-UI": "1" });
    expect(globalThis.fetch.mock.calls[2][1].headers["X-SpendSlicer-Token"]).toBe("new-run-token");
    const switched = await api.summary("prod", "mtd");
    expect(switched.data.total_mtd).toBe(42);
    expect(globalThis.fetch.mock.calls[3][0]).toContain("profile=prod");
  });

  it("stops after one retry if reconnection still receives 401", async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce(jsonResponse({ token: "expired-again" }))
      .mockResolvedValueOnce({ ok: false, status: 401 });
    const { api } = await import("./api");
    await expect(api.context("other", "mtd")).rejects.toThrow(/link printed in the terminal/);
    expect(globalThis.fetch).toHaveBeenCalledTimes(3);
  });
});
