import { requestUrl } from "obsidian";
import type { ReleaseInspection } from "./release-inspector";

export interface VerifiedReleaseManifest {
  id: string;
  version: string;
  minAppVersion: string;
}

export interface AssetVerificationReport {
  verified: boolean;
  manifest: VerifiedReleaseManifest | null;
  reasons: string[];
}

interface PluginManifest {
  id?: unknown;
  version?: unknown;
  minAppVersion?: unknown;
  isDesktopOnly?: unknown;
}

const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

function parseVersion(value: string): [number, number, number] | null {
  const match = value.match(VERSION);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function compareVersions(left: string, right: string): number | null {
  const a = parseVersion(left);
  const b = parseVersion(right);
  if (!a || !b) return null;
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) return a[index] < b[index] ? -1 : 1;
  }
  return 0;
}

/**
 * Downloads only the allowlisted release assets into memory, verifies their
 * SHA-256 digests against GitHub's published asset digests, and validates the
 * manifest. It does not write to the vault or execute downloaded code.
 */
export async function verifyLatestReleaseAssets(
  release: ReleaseInspection,
  expectedPluginId: string,
  obsidianVersion: string,
): Promise<AssetVerificationReport> {
  const reasons: string[] = [];
  if (!release.ok || !release.tag || !release.installable) {
    return { verified: false, manifest: null, reasons: ["Release metadata has not passed its safety checks."] };
  }

  const manifestAsset = release.assets.find((asset) => asset.name === "manifest.json");
  if (!manifestAsset) {
    return { verified: false, manifest: null, reasons: ["manifest.json is missing."] };
  }

  let manifest: PluginManifest | null = null;
  for (const asset of release.assets) {
    if (!asset.digestVerified || !asset.digest || !/^sha256:[a-f0-9]{64}$/i.test(asset.digest)) {
      reasons.push(`${asset.name}: no valid SHA-256 digest metadata.`);
      continue;
    }
    const response = await requestUrl({
      url: asset.downloadUrl,
      headers: { Accept: "application/octet-stream" },
      throw: false,
    });
    if (response.status < 200 || response.status >= 300) {
      reasons.push(`${asset.name}: download failed with HTTP ${response.status}.`);
      continue;
    }
    const bytes = response.arrayBuffer;
    if (bytes.byteLength !== asset.size) {
      reasons.push(`${asset.name}: downloaded size does not match GitHub metadata.`);
      continue;
    }
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    if (actual.toLowerCase() !== asset.digest.slice("sha256:".length).toLowerCase()) {
      reasons.push(`${asset.name}: SHA-256 digest mismatch.`);
      continue;
    }
    if (asset.name === "manifest.json") {
      try {
        const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("Manifest must be a JSON object.");
        }
        manifest = parsed as PluginManifest;
      } catch (error) {
        reasons.push(error instanceof Error ? error.message : "manifest.json is invalid JSON.");
      }
    }
  }

  if (!manifest) {
    reasons.push("A digest-verified manifest could not be read.");
    return { verified: false, manifest: null, reasons };
  }
  if (manifest.id !== expectedPluginId) reasons.push("Manifest plugin ID does not match the catalogue entry.");
  if (typeof manifest.version !== "string" || manifest.version.replace(/^v/, "") !== release.version) {
    reasons.push("Manifest version does not match the selected GitHub release tag.");
  }
  if (typeof manifest.minAppVersion !== "string" || !parseVersion(manifest.minAppVersion)) {
    reasons.push("Manifest minAppVersion is missing or invalid.");
  } else {
    const comparison = compareVersions(obsidianVersion, manifest.minAppVersion);
    if (comparison === null) reasons.push("Obsidian or minAppVersion is not a supported semantic version.");
    else if (comparison < 0) reasons.push(`Requires Obsidian ${manifest.minAppVersion} or newer.`);
  }
  if (manifest.isDesktopOnly !== false) {
    reasons.push("Manifest does not explicitly declare isDesktopOnly: false.");
  }

  return {
    verified: reasons.length === 0,
    manifest: reasons.length === 0 ? {
      id: manifest.id as string,
      version: manifest.version as string,
      minAppVersion: manifest.minAppVersion as string,
    } : null,
    reasons,
  };
}
