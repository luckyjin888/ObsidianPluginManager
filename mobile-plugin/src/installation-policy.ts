import type { RuntimePlatform } from "./platform";

export type CataloguePlatform = "windows" | "macos" | "ios" | "ipados" | "android";
export type CompatibilityStatus = "verified" | "declared_unverified" | "incompatible" | "unknown";

export interface InstallCandidate {
  id: string;
  upstream_url: string | null;
  manifest_is_desktop_only: boolean | null;
  platforms: Record<CataloguePlatform, { status: CompatibilityStatus; evidence: string }>;
}

export interface EligibilityDecision {
  eligible: boolean;
  platform: RuntimePlatform;
  reasons: string[];
}

/**
 * Conservative preflight only. This does not download, write, enable, or install
 * anything. iOS and iPadOS share Obsidian's iOS runtime flag, so both catalogue
 * records must be verified before an iOS-family install can be considered.
 */
export function assessInstallEligibility(
  candidate: InstallCandidate,
  platform: RuntimePlatform,
): EligibilityDecision {
  const reasons: string[] = [];
  const idIsSafe = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(candidate.id)
    && !candidate.id.includes("obsidian")
    && !candidate.id.endsWith("plugin");
  if (!idIsSafe) reasons.push("Plugin ID does not satisfy the safe community-plugin ID rules.");

  let source: URL | null = null;
  try {
    if (!candidate.upstream_url) throw new Error("missing");
    source = new URL(candidate.upstream_url);
  } catch {
    reasons.push("A canonical upstream repository URL is required.");
  }
  if (source && (
    source.protocol !== "https:"
    || source.hostname !== "github.com"
    || source.username !== ""
    || source.password !== ""
    || source.search !== ""
    || source.hash !== ""
    || !/^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(source.pathname)
  )) {
    reasons.push("Only a canonical HTTPS GitHub repository URL is currently allowed.");
  }

  if (platform === "linux" || platform === "other") {
    reasons.push("This runtime platform is not covered by the current five-platform catalogue.");
  } else {
    const requiredPlatforms: CataloguePlatform[] = platform === "ios"
      ? ["ios", "ipados"]
      : [platform];
    for (const key of requiredPlatforms) {
      const status = candidate.platforms[key]?.status ?? "unknown";
      if (status !== "verified") {
        reasons.push(
          platform === "ios"
            ? `Both iOS and iPadOS must be verified; ${key} is ${status}.`
            : `${key} compatibility is ${status}; only verified entries may proceed.`,
        );
      }
    }
  }

  if (candidate.manifest_is_desktop_only === true && (platform === "ios" || platform === "android")) {
    reasons.push("The upstream manifest declares this plugin desktop-only.");
  }

  return { eligible: reasons.length === 0, platform, reasons };
}
