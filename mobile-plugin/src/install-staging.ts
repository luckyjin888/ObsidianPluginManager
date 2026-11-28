import type { InstallPlan, PlannedInstallAsset } from "./install-transaction";

/**
 * P4.4.2 — isolated staging transaction.
 *
 * Writes only beneath a manager-owned staging directory. It never changes the
 * live plugin directory, never enables a plugin, and never removes user data.
 * The caller must obtain explicit confirmation before invoking this helper.
 */
export interface InstallStagingAdapter {
  exists(path: string): Promise<boolean>;
  mkdir(path: string): Promise<void>;
  writeBinary(path: string, data: ArrayBuffer): Promise<void>;
  readBinary(path: string): Promise<ArrayBuffer>;
  remove(path: string): Promise<void>;
}

export interface StageInstallInput {
  adapter: InstallStagingAdapter;
  plan: InstallPlan;
  transactionId: string;
  confirmed: boolean;
}

export interface StagedInstallFile {
  name: PlannedInstallAsset["name"];
  path: string;
  byteLength: number;
  sha256: string;
}

export type StageInstallResult =
  | { status: "staged"; stagingDirectory: string; files: StagedInstallFile[] }
  | { status: "blocked"; reason: string }
  | { status: "failed"; reason: string; leftoverPaths: string[] };

const SAFE_PLUGIN_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SAFE_TRANSACTION_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const ALLOWED = new Set(["manifest.json", "main.js", "styles.css"]);

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", toArrayBuffer(bytes));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function validPlan(plan: InstallPlan): boolean {
  if (!SAFE_PLUGIN_ID.test(plan.pluginId) || plan.pluginId.includes("obsidian") || plan.pluginId.endsWith("plugin")) return false;
  if (typeof plan.targetDirectory !== "string" || plan.targetDirectory.includes("\\") || plan.targetDirectory.includes(String.fromCharCode(0))) return false;
  const parts = plan.targetDirectory.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return false;
  return parts.length >= 3 && parts[parts.length - 2] === "plugins" && parts[parts.length - 1] === plan.pluginId;
}

/**
 * Creates and verifies a complete staged copy of the plan's exact bytes.
 * Existing staging paths are never overwritten. The live target is untouched.
 */
export async function stageInstallPlan(input: StageInstallInput): Promise<StageInstallResult> {
  if (!input.confirmed) return { status: "blocked", reason: "Explicit user confirmation is required before staging." };
  if (!SAFE_TRANSACTION_ID.test(input.transactionId)) return { status: "blocked", reason: "Transaction ID is unsafe." };
  if (!validPlan(input.plan)) return { status: "blocked", reason: "Install plan target path or plugin ID is invalid." };

  const names = input.plan.assets.map((asset) => asset.name);
  if (new Set(names).size !== names.length || names.some((name) => !ALLOWED.has(name))) {
    return { status: "blocked", reason: "Install plan contains duplicate or non-allowlisted assets." };
  }
  if (!names.includes("manifest.json") || !names.includes("main.js")) {
    return { status: "blocked", reason: "Install plan is missing a required runtime asset." };
  }

  const targetParts = input.plan.targetDirectory.split("/");
  const configDir = targetParts.slice(0, -2).join("/");
  const stagingDirectory = `${configDir}/plugins/.plugin-manager-staging/${input.plan.pluginId}/${input.transactionId}`;
  const directories = stagingDirectory.split("/");
  const createdDirectories: string[] = [];
  const writtenFiles: string[] = [];

  try {
    if (await input.adapter.exists(stagingDirectory)) {
      return { status: "blocked", reason: "This staging transaction already exists; refusing to overwrite it." };
    }

    let current = "";
    for (const part of directories) {
      current = current ? `${current}/${part}` : part;
      if (!(await input.adapter.exists(current))) {
        await input.adapter.mkdir(current);
        createdDirectories.push(current);
      }
    }

    const staged: StagedInstallFile[] = [];
    for (const asset of input.plan.assets) {
      if (!(asset.bytes instanceof Uint8Array)) throw new Error(`${asset.name}: staged input is not byte data.`);
      const digest = await sha256Hex(asset.bytes);
      if (digest.toLowerCase() !== asset.sha256.toLowerCase()) throw new Error(`${asset.name}: install-plan bytes changed before staging.`);

      const path = `${stagingDirectory}/${asset.name}`;
      await input.adapter.writeBinary(path, toArrayBuffer(asset.bytes));
      writtenFiles.push(path);

      const readBack = new Uint8Array(await input.adapter.readBinary(path));
      const readBackDigest = await sha256Hex(readBack);
      if (readBack.byteLength !== asset.bytes.byteLength || readBackDigest !== digest) {
        throw new Error(`${asset.name}: staged read-back verification failed.`);
      }
      staged.push({ name: asset.name, path, byteLength: readBack.byteLength, sha256: readBackDigest });
    }

    return { status: "staged", stagingDirectory, files: staged };
  } catch (error) {
    const leftoverPaths: string[] = [];
    for (const path of [...writtenFiles].reverse()) {
      try {
        if (await input.adapter.exists(path)) await input.adapter.remove(path);
      } catch {
        leftoverPaths.push(path);
      }
    }
    for (const path of [...createdDirectories].reverse()) {
      try {
        if (await input.adapter.exists(path)) await input.adapter.remove(path);
      } catch {
        leftoverPaths.push(path);
      }
    }
    return {
      status: "failed",
      reason: error instanceof Error ? error.message : "Unknown staging failure.",
      leftoverPaths,
    };
  }
}
