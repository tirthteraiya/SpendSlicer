import { expect, it, vi } from "vitest";
import { readPreference, writePreference } from "./preferences";

it("blocked browser storage cannot prevent the dashboard from opening", () => {
  const storage = { getItem: () => { throw new Error("SecurityError"); }, setItem: () => { throw new Error("QuotaExceededError"); } };
  vi.stubGlobal("localStorage", storage);
  expect(readPreference("acu:profile")).toBe("");
  expect(() => writePreference("acu:profile", "prod")).not.toThrow();
  vi.unstubAllGlobals();
});
