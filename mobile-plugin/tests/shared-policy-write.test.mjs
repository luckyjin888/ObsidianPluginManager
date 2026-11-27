import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: ["src/shared-policy-write.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const encoded = Buffer.from(bundled.outputFiles[0].text).toString("base64");
const { writeSharedPolicyWithBaseline, createObsidianVaultPolicyAdapter, createSharedPolicyBackupEnvelope, validateSharedPolicyBackupEnvelope, buildSharedPolicyBackupFileName } = await import(`data:text/javascript;base64,${encoded}`);

const baseline = JSON.stringify({ schema_version: 1, revision: "r1", plugins: [{ id: "quickadd" }] }, null, 2) + "\n";
const candidate = JSON.stringify({ schema_version: 1, revision: "r2", plugins: [{ id: "quickadd" }, { id: "templater" }] }, null, 2) + "\n";

function fakeVault(initial, options = {}) {
  const state = { content: initial, writes: 0, processCalls: 0, readCalls: 0 };
  return {
    state,
    async process(_file, callback) {
      state.processCalls++;
      if (options.beforeProcess) state.content = options.beforeProcess(state.content);
      if (options.throwProcess) throw new Error("injected process failure");
      const next = callback(state.content);
      if (next !== state.content) state.writes++;
      state.content = next;
    },
    async read() {
      state.readCalls++;
      if (options.throwRead) throw new Error("injected read failure");
      if (options.corruptAfterWrite && state.writes) return options.corruptAfterWrite(state.content);
      return state.content;
    },
  };
}

test("writes validated candidate only when process sees exact baseline", async () => {
  const vault = fakeVault(baseline);
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.deepEqual(result, { status: "written" });
  assert.equal(vault.state.content, candidate);
  assert.equal(vault.state.writes, 1);
  assert.equal(vault.state.readCalls, 1);
});

test("aborts stale preview without overwriting concurrent content", async () => {
  const concurrent = JSON.stringify({ schema_version: 1, revision: "r3", plugins: [{ id: "dataview" }] });
  const vault = fakeVault(baseline, { beforeProcess: () => concurrent });
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.deepEqual(result, { status: "stale", current: concurrent });
  assert.equal(vault.state.content, concurrent);
  assert.equal(vault.state.writes, 0);
  assert.equal(vault.state.readCalls, 0);
});

test("rejects invalid candidate before invoking Vault.process", async () => {
  const vault = fakeVault(baseline);
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, "{");
  assert.equal(result.status, "invalid-candidate");
  assert.equal(vault.state.processCalls, 0);
  assert.equal(vault.state.writes, 0);
});

test("reports process exceptions without claiming success", async () => {
  const vault = fakeVault(baseline, { throwProcess: true });
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.deepEqual(result, { status: "failed", message: "injected process failure" });
  assert.equal(vault.state.writes, 0);
});

test("detects post-write content that does not match the candidate", async () => {
  const vault = fakeVault(baseline, { corruptAfterWrite: () => "{corrupted" });
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.deepEqual(result, { status: "verification-failed", actual: "{corrupted" });
  assert.equal(vault.state.writes, 1);
});

test("reports post-write read failures without claiming success", async () => {
  const vault = fakeVault(baseline, { throwRead: true });
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.deepEqual(result, { status: "failed", message: "injected read failure" });
});

test("rejects adapters that never invoke the process callback", async () => {
  const vault = {
    async process() {},
    async read() { return baseline; },
  };
  const result = await writeSharedPolicyWithBaseline(vault, {}, baseline, candidate);
  assert.equal(result.status, "failed");
  assert.match(result.message, /without invoking its callback/);
});


test("Obsidian Vault adapter delegates process and read to the public API", async () => {
  const calls = [];
  const file = { path: "PluginManager/shared-policy.json" };
  const vaultApi = {
    async process(receivedFile, callback) {
      calls.push(["process", receivedFile]);
      const next = callback(baseline);
      calls.push(["candidate", next]);
      return next;
    },
    async read(receivedFile) {
      calls.push(["read", receivedFile]);
      return candidate;
    },
  };
  const adapter = createObsidianVaultPolicyAdapter(vaultApi);
  const result = await writeSharedPolicyWithBaseline(adapter, file, baseline, candidate);
  assert.deepEqual(result, { status: "written" });
  assert.deepEqual(calls, [
    ["process", file],
    ["candidate", candidate],
    ["read", file],
  ]);
});


test("backup envelope preserves exact original bytes and verifies its digest", async () => {
  const createdAt = "2026-11-28T01:30:00.000Z";
  const backup = await createSharedPolicyBackupEnvelope(baseline, createdAt);
  const raw = JSON.stringify(backup);
  const checked = await validateSharedPolicyBackupEnvelope(raw);
  assert.equal(checked.ok, true);
  assert.equal(checked.backup.original_content, baseline);
  assert.equal(checked.backup.created_at, createdAt);
  assert.match(checked.backup.original_sha256, /^[a-f0-9]{64}$/);
});

test("backup validation rejects tampered original content", async () => {
  const backup = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T01:30:00.000Z");
  backup.original_content = candidate;
  const checked = await validateSharedPolicyBackupEnvelope(JSON.stringify(backup));
  assert.equal(checked.ok, false);
  assert.match(checked.errors.join(" "), /SHA-256/);
});

test("backup validation rejects unsupported fields and malformed timestamps", async () => {
  const backup = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T01:30:00.000Z");
  const extraField = await validateSharedPolicyBackupEnvelope(JSON.stringify({ ...backup, executable: true }));
  assert.equal(extraField.ok, false);
  const badTime = await validateSharedPolicyBackupEnvelope(JSON.stringify({ ...backup, created_at: "not-a-date" }));
  assert.equal(badTime.ok, false);
});

test("backup filename is deterministic and rejects unsafe inputs", () => {
  const digest = "a".repeat(64);
  assert.equal(
    buildSharedPolicyBackupFileName("2026-11-28T01:30:00.000Z", digest),
    "shared-policy-2026-11-28T01-30-00-000Z-" + "a".repeat(12) + ".backup.json",
  );
  assert.equal(buildSharedPolicyBackupFileName("not-a-date", digest), null);
  assert.equal(buildSharedPolicyBackupFileName("2026-11-28T01:30:00.000Z", "../bad"), null);
});
