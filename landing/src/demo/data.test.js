import assert from "node:assert/strict";
import test from "node:test";
import { ATTRIBUTED, CE_TOTAL, COMPOSITION, DRIFT, RESOURCES, SERVICES, TREND, sum } from "./data.js";

test("sample costs reconcile across services, resources, trend, and composition", () => {
  assert.equal(sum(SERVICES), CE_TOTAL);
  assert.equal(sum(TREND, "Spend"), CE_TOTAL);
  assert.equal(sum(RESOURCES), ATTRIBUTED);
  assert.equal(Math.round((ATTRIBUTED + DRIFT) * 100), Math.round(CE_TOTAL * 100));
  for (const [name, composition] of Object.entries(COMPOSITION)) {
    assert.equal(sum(composition.usage_types), SERVICES.find((s) => s.name === name).cost);
  }
  for (const service of SERVICES) {
    assert.ok(sum(RESOURCES.filter((r) => r.service === service.name)) <= service.cost);
  }
});

test("the first dashboard table includes the requested database, MCP server, and bucket", () => {
  const top = [...RESOURCES].sort((a, b) => b.cost - a.cost).slice(0, 10);
  for (const name of ["testing-3-db", "testing-3-mcp-server", "testing-3-s3-bucket"]) {
    assert.ok(top.some((r) => r.name === name), name);
  }
  assert.ok(new Set(top.map((r) => r.service)).size >= 5);
  assert.equal(new Set(RESOURCES.map((r) => r.resource_id)).size, RESOURCES.length);
});
