/**
 * P4.4.1 — pure install-plan gate.
 *
 * This module deliberately performs no network request and no Vault mutation.
 * It accepts the exact in-memory bytes intended for installation, verifies
 * those bytes again against the release SHA-256 metadata, validates the
 * manifest/platform/path constraints, and returns a plan for a later writer.
 *
 * P4.4.2+ must re-verify these bytes immediately before staging/writing.
 */

export type InstallPlatform = "windows" | "macos" | "ios" | "ipados" | "android";
export type InstallCompatibility = "verified" | "declared_unverified" | "incompatible" | "unknown";

export interface InstallAssetBytes {
  name: string;
  bytes: Uint8Array;
  sha256: string;
}

export interface InstallPlatformEvidence {
  windows?: InstallCompatibility;
  macos?: InstallCompatibility;
  ios?: InstallCompatibility;
  ipados?: InstallCompatibility;
  android?: InstallCompatibility;
}

export interface BuildInstallPlanInput {
  pluginId: string;
  releaseVersion: string;
  obsidianApiVersion: string;
  runtimePlatform: InstallPlatform;
  platformEvidence: InstallPlatformEvidence;
  configDir: string;
  assets: InstallAssetBytes[];
}

export interface PlannedInstallAsset {
  name: "manifest.json" | "main.js" | "styles.css";
  bytes: Uint8Array;
  sha256: string;
}

export interface InstallPlan {
  pluginId: string;
  releaseVersion: string;
  runtimePlatform: InstallPlatform;
  targetDirectory: string;
  assets: PlannedInstallAsset[];
  totalBytes: number;
  manifest: {
    id: string;
    version: string;
    minAppVersion: string;
  };
}

export type InstallPlanResult =
  | { status: "ready"; plan: InstallPlan }
  | { status: "blocked"; reasons: string[] };

const MAX_SIZES: Record<string, number> = {
  "manifest.json": 256 * 1024,
  "main.js": 20 * 1024 * 1024,
  "styles.css": 2 * 1024 * 1024,
};
const MAX_TOTAL_SIZE = 25 * 1024 * 1024;
const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const SAFE_PLUGIN_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

interface ParsedManifest {
  id?: unknown;
  version?: unknown;
  minAppVersion?: unknown;
  isDesktopOnly?: unknown;
}

function parseVersion(value: string): [number, number, number] | null {
  const match = value.match(VERSION);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function compareVersions(left: string, right: string): number | null {
  const a = parseVersion(left);
  const b = parseVersion(right);
  if (!a || !b) return null;
  for (let i = 0; i < 3; i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return 0;
}

function safeConfigDir(value: string): boolean {
  if (
    !value
    || value.startsWith("/")
    || value.includes(String.fromCharCode(92))
    || value.includes(String.fromCharCode(0))
  ) return false;
  const parts = value.split("/");
  return parts.every((part) => part.length > 0 && part !== "." && part !== "..");
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", toArrayBuffer(bytes));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/**
 * Builds a conservative install plan from the exact bytes the later writer
 * would stage. "ready" means only that this preflight passed; it does not
 * perform installation or imply that a platform has been physically tested.
 */
export async function buildInstallPlan(input: BuildInstallPlanInput): Promise<InstallPlanResult> {
  const reasons: string[] = [];

  if (
    !SAFE_PLUGIN_ID.test(input.pluginId)
    || input.pluginId.includes("obsidian")
    || input.pluginId.endsWith("plugin")
  ) {
    reasons.push("Plugin ID does not satisfy the safe community-plugin ID rules.");
  }

  if (!safeConfigDir(input.configDir)) {
    reasons.push("Obsidian configDir must be a safe relative Vault path.");
  }

  const requiredPlatforms: InstallPlatform[] = input.runtimePlatform === "ios"
    ? ["ios", "ipados"]
    : [input.runtimePlatform];
  for (const platform of requiredPlatforms) {
    if (input.platformEvidence[platform] !== "verified") {
      reasons.push(
        input.runtimePlatform === "ios"
          ? `Both iOS and iPadOS must be verified; ${platform} is ${input.platformEvidence[platform] ?? "unknown"}.`
          : `${platform} compatibility is ${input.platformEvidence[platform] ?? "unknown"}; only verified entries may proceed.`,
      );
    }
  }

  if (!parseVersion(input.releaseVersion)) {
    reasons.push("Release version must be a stable three-part semantic version.");
  }
  if (!parseVersion(input.obsidianApiVersion)) {
    reasons.push("Obsidian API version is missing or invalid.");
  }

  const names = input.assets.map((asset) => asset.name);
  if (new Set(names).size !== names.length) reasons.push("Release contains duplicate asset names.");
  for (const name of names) {
    if (!(name in MAX_SIZES)) reasons.push(`Unexpected release asset: ${name}.`);
  }
  if (!names.includes("manifest.json")) reasons.push("manifest.json is missing.");
  if (!names.includes("main.js")) reasons.push("main.js is missing.");

  let totalBytes = 0;
  const plannedAssets: PlannedInstallAsset[] = [];
  for (const asset of input.assets) {
    const limit = MAX_SIZES[asset.name];
    if (limit === undefined) continue;
    if (!(asset.bytes instanceof Uint8Array)) {
      reasons.push(`${asset.name} is not supplied as verified byte data.`);
      continue;
    }
    if (asset.bytes.byteLength > limit) {
      reasons.push(`${asset.name} exceeds its configured size limit.`);
      continue;
    }
    totalBytes += asset.bytes.byteLength;
    if (!/^[a-f0-9]{64}$/i.test(asset.sha256)) {
      reasons.push(`${asset.name} has invalid SHA-256 metadata.`);
      continue;
    }
    const actualDigest = await sha256Hex(asset.bytes);
    if (actualDigest.toLowerCase() !== asset.sha256.toLowerCase()) {
      reasons.push(`${asset.name} SHA-256 does not match the published release digest.`);
      continue;
    }
    plannedAssets.push({
      name: asset.name as PlannedInstallAsset["name"],
      bytes: new Uint8Array(asset.bytes),
      sha256: actualDigest,
    });
  }
  if (totalBytes > MAX_TOTAL_SIZE) reasons.push("Release assets exceed the 25 MiB total size limit.");

  let manifest: ParsedManifest | null = null;
  const manifestAsset = plannedAssets.find((asset) => asset.name === "manifest.json");
  if (manifestAsset) {
    try {
      const parsed: unknown = JSON.parse(new TextDecoder().decode(manifestAsset.bytes));
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("Manifest root must be an object.");
      }
      manifest = parsed as ParsedManifest;
    } catch (error) {
      reasons.push(error instanceof Error ? error.message : "manifest.json is invalid JSON.");
    }
  }

  if (manifest) {
    if (manifest.id !== input.pluginId) reasons.push("Manifest plugin ID does not match the selected catalogue entry.");
    if (manifest.version !== input.releaseVersion) reasons.push("Manifest version does not match the selected release version.");
    if (typeof manifest.minAppVersion !== "string" || !parseVersion(manifest.minAppVersion)) {
      reasons.push("Manifest minAppVersion is missing or invalid.");
    } else {
      const comparison = compareVersions(input.obsidianApiVersion, manifest.minAppVersion);
      if (comparison === null) reasons.push("Obsidian API version and minAppVersion cannot be compared.");
      else if (comparison < 0) reasons.push(`Requires Obsidian API ${manifest.minAppVersion} or newer.`);
    }
    if (manifest.isDesktopOnly !== false) {
      reasons.push("Manifest does not explicitly declare isDesktopOnly: false.");
    }
  }

  if (reasons.length > 0 || !manifest || !safeConfigDir(input.configDir)) {
    return { status: "blocked", reasons };
  }

  return {
    status: "ready",
    plan: {
      pluginId: input.pluginId,
      releaseVersion: input.releaseVersion,
      runtimePlatform: input.runtimePlatform,
      targetDirectory: `${input.configDir}/plugins/${input.pluginId}`,
      assets: plannedAssets,
      totalBytes,
      manifest: {
        id: manifest.id as string,
        version: manifest.version as string,
        minAppVersion: manifest.minAppVersion as string,
      },
    },
  };
}
