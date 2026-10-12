import { describe, it, expect, vi, beforeEach } from "vitest";

// In-memory localStorage for the swrCache dependency (vitest runs in node env).
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
    // Past the fresh TTL but inside stale-while-revalidate: a network failure
    // here would fall back to the cached copy; a 401 must not.
    const later = Date.now() + 31 * 60 * 1000;
    vi.spyOn(Date, "now").mockReturnValue(later);
    await expect(api.summary("q", "mtd")).rejects.toThrow(/link printed in the terminal/);
  });

  it("caches clean payloads as before", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(jsonResponse({ total_mtd: 7 }));
    const { api } = await import("./api");
    await api.summary("p", "mtd");
    const again = await api.summary("p", "mtd");
    expect(again.meta.fromCache).toBe("fresh");
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
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
