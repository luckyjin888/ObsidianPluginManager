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
const { writeSharedPolicyWithBaseline, createObsidianVaultPolicyAdapter, createSharedPolicyBackupEnvelope, validateSharedPolicyBackupEnvelope, buildSharedPolicyBackupFileName, createObsidianVaultBackupAdapter, persistSharedPolicyBackup, scanSharedPolicyBackups, prepareSharedPolicyRestorePreview, restoreSharedPolicyWithBackup } = await import(`data:text/javascript;base64,${encoded}`);

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


function fakeBackupVault(options = {}) {
  const files = new Map();
  const state = { folder: false, creates: 0, folderCreates: 0, reads: 0 };
  const api = {
    getAbstractFileByPath(path) {
      if (path === "PluginManager/backups" && state.folder) return { path, children: [...files.values()] };
      return files.get(path) ?? null;
    },
    async createFolder() {
      state.folderCreates++;
      if (options.throwFolder) throw new Error("injected folder failure");
      state.folder = true;
    },
    async create(path, content) {
      state.creates++;
      if (options.throwCreate) throw new Error("injected backup create failure");
      if (files.has(path)) throw new Error("file already exists");
      const file = { path, content, extension: "json", stat: { size: content.length } };
      files.set(path, file);
      return file;
    },
    async read(file) {
      state.reads++;
      if (options.throwRead) throw new Error("injected backup read failure");
      return options.corruptRead ? "{corrupted" : file.content;
    },
  };
  return { adapter: api, files, state };
}

test("persists a new backup without overwriting and verifies exact read-back", async () => {
  const fake = fakeBackupVault();
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  const result = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  assert.equal(result.status, "created");
  assert.equal(fake.state.folderCreates, 1);
  assert.equal(fake.state.creates, 1);
  assert.equal(fake.state.reads, 1);
  const raw = fake.files.get(result.path).content;
  const checked = await validateSharedPolicyBackupEnvelope(raw);
  assert.equal(checked.ok, true);
  assert.equal(checked.backup.original_content, baseline);
});

test("reuses an identical backup and refuses to overwrite a corrupted path", async () => {
  const fake = fakeBackupVault();
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  const first = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  const second = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  assert.equal(first.status, "created");
  assert.deepEqual(second, { status: "already-exists", path: first.path });
  assert.equal(fake.state.creates, 1);

  fake.files.get(first.path).content = "{unexpected replacement}";
  const collision = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  assert.equal(collision.status, "failed");
  assert.match(collision.message, /not overwritten/);
  assert.equal(fake.state.creates, 1);
  assert.equal(fake.files.get(first.path).content, "{unexpected replacement}");
});

test("preserves a backup whose read-back verification fails", async () => {
  const fake = fakeBackupVault({ corruptRead: true });
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  const result = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  assert.equal(result.status, "verification-failed");
  assert.equal(fake.state.creates, 1);
  assert.equal(fake.files.size, 1);
});

test("reports backup folder, create, and read failures without touching the policy", async () => {
  for (const options of [{ throwFolder: true }, { throwCreate: true }, { throwRead: true }]) {
    const fake = fakeBackupVault(options);
    const adapter = createObsidianVaultBackupAdapter(fake.adapter);
    const result = await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
    assert.equal(result.status, "failed");
    assert.equal(fake.state.creates <= 1, true);
  }
});


test("read-only backup scan lists valid backups newest-first and validates embedded policies", async () => {
  const fake = fakeBackupVault();
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  await persistSharedPolicyBackup(adapter, candidate, "2026-11-28T03:00:00.000Z");
  const items = await scanSharedPolicyBackups(adapter);
  assert.equal(items.length, 2);
  assert.equal(items[0].status, "valid");
  assert.equal(items[0].backup.created_at, "2026-11-28T03:00:00.000Z");
  assert.equal(items[1].status, "valid");
  assert.equal(items[1].backup.original_content, baseline);
  assert.equal(fake.state.creates, 2);
});

test("read-only backup scan reports corrupt and invalid-policy backups without modifying them", async () => {
  const fake = fakeBackupVault();
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  await persistSharedPolicyBackup(adapter, "{not a policy", "2026-11-28T02:00:00.000Z");
  const corruptPath = "PluginManager/backups/corrupt.backup.json";
  const corruptFile = { path: corruptPath, content: "{bad", extension: "json", stat: { size: 4 } };
  fake.files.set(corruptPath, corruptFile);
  const before = [...fake.files.entries()].map(([path, file]) => [path, file.content]);
  const items = await scanSharedPolicyBackups(adapter);
  assert.equal(items.some((item) => item.status === "invalid-policy"), true);
  assert.equal(items.some((item) => item.status === "invalid-backup"), true);
  assert.deepEqual([...fake.files.entries()].map(([path, file]) => [path, file.content]), before);
});

test("read-only backup scan skips oversized entries before reading", async () => {
  const fake = fakeBackupVault();
  fake.state.folder = true;
  const path = "PluginManager/backups/too-large.backup.json";
  fake.files.set(path, { path, content: "x", extension: "json", stat: { size: 200000 } });
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  const items = await scanSharedPolicyBackups(adapter);
  assert.equal(items.length, 1);
  assert.equal(items[0].status, "oversized");
  assert.equal(fake.state.reads, 0);
});

test("read-only backup scan reports unreadable backup files", async () => {
  const options = {};
  const fake = fakeBackupVault(options);
  const adapter = createObsidianVaultBackupAdapter(fake.adapter);
  await persistSharedPolicyBackup(adapter, baseline, "2026-11-28T02:00:00.000Z");
  options.throwRead = true;
  fake.state.reads = 0;
  const items = await scanSharedPolicyBackups(adapter);
  assert.equal(items[0].status, "invalid-backup");
  assert.equal(fake.state.reads, 1);
});


test("restore preview accepts a verified backup only when current content still matches reviewed baseline", async () => {
  const backup = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const result = await prepareSharedPolicyRestorePreview(backup, candidate, candidate);
  assert.equal(result.status, "ready");
  assert.equal(result.target_path, "PluginManager/shared-policy.json");
  assert.equal(result.backup_created_at, "2026-11-28T03:00:00.000Z");
  assert.equal(result.restored_policy_revision, "r1");
  assert.equal(result.restored_plugin_count, 1);
  assert.equal(result.restore_content, baseline);
});

test("restore preview blocks if the current policy changed or appeared/disappeared after review", async () => {
  const backup = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const changed = await prepareSharedPolicyRestorePreview(backup, candidate, baseline);
  assert.equal(changed.status, "stale");
  const appeared = await prepareSharedPolicyRestorePreview(backup, null, candidate);
  assert.equal(appeared.status, "stale");
  const disappeared = await prepareSharedPolicyRestorePreview(backup, candidate, null);
  assert.equal(disappeared.status, "stale");
});

test("restore preview rejects invalid backup digest and invalid embedded policy", async () => {
  const backup = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const tampered = { ...backup, original_content: candidate };
  const invalidDigest = await prepareSharedPolicyRestorePreview(tampered, baseline, baseline);
  assert.equal(invalidDigest.status, "invalid-backup");
  const invalidPolicyBackup = await createSharedPolicyBackupEnvelope("{not a policy", "2026-11-28T03:00:00.000Z");
  const invalidPolicy = await prepareSharedPolicyRestorePreview(invalidPolicyBackup, baseline, baseline);
  assert.equal(invalidPolicy.status, "invalid-policy");
});


test("confirmed restore persists and verifies a fresh backup before writing", async () => {
  const policy = fakeVault(candidate);
  const backup = fakeBackupVault();
  const selected = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const result = await restoreSharedPolicyWithBackup(
    policy, createObsidianVaultBackupAdapter(backup.adapter), {}, selected,
    candidate, candidate, "2026-11-28T04:00:00.000Z", true,
  );
  assert.equal(result.status, "restored");
  assert.equal(policy.state.content, baseline);
  assert.equal(backup.state.creates, 1);
  assert.equal(backup.state.reads, 1);
  assert.equal(policy.state.writes, 1);
});

test("restore requires explicit confirmation and rejects a stale reviewed baseline before backup", async () => {
  const selected = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const policy = fakeVault(candidate);
  const backup = fakeBackupVault();
  const unconfirmed = await restoreSharedPolicyWithBackup(
    policy, createObsidianVaultBackupAdapter(backup.adapter), {}, selected,
    candidate, candidate, "2026-11-28T04:00:00.000Z", false,
  );
  assert.deepEqual(unconfirmed, { status: "confirmation-required" });
  assert.equal(backup.state.creates, 0);
  const stale = await restoreSharedPolicyWithBackup(
    policy, createObsidianVaultBackupAdapter(backup.adapter), {}, selected,
    candidate, baseline, "2026-11-28T04:00:00.000Z", true,
  );
  assert.equal(stale.status, "stale");
  assert.equal(backup.state.creates, 0);
  assert.equal(policy.state.writes, 0);
});

test("restore aborts when the final Vault.process baseline changed after backup", async () => {
  const selected = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const concurrent = JSON.stringify({ schema_version: 1, revision: "r9", plugins: [{ id: "dataview" }] });
  const policy = fakeVault(candidate, { beforeProcess: () => concurrent });
  const backup = fakeBackupVault();
  const result = await restoreSharedPolicyWithBackup(
    policy, createObsidianVaultBackupAdapter(backup.adapter), {}, selected,
    candidate, candidate, "2026-11-28T04:00:00.000Z", true,
  );
  assert.equal(result.status, "stale");
  assert.equal(policy.state.content, concurrent);
  assert.equal(policy.state.writes, 0);
  assert.equal(backup.state.creates, 1);
});

test("restore reports failed fresh-backup persistence and never writes primary", async () => {
  const selected = await createSharedPolicyBackupEnvelope(baseline, "2026-11-28T03:00:00.000Z");
  const policy = fakeVault(candidate);
  const backup = fakeBackupVault({ throwCreate: true });
  const result = await restoreSharedPolicyWithBackup(
    policy, createObsidianVaultBackupAdapter(backup.adapter), {}, selected,
    candidate, candidate, "2026-11-28T04:00:00.000Z", true,
  );
  assert.equal(result.status, "backup-failed");
  assert.equal(policy.state.writes, 0);
});
