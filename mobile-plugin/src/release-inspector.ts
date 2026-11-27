import { requestUrl } from "obsidian";

export interface ReleaseAssetInspection {
  name: string;
  size: number;
  digest: string | null;
  digestVerified: boolean;
  downloadUrl: string;
}

export interface ReleaseInspection {
  ok: boolean;
  installable: boolean;
  repository: string;
  tag: string | null;
  version: string | null;
  htmlUrl: string | null;
  assets: ReleaseAssetInspection[];
  reasons: string[];
}

interface GitHubReleaseAsset {
  name?: unknown;
  size?: unknown;
  digest?: unknown;
  browser_download_url?: unknown;
}

interface GitHubRelease {
  tag_name?: unknown;
  draft?: unknown;
  prerelease?: unknown;
  html_url?: unknown;
  assets?: unknown;
}

const MAX_SIZES: Record<string, number> = {
  "manifest.json": 256 * 1024,
  "main.js": 20 * 1024 * 1024,
  "styles.css": 2 * 1024 * 1024,
};
const MAX_TOTAL_SIZE = 25 * 1024 * 1024;
const SEMVER = /^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseRepository(repositoryUrl: string): { owner: string; repo: string } {
  const url = new URL(repositoryUrl);
  const match = url.pathname.match(/^\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)\/?$/);
  if (
    url.protocol !== "https:" || url.hostname !== "github.com"
    || url.username || url.password || url.search || url.hash || !match
  ) {
    throw new Error("Only a canonical HTTPS github.com/owner/repository URL is accepted.");
  }
  return { owner: match[1], repo: match[2] };
}

function inspectAsset(
  raw: unknown,
  owner: string,
  repo: string,
): ReleaseAssetInspection {
  if (!isRecord(raw)) throw new Error("Release contains an invalid asset record.");
  const asset = raw as GitHubReleaseAsset;
  if (
    typeof asset.name !== "string" || typeof asset.size !== "number"
    || !Number.isSafeInteger(asset.size) || asset.size < 0
    || typeof asset.browser_download_url !== "string"
  ) {
    throw new Error("Release asset is missing a valid name, size, or download URL.");
  }
  const limit = MAX_SIZES[asset.name];
  if (limit === undefined) throw new Error(`Unexpected release asset: ${asset.name}`);
  if (asset.size > limit) throw new Error(`${asset.name} exceeds its configured size limit.`);

  const download = new URL(asset.browser_download_url);
  const expectedPrefix = `/${owner}/${repo}/releases/download/`;
  if (
    download.protocol !== "https:" || download.hostname !== "github.com"
    || download.username || download.password || download.search || download.hash
    || !download.pathname.startsWith(expectedPrefix)
    || download.pathname.split("/").length < 7
  ) {
    throw new Error(`Asset ${asset.name} has an untrusted download URL.`);
  }

  const digest = typeof asset.digest === "string" ? asset.digest : null;
  const digestVerified = digest !== null && /^sha256:[a-f0-9]{64}$/i.test(digest);
  return {
    name: asset.name,
    size: asset.size,
    digest,
    digestVerified,
    downloadUrl: download.toString(),
  };
}

/**
 * Inspects latest GitHub Release metadata only. It never downloads assets or
 * writes to the vault. A release without GitHub's SHA-256 asset digest is
 * inspectable but explicitly not installable.
 */
export async function inspectLatestRelease(repositoryUrl: string): Promise<ReleaseInspection> {
  const { owner, repo } = parseRepository(repositoryUrl);
  const repository = `${owner}/${repo}`;
  const endpoint = `https://api.github.com/repos/${owner}/${repo}/releases/latest`;
  const response = await requestUrl({
    url: endpoint,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    throw: false,
  });

  if (response.status === 404) throw new Error("No published stable GitHub Release was found (HTTP 404).");
  if (response.status === 403 || response.status === 429) {
    throw new Error(`GitHub API rate limit or access restriction (HTTP ${response.status}); retry later.`);
  }
  if (response.status < 200 || response.status >= 300) {
    throw new Error(`GitHub Release lookup failed (HTTP ${response.status}).`);
  }

  const payload: unknown = response.json;
  if (!isRecord(payload)) throw new Error("GitHub returned an invalid release response.");
  const release = payload as GitHubRelease;
  if (release.draft !== false || release.prerelease !== false) {
    throw new Error("Only published, non-draft, non-prerelease releases are accepted.");
  }
  if (typeof release.tag_name !== "string" || !SEMVER.test(release.tag_name)) {
    throw new Error("Latest release tag is not a supported semantic version.");
  }
  if (!Array.isArray(release.assets)) throw new Error("GitHub release asset list is invalid.");

  const assets = release.assets.map((asset) => inspectAsset(asset, owner, repo));
  const names = assets.map((asset) => asset.name);
  if (new Set(names).size !== names.length) throw new Error("Release contains duplicate asset names.");
  if (!names.includes("manifest.json") || !names.includes("main.js")) {
    throw new Error("Release must include both manifest.json and main.js.");
  }
  const totalSize = assets.reduce((sum, asset) => sum + asset.size, 0);
  if (totalSize > MAX_TOTAL_SIZE) throw new Error("Release assets exceed the 25 MiB total size limit.");

  const reasons: string[] = [];
  for (const asset of assets) {
    if (!asset.digestVerified) {
      reasons.push(`${asset.name} has no valid GitHub SHA-256 digest; cryptographic integrity cannot be verified.`);
    }
  }
  return {
    ok: true,
    installable: reasons.length === 0,
    repository,
    tag: release.tag_name,
    version: release.tag_name.replace(/^v/, ""),
    htmlUrl: typeof release.html_url === "string" ? release.html_url : null,
    assets,
    reasons,
  };
}
