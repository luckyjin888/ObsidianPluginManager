import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { test } from "node:test";
import { build } from "esbuild";

if (!globalThis.crypto) globalThis.crypto = webcrypto;

const bundled = await build({
  entryPoints: ["src/install-staging.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const encoded = Buffer.from(bundled.outputFiles[0].text).toString("base64");
const { stageInstallPlan } = await import(`data:text/javascript;base64,${encoded}`);

function bytes(value) {
  return new Uint8Array(Buffer.from(value, "utf8"));
}

function digest(value) {
  return createHash("sha256").update(value).digest("hex");
}

function makePlan() {
  const manifest = bytes(JSON.stringify({ id: "sample-tool", version: "1.2.3" }));
  const main = bytes("verified bundle bytes");
  return {
    pluginId: "sample-tool",
    releaseVersion: "1.2.3",
    runtimePlatform: "macos",
    targetDirectory: ".obsidian/plugins/sample-tool",
    assets: [
      { name: "manifest.json", bytes: manifest, sha256: digest(manifest) },
      { name: "main.js", bytes: main, sha256: digest(main) },
    ],
    totalBytes: manifest.byteLength + main.byteLength,
    manifest: { id: "sample-tool", version: "1.2.3", minAppVersion: "1.5.0" },
  };
}

class FakeAdapter {
  constructor() {
    this.directories = new Set([".obsidian", ".obsidian/plugins", ".obsidian/plugins/sample-tool"]);
    this.files = new Map([[".obsidian/plugins/sample-tool/main.js", bytes("existing live plugin")]]);
    this.corruptReadBack = false;
    this.failWriteName = null;
  }
  async exists(path) { return this.directories.has(path) || this.files.has(path); }
  async mkdir(path) {
    const parent = path.split("/").slice(0, -1).join("/");
    if (!this.directories.has(parent)) throw new Error("parent directory missing");
    if (await this.exists(path)) throw new Error("path already exists");
    this.directories.add(path);
  }
  async writeBinary(path, data) {
    if (this.failWriteName && path.endsWith(this.failWriteName)) throw new Error("injected write failure");
    if (await this.exists(path)) throw new Error("refusing overwrite");
    this.files.set(path, new Uint8Array(data));
  }
  async readBinary(path) {
    const value = this.files.get(path);
    if (!value) throw new Error("file missing");
    const copy = new Uint8Array(value);
    if (this.corruptReadBack && path.endsWith("main.js")) copy[0] ^= 1;
    return copy.buffer;
  }
  async remove(path) {
    if (this.files.has(path)) { this.files.delete(path); return; }
    for (const item of [...this.files.keys(), ...this.directories]) {
      if (item.startsWith(path + "/")) throw new Error("directory not empty");
    }
    this.directories.delete(path);
  }
}

test("stages all allowlisted bytes and verifies exact read-back without touching live plugin", async () => {
  const adapter = new FakeAdapter();
  const original = Buffer.from(adapter.files.get(".obsidian/plugins/sample-tool/main.js"));
  const result = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "tx-001", confirmed: true,
  });
  assert.equal(result.status, "staged");
  assert.equal(result.files.length, 2);
  assert.equal(Buffer.from(adapter.files.get(".obsidian/plugins/sample-tool/main.js")).toString(), original.toString());
  assert.equal(result.files.every((file) => adapter.files.has(file.path)), true);
});

test("blocks staging without explicit confirmation", async () => {
  const adapter = new FakeAdapter();
  const result = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "tx-002", confirmed: false,
  });
  assert.equal(result.status, "blocked");
  assert.match(result.reason, /confirmation/);
  assert.equal([...adapter.files.keys()].some((path) => path.includes("staging")), false);
});

test("refuses to overwrite an existing transaction directory", async () => {
  const adapter = new FakeAdapter();
  adapter.directories.add(".obsidian/plugins/.plugin-manager-staging");
  adapter.directories.add(".obsidian/plugins/.plugin-manager-staging/sample-tool");
  adapter.directories.add(".obsidian/plugins/.plugin-manager-staging/sample-tool/tx-003");
  const result = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "tx-003", confirmed: true,
  });
  assert.equal(result.status, "blocked");
  assert.match(result.reason, /already exists/);
});

test("rejects an unsafe transaction ID or target path", async () => {
  const adapter = new FakeAdapter();
  const unsafeId = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "../escape", confirmed: true,
  });
  assert.equal(unsafeId.status, "blocked");

  const plan = makePlan();
  plan.targetDirectory = ".obsidian/plugins/../sample-tool";
  const unsafePath = await stageInstallPlan({
    adapter, plan, transactionId: "tx-004", confirmed: true,
  });
  assert.equal(unsafePath.status, "blocked");
});

test("cleans up partial staging after a write failure and preserves live files", async () => {
  const adapter = new FakeAdapter();
  adapter.failWriteName = "main.js";
  const result = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "tx-005", confirmed: true,
  });
  assert.equal(result.status, "failed");
  assert.deepEqual(result.leftoverPaths, []);
  assert.equal([...adapter.files.keys()].some((path) => path.includes(".plugin-manager-staging")), false);
  assert.equal(Buffer.from(adapter.files.get(".obsidian/plugins/sample-tool/main.js")).toString(), "existing live plugin");
});

test("cleans up staged files when read-back integrity verification fails", async () => {
  const adapter = new FakeAdapter();
  adapter.corruptReadBack = true;
  const result = await stageInstallPlan({
    adapter, plan: makePlan(), transactionId: "tx-006", confirmed: true,
  });
  assert.equal(result.status, "failed");
  assert.match(result.reason, /read-back verification failed/);
  assert.deepEqual(result.leftoverPaths, []);
  assert.equal([...adapter.files.keys()].some((path) => path.includes(".plugin-manager-staging")), false);
});
