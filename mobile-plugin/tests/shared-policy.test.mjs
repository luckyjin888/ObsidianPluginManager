import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: ["src/shared-policy.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const encoded = Buffer.from(bundled.outputFiles[0].text).toString("base64");
const { parseSharedPluginPolicy, findPolicyConflictCandidates, fingerprintSharedPolicy, compareSharedPolicyPluginIds, buildSharedPolicyResolutionPreview } = await import(`data:text/javascript;base64,${encoded}`);

test("accepts a valid minimal policy", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-1",
    plugins: [{ id: "quickadd" }],
  }));
  assert.equal(result.ok, true);
  assert.equal(result.policy?.plugins[0].id, "quickadd");
});

test("accepts bounded optional notes", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-2",
    plugins: [{ id: "quickadd", note: "Wanted on all devices" }],
  }));
  assert.equal(result.ok, true);
  assert.equal(result.policy?.plugins[0].note, "Wanted on all devices");
});

test("rejects duplicate IDs", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-3",
    plugins: [{ id: "quickadd" }, { id: "quickadd" }],
  }));
  assert.equal(result.ok, false);
  assert.match(result.errors.join(" "), /Duplicate plugin ID/);
});

test("rejects unsafe IDs and arbitrary fields", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-4",
    plugins: [{ id: "../plugins/main", source_url: "https://example.com/payload" }],
  }));
  assert.equal(result.ok, false);
});

test("rejects unknown top-level fields", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-5",
    plugins: [],
    install_now: true,
  }));
  assert.equal(result.ok, false);
  assert.match(result.errors.join(" "), /unsupported top-level fields/);
});

test("rejects invalid JSON and oversized documents", () => {
  assert.equal(parseSharedPluginPolicy("{").ok, false);
  assert.equal(parseSharedPluginPolicy(" ".repeat(64 * 1024 + 1)).ok, false);
});

test("rejects more than 200 entries", () => {
  const result = parseSharedPluginPolicy(JSON.stringify({
    schema_version: 1,
    revision: "rev-6",
    plugins: Array.from({ length: 201 }, (_, i) => ({ id: `plugin-${i}` })),
  }));
  assert.equal(result.ok, false);
  assert.match(result.errors.join(" "), /more than 200/);
});

test("surfaces possible conflict copies without treating the primary file as a conflict", () => {
  const candidates = findPolicyConflictCandidates([
    "PluginManager/shared-policy.json",
    "PluginManager/shared-policy (conflicted copy 2026-11-28).json",
    "PluginManager/shared-policy.conflict.json",
    "PluginManager/other.json",
  ]);
  assert.deepEqual(candidates, [
    "PluginManager/shared-policy (conflicted copy 2026-11-28).json",
    "PluginManager/shared-policy.conflict.json",
  ]);
});

test("fingerprint is stable for identical policy text and changes with content", async () => {
  const first = await fingerprintSharedPolicy('{"schema_version":1}');
  const same = await fingerprintSharedPolicy('{"schema_version":1}');
  const changed = await fingerprintSharedPolicy('{"schema_version":2}');
  assert.equal(first, same);
  assert.notEqual(first, changed);
  assert.match(first, /^[a-f0-9]{64}$/);
});

test("compares candidate policy lists without mutating either policy", () => {
  const current = {
    schema_version: 1,
    revision: "current",
    plugins: [{ id: "quickadd" }, { id: "templater" }],
  };
  const candidate = {
    schema_version: 1,
    revision: "conflict-copy",
    plugins: [{ id: "quickadd" }, { id: "dataview" }],
  };
  const diff = compareSharedPolicyPluginIds(current, candidate);
  assert.deepEqual(diff.onlyInCandidate, ["dataview"]);
  assert.deepEqual(diff.onlyInCurrent, ["templater"]);
  assert.deepEqual(current.plugins.map((entry) => entry.id), ["quickadd", "templater"]);
  assert.deepEqual(candidate.plugins.map((entry) => entry.id), ["quickadd", "dataview"]);
});


test("requires an explicit choice for every ID in a conflict resolution preview", () => {
  const current = { schema_version: 1, revision: "a", plugins: [{ id: "quickadd" }] };
  const candidate = { schema_version: 1, revision: "b", plugins: [{ id: "dataview" }] };
  const result = buildSharedPolicyResolutionPreview(current, candidate, { quickadd: "current" }, "merged-1");
  assert.equal(result.ok, false);
  assert.deepEqual(result.unresolvedIds, ["dataview"]);
  assert.equal(result.json, null);
});

test("builds deterministic in-memory resolution from explicit per-ID choices", () => {
  const current = {
    schema_version: 1, revision: "a",
    plugins: [{ id: "quickadd", note: "keep current note" }, { id: "templater" }],
  };
  const candidate = {
    schema_version: 1, revision: "b",
    plugins: [{ id: "quickadd", note: "use candidate note" }, { id: "dataview" }],
  };
  const beforeCurrent = JSON.stringify(current);
  const beforeCandidate = JSON.stringify(candidate);
  const result = buildSharedPolicyResolutionPreview(current, candidate, {
    quickadd: "candidate",
    templater: "remove",
    dataview: "candidate",
  }, "merged-2");
  assert.equal(result.ok, true);
  assert.deepEqual(result.policy.plugins, [
    { id: "dataview" },
    { id: "quickadd", note: "use candidate note" },
  ]);
  assert.match(result.json, /"revision": "merged-2"/);
  assert.equal(JSON.stringify(current), beforeCurrent);
  assert.equal(JSON.stringify(candidate), beforeCandidate);
});

test("rejects choices that select an entry absent from the chosen source", () => {
  const current = { schema_version: 1, revision: "a", plugins: [{ id: "quickadd" }] };
  const candidate = { schema_version: 1, revision: "b", plugins: [] };
  const result = buildSharedPolicyResolutionPreview(current, candidate, {
    quickadd: "candidate",
  }, "merged-3");
  assert.equal(result.ok, false);
  assert.deepEqual(result.invalidChoices, ["quickadd"]);
  assert.equal(result.json, null);
});

test("rejects invalid choices and invalid revision values", () => {
  const current = { schema_version: 1, revision: "a", plugins: [{ id: "quickadd" }] };
  const candidate = { schema_version: 1, revision: "b", plugins: [] };
  const invalidChoice = buildSharedPolicyResolutionPreview(current, candidate, {
    quickadd: "automatic",
  }, "merged-4");
  assert.equal(invalidChoice.ok, false);
  assert.deepEqual(invalidChoice.invalidChoices, ["quickadd"]);
  const invalidRevision = buildSharedPolicyResolutionPreview(current, candidate, {
    quickadd: "current",
  }, "");
  assert.equal(invalidRevision.ok, false);
  assert.deepEqual(invalidRevision.invalidChoices, ["<revision>"]);
});
