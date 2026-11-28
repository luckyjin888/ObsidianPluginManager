import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { test } from "node:test";
import { build } from "esbuild";

if (!globalThis.crypto) globalThis.crypto = webcrypto;

const bundled = await build({
  entryPoints: ["src/install-transaction.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const encoded = Buffer.from(bundled.outputFiles[0].text).toString("base64");
const { buildInstallPlan } = await import(`data:text/javascript;base64,${encoded}`);

function asset(name, value) {
  const bytes = new TextEncoder().encode(value);
  return {
    name,
    bytes,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

function input(overrides = {}) {
  const manifest = JSON.stringify({
    id: "sample-tool",
    version: "1.2.3",
    minAppVersion: "1.5.0",
    isDesktopOnly: false,
  });
  return {
    pluginId: "sample-tool",
    releaseVersion: "1.2.3",
    obsidianApiVersion: "1.6.7",
    runtimePlatform: "macos",
    platformEvidence: { macos: "verified" },
    configDir: ".obsidian",
    assets: [
      asset("manifest.json", manifest),
      asset("main.js", "/* verified plugin bundle */"),
    ],
    ...overrides,
  };
}

test("builds a plan only from digest-verified allowlisted bytes", async () => {
  const result = await buildInstallPlan(input());
  assert.equal(result.status, "ready");
  assert.equal(result.plan.targetDirectory, ".obsidian/plugins/sample-tool");
  assert.deepEqual(result.plan.assets.map((item) => item.name), ["manifest.json", "main.js"]);
  assert.equal(result.plan.manifest.minAppVersion, "1.5.0");
});

test("blocks bytes whose SHA-256 differs from release metadata", async () => {
  const data = input();
  data.assets[1] = { ...data.assets[1], sha256: "0".repeat(64) };
  const result = await buildInstallPlan(data);
  assert.equal(result.status, "blocked");
  assert.match(result.reasons.join(" "), /SHA-256/);
});

test("requires both iOS and iPadOS evidence for the iOS runtime", async () => {
  const result = await buildInstallPlan(input({
    runtimePlatform: "ios",
    platformEvidence: { ios: "verified", ipados: "unknown" },
  }));
  assert.equal(result.status, "blocked");
  assert.match(result.reasons.join(" "), /iPadOS/);
});

test("blocks an incompatible minimum Obsidian API version", async () => {
  const data = input();
  data.assets[0] = asset("manifest.json", JSON.stringify({
    id: "sample-tool",
    version: "1.2.3",
    minAppVersion: "2.0.0",
    isDesktopOnly: false,
  }));
  const result = await buildInstallPlan(data);
  assert.equal(result.status, "blocked");
  assert.match(result.reasons.join(" "), /Requires Obsidian API/);
});

test("blocks unsafe config paths and plugin identifiers", async () => {
  const pathResult = await buildInstallPlan(input({ configDir: "../outside" }));
  assert.equal(pathResult.status, "blocked");
  assert.match(pathResult.reasons.join(" "), /configDir/);

  const idResult = await buildInstallPlan(input({ pluginId: "../sample-tool" }));
  assert.equal(idResult.status, "blocked");
  assert.match(idResult.reasons.join(" "), /Plugin ID/);
});

test("blocks unknown release assets", async () => {
  const data = input();
  data.assets.push(asset("README.md", "not an install asset"));
  const result = await buildInstallPlan(data);
  assert.equal(result.status, "blocked");
  assert.match(result.reasons.join(" "), /Unexpected release asset/);
});

test("blocks duplicate release asset names", async () => {
  const data = input();
  data.assets.push(asset("main.js", "second bundle"));
  const result = await buildInstallPlan(data);
  assert.equal(result.status, "blocked");
  assert.match(result.reasons.join(" "), /duplicate asset names/);
});
