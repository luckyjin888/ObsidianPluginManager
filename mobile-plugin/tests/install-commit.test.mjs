import assert from "node:assert/strict";
import { test } from "node:test";
import { build } from "esbuild";

const bundled = await build({
  entryPoints: ["src/install-commit.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const encoded = Buffer.from(bundled.outputFiles[0].text).toString("base64");
const { commitStagedInstall } = await import(`data:text/javascript;base64,${encoded}`);

async function sha(bytes) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
function buffer(text) {
  return new TextEncoder().encode(text).buffer;
}
function fakeAdapter(initial = {}, options = {}) {
  const files = new Map(Object.entries(initial).map(([path, value]) => [path, buffer(value)]));
  const dirs = new Set([".obsidian", ".obsidian/plugins", "PluginManager"]);
  let writes = 0;
  return {
    files, dirs,
    async exists(path) { return files.has(path) || dirs.has(path); },
    async mkdir(path) { dirs.add(path); },
    async readBinary(path) {
      if (!files.has(path)) throw new Error("missing " + path);
      return files.get(path).slice(0);
    },
    async writeBinary(path, data) {
      writes++;
      if (options.failWriteAt === writes) throw new Error("injected write failure");
      files.set(path, data.slice(0));
    },
    async remove(path) { files.delete(path); },
  };
}
async function fixture(adapter, { oldMain = "old-main", includeOldStyle = true } = {}) {
  const assets = [
    { name: "manifest.json", text: '{"id":"demo","version":"2.0.0"}' },
    { name: "main.js", text: "new-main" },
  ];
  if (includeOldStyle) assets.push({ name: "styles.css", text: "new-style" });
  const planAssets = [];
  const staged = [];
  for (const asset of assets) {
    const bytes = new TextEncoder().encode(asset.text);
    const sha256 = await sha(bytes);
    planAssets.push({ name: asset.name, bytes, sha256 });
    const path = `.obsidian/plugins/.plugin-manager-staging/demo/tx1/${asset.name}`;
    await adapter.writeBinary(path, bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    staged.push({ name: asset.name, path, byteLength: bytes.byteLength, sha256 });
  }
  const plan = {
    pluginId: "demo",
    releaseVersion: "2.0.0",
    runtimePlatform: "windows",
    targetDirectory: ".obsidian/plugins/demo",
    assets: planAssets,
    totalBytes: planAssets.reduce((sum, item) => sum + item.bytes.byteLength, 0),
    manifest: { id: "demo", version: "2.0.0", minAppVersion: "1.0.0" },
  };
  return { plan, staged };
}

test("backs up existing allowlisted files before replacing and verifies installed bytes", async () => {
  const adapter = fakeAdapter({
    ".obsidian/plugins/demo/manifest.json": "old-manifest",
    ".obsidian/plugins/demo/main.js": "old-main",
    ".obsidian/plugins/demo/data.json": '{"user":"keep"}',
  });
  const { plan, staged } = await fixture(adapter);
  const result = await commitStagedInstall(adapter, plan, staged,
    ".obsidian/plugins/.plugin-manager-staging/demo/tx1", "tx1", true, "2026-11-28T04:00:00.000Z");
  assert.equal(result.status, "installed");
  assert.equal(new TextDecoder().decode(await adapter.readBinary(".obsidian/plugins/demo/main.js")), "new-main");
  assert.equal(new TextDecoder().decode(await adapter.readBinary(".obsidian/plugins/demo/data.json")), '{"user":"keep"}');
  assert.equal(new TextDecoder().decode(await adapter.readBinary(result.backupDirectory + "/main.js")), "old-main");
  assert.equal(adapter.files.has(result.backupDirectory + "/backup-manifest.json"), true);
});

test("requires explicit confirmation and refuses an existing backup transaction", async () => {
  const adapter = fakeAdapter();
  const { plan, staged } = await fixture(adapter);
  const args = [adapter, plan, staged, ".obsidian/plugins/.plugin-manager-staging/demo/tx1", "tx1"];
  assert.equal((await commitStagedInstall(...args, false, "2026-11-28T04:00:00.000Z")).status, "blocked");
  adapter.dirs.add("PluginManager/install-backups/demo/tx1");
  assert.equal((await commitStagedInstall(...args, true, "2026-11-28T04:00:00.000Z")).status, "blocked");
});

test("refuses staged bytes that no longer match the approved digest", async () => {
  const adapter = fakeAdapter();
  const { plan, staged } = await fixture(adapter);
  await adapter.writeBinary(staged[1].path, buffer("tampered"));
  const result = await commitStagedInstall(adapter, plan, staged,
    ".obsidian/plugins/.plugin-manager-staging/demo/tx1", "tx1", true, "2026-11-28T04:00:00.000Z");
  assert.equal(result.status, "blocked");
  assert.equal(adapter.files.has(".obsidian/plugins/demo/main.js"), false);
});

test("rolls back already attempted files after a mid-commit write failure", async () => {
  const adapter = fakeAdapter({
    ".obsidian/plugins/demo/manifest.json": "old-manifest",
    ".obsidian/plugins/demo/main.js": "old-main",
  }, { failWriteAt: 5 });
  const { plan, staged } = await fixture(adapter);
  // Three staging writes occur in fixture; backup files/manifest are writes 4-6.
  // Use a later injected failure so the first live target write succeeds.
  const originalWrite = adapter.writeBinary.bind(adapter);
  let liveWrites = 0;
  adapter.writeBinary = async (path, data) => {
    if (path.startsWith(".obsidian/plugins/demo/")) {
      liveWrites++;
      if (liveWrites === 2) throw new Error("injected second live-file failure");
    }
    await originalWrite(path, data);
  };
  const result = await commitStagedInstall(adapter, plan, staged,
    ".obsidian/plugins/.plugin-manager-staging/demo/tx1", "tx1", true, "2026-11-28T04:00:00.000Z");
  assert.equal(result.status, "failed");
  assert.equal(result.rollback, "restored");
  assert.equal(new TextDecoder().decode(await adapter.readBinary(".obsidian/plugins/demo/manifest.json")), "old-manifest");
  assert.equal(new TextDecoder().decode(await adapter.readBinary(".obsidian/plugins/demo/main.js")), "old-main");
});

test("does not delete unrelated plugin data or stale files absent from the new release", async () => {
  const adapter = fakeAdapter({
    ".obsidian/plugins/demo/data.json": '{"keep":true}',
    ".obsidian/plugins/demo/old-extra.js": "keep-unknown-file",
    ".obsidian/plugins/demo/styles.css": "old-style",
  });
  const { plan, staged } = await fixture(adapter, { includeOldStyle: false });
  const result = await commitStagedInstall(adapter, plan, staged,
    ".obsidian/plugins/.plugin-manager-staging/demo/tx1", "tx1", true, "2026-11-28T04:00:00.000Z");
  assert.equal(result.status, "installed");
  assert.equal(adapter.files.has(".obsidian/plugins/demo/styles.css"), true);
  assert.equal(adapter.files.has(".obsidian/plugins/demo/old-extra.js"), true);
  assert.equal(adapter.files.has(".obsidian/plugins/demo/data.json"), true);
});
