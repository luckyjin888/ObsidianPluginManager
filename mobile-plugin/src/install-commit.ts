import type { Vault } from "obsidian";
import type { InstallPlan } from "./install-transaction";
import type { StagedInstallFile } from "./install-staging";

const ALLOWED = new Set(["manifest.json", "main.js", "styles.css"]);
const SAFE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SAFE_TX = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const BACKUP_ROOT = "PluginManager/install-backups";

export interface InstallCommitAdapter {
  exists(path: string): Promise<boolean>;
  mkdir(path: string): Promise<void>;
  readBinary(path: string): Promise<ArrayBuffer>;
  writeBinary(path: string, data: ArrayBuffer): Promise<void>;
  remove(path: string): Promise<void>;
}

export type InstallCommitResult =
  | { status: "installed"; backupDirectory: string; installedFiles: string[] }
  | { status: "blocked"; reason: string }
  | { status: "failed"; reason: string; rollback: "restored" | "failed" | "not-needed"; backupDirectory: string; rollbackFailures: string[] };

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function digest(bytes: Uint8Array): Promise<string> {
  const value = await globalThis.crypto.subtle.digest("SHA-256", toArrayBuffer(bytes));
  return Array.from(new Uint8Array(value), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function validTarget(plan: InstallPlan, staged: StagedInstallFile[], transactionId: string, stagingDirectory: string): boolean {
  if (!SAFE_ID.test(plan.pluginId) || !SAFE_TX.test(transactionId)) return false;
  if (plan.pluginId.includes("obsidian") || plan.pluginId.endsWith("plugin")) return false;
  const target = plan.targetDirectory.split("/");
  if (target.some((part) => !part || part === "." || part === "..") ||
      target[target.length - 2] !== "plugins" || target[target.length - 1] !== plan.pluginId) return false;
  const expected = `${target.slice(0, -2).join("/")}/plugins/.plugin-manager-staging/${plan.pluginId}/${transactionId}`;
  if (stagingDirectory !== expected) return false;
  if (staged.length !== plan.assets.length || staged.length < 2) return false;
  const names = new Set<string>();
  for (const file of staged) {
    if (!ALLOWED.has(file.name) || names.has(file.name)) return false;
    names.add(file.name);
  }
  return names.has("manifest.json") && names.has("main.js");
}

async function ensureDirectory(adapter: InstallCommitAdapter, path: string): Promise<void> {
  let current = "";
  for (const part of path.split("/")) {
    current = current ? `${current}/${part}` : part;
    if (!(await adapter.exists(current))) await adapter.mkdir(current);
  }
}

/**
 * P4.4.3–P4.4.5 guarded live-file transaction.
 *
 * The caller must obtain explicit user confirmation before calling this
 * function. All existing allowlisted target files are backed up and verified
 * before the first live write. Only manifest.json, main.js and styles.css are
 * ever replaced; data.json, settings, unknown files and enablement are untouched.
 * A failed replacement triggers a conditional best-effort rollback of only
 * files attempted by this transaction. The verified backup is retained.
 */
export async function commitStagedInstall(
  adapter: InstallCommitAdapter,
  plan: InstallPlan,
  staged: StagedInstallFile[],
  stagingDirectory: string,
  transactionId: string,
  explicitlyConfirmed: boolean,
  createdAt: string,
): Promise<InstallCommitResult> {
  if (!explicitlyConfirmed) return { status: "blocked", reason: "Explicit user confirmation is required." };
  if (!Number.isFinite(Date.parse(createdAt))) return { status: "blocked", reason: "Transaction timestamp is invalid." };
  if (!validTarget(plan, staged, transactionId, stagingDirectory)) {
    return { status: "blocked", reason: "Plan, staging directory, transaction ID, or staged asset list is invalid." };
  }

  const backupDirectory = `${BACKUP_ROOT}/${plan.pluginId}/${transactionId}`;
  const backupManifestPath = `${backupDirectory}/backup-manifest.json`;
  const stagedByName = new Map(staged.map((item) => [item.name, item]));
  const originals = new Map<string, Uint8Array>();
  const attempted: string[] = [];

  try {
    if (await adapter.exists(backupDirectory)) {
      return { status: "blocked", reason: "Backup transaction already exists; refusing to overwrite it." };
    }

    // Validate staged bytes before reading or backing up live target files.
    for (const item of staged) {
      const planned = plan.assets.find((asset) => asset.name === item.name);
      if (!planned || item.byteLength !== planned.bytes.byteLength ||
          item.sha256.toLowerCase() !== planned.sha256.toLowerCase()) {
        return { status: "blocked", reason: `Staging metadata does not match install plan for ${item.name}.` };
      }
      const stagedBytes = new Uint8Array(await adapter.readBinary(item.path));
      if (stagedBytes.byteLength !== item.byteLength || await digest(stagedBytes) !== item.sha256) {
        return { status: "blocked", reason: `Staged file failed integrity verification: ${item.name}.` };
      }
    }

    // Capture all original target files before any replacement.
    for (const item of staged) {
      const targetPath = `${plan.targetDirectory}/${item.name}`;
      if (await adapter.exists(targetPath)) originals.set(item.name, new Uint8Array(await adapter.readBinary(targetPath)));
    }

    await ensureDirectory(adapter, backupDirectory);
    const backupRecords: Array<{ name: string; byteLength: number; sha256: string }> = [];
    for (const [name, bytes] of originals) {
      const backupPath = `${backupDirectory}/${name}`;
      await adapter.writeBinary(backupPath, toArrayBuffer(bytes));
      const readBack = new Uint8Array(await adapter.readBinary(backupPath));
      const sha256 = await digest(bytes);
      if (readBack.byteLength !== bytes.byteLength || await digest(readBack) !== sha256) {
        throw new Error(`Backup read-back verification failed for ${name}.`);
      }
      backupRecords.push({ name, byteLength: bytes.byteLength, sha256 });
    }
    const backupManifest = new TextEncoder().encode(JSON.stringify({
      schema_version: 1,
      plugin_id: plan.pluginId,
      release_version: plan.releaseVersion,
      target_directory: plan.targetDirectory,
      transaction_id: transactionId,
      created_at: createdAt,
      files: backupRecords,
    }, null, 2) + "\n");
    await adapter.writeBinary(backupManifestPath, toArrayBuffer(backupManifest));
    const manifestReadBack = new Uint8Array(await adapter.readBinary(backupManifestPath));
    if (await digest(manifestReadBack) !== await digest(backupManifest)) {
      throw new Error("Backup manifest read-back verification failed.");
    }

    // Create the plugin folder only after the backup envelope is safely persisted.
    await ensureDirectory(adapter, plan.targetDirectory);

    // Commit verified staged assets. The backup is complete before this loop.
    for (const item of staged) {
      const targetPath = `${plan.targetDirectory}/${item.name}`;
      attempted.push(targetPath);
      const bytes = new Uint8Array(await adapter.readBinary(item.path));
      await adapter.writeBinary(targetPath, toArrayBuffer(bytes));
      const readBack = new Uint8Array(await adapter.readBinary(targetPath));
      if (readBack.byteLength !== item.byteLength || await digest(readBack) !== item.sha256) {
        throw new Error(`Live target read-back verification failed for ${item.name}.`);
      }
    }

    return {
      status: "installed",
      backupDirectory,
      installedFiles: staged.map((item) => item.name),
    };
  } catch (error) {
    const rollbackFailures: string[] = [];
    for (const targetPath of [...attempted].reverse()) {
      const name = targetPath.slice(plan.targetDirectory.length + 1);
      try {
        const original = originals.get(name);
        if (original) {
          await adapter.writeBinary(targetPath, toArrayBuffer(original));
          const actual = new Uint8Array(await adapter.readBinary(targetPath));
          if (actual.byteLength !== original.byteLength || await digest(actual) !== await digest(original)) {
            rollbackFailures.push(targetPath);
          }
        } else if (await adapter.exists(targetPath)) {
          await adapter.remove(targetPath);
          if (await adapter.exists(targetPath)) rollbackFailures.push(targetPath);
        }
      } catch {
        rollbackFailures.push(targetPath);
      }
    }
    return {
      status: "failed",
      reason: error instanceof Error ? error.message : "Unknown installation transaction failure.",
      rollback: attempted.length === 0 ? "not-needed" : rollbackFailures.length === 0 ? "restored" : "failed",
      backupDirectory,
      rollbackFailures,
    };
  }
}

/** Public Obsidian DataAdapter adapter; supports hidden configDir paths. */
export function createObsidianInstallCommitAdapter(
  adapter: Pick<Vault["adapter"], "exists" | "mkdir" | "readBinary" | "writeBinary" | "remove">,
): InstallCommitAdapter {
  return {
    exists: (path) => adapter.exists(path),
    mkdir: (path) => adapter.mkdir(path),
    readBinary: (path) => adapter.readBinary(path),
    writeBinary: (path, data) => adapter.writeBinary(path, data),
    remove: (path) => adapter.remove(path),
  };
}
