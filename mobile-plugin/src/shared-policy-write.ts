import type { TFile, TFolder, Vault } from "obsidian";
import { parseSharedPluginPolicy } from "./shared-policy";

/**
 * Minimal public-Vault surface used by the guarded policy writer.
 * This helper is intentionally not wired to any command or UI.
 */
export interface SharedPolicyVaultProcessAdapter<TFileLike> {
  process(file: TFileLike, fn: (current: string) => string): Promise<unknown>;
  read(file: TFileLike): Promise<string>;
}

/**
 * Thin adapter over the documented Obsidian Vault API. Vault.process() returns
 * a Promise<string> in the public API; Promise<unknown> in the port keeps the
 * helper independent from that concrete return value.
 */
export function createObsidianVaultPolicyAdapter(
  vault: Pick<Vault, "process" | "read">,
): SharedPolicyVaultProcessAdapter<TFile> {
  return {
    process: (file, callback) => vault.process(file, callback),
    read: (file) => vault.read(file),
  };
}

export interface SharedPolicyBackupVaultAdapter<TFileLike> {
  folderExists(path: string): boolean;
  createFolder(path: string): Promise<unknown>;
  getFile(path: string): TFileLike | null;
  create(path: string, content: string): Promise<TFileLike>;
  read(file: TFileLike): Promise<string>;
  listFiles(): Array<{ path: string; file: TFileLike; size: number }>;
}

/** Public Obsidian Vault adapter for creating new backup files without overwriting. */
function isVaultFolder(item: unknown): item is TFolder {
  return typeof item === "object" && item !== null &&
    Array.isArray((item as TFolder).children);
}

function isVaultFile(item: unknown): item is TFile {
  return typeof item === "object" && item !== null &&
    typeof (item as TFile).extension === "string" &&
    typeof (item as TFile).stat === "object";
}

export function createObsidianVaultBackupAdapter(
  vault: Pick<Vault, "getAbstractFileByPath" | "createFolder" | "create" | "read">,
): SharedPolicyBackupVaultAdapter<TFile> {
  return {
    folderExists: (path) => isVaultFolder(vault.getAbstractFileByPath(path)),
    createFolder: (path) => vault.createFolder(path),
    getFile: (path) => {
      const item = vault.getAbstractFileByPath(path);
      return isVaultFile(item) ? item : null;
    },
    create: (path, content) => vault.create(path, content),
    read: (file) => vault.read(file),
    listFiles: () => {
      const folder = vault.getAbstractFileByPath(SHARED_POLICY_BACKUP_DIRECTORY);
      if (!isVaultFolder(folder)) return [];
      return folder.children
        .filter(isVaultFile)
        .map((file) => ({ path: file.path, file, size: file.stat.size }));
    },
  };
}

export type SharedPolicyWriteResult =
  | { status: "written" }
  | { status: "stale"; current: string }
  | { status: "invalid-candidate"; errors: string[] }
  | { status: "verification-failed"; actual: string }
  | { status: "failed"; message: string };

/**
 * Applies a previously reviewed candidate only if Vault.process observes the
 * exact baseline text. This is local stale-write protection, not a distributed
 * lock. Callers must obtain baseline with Vault.cachedRead() before review.
 *
 * Not exposed in the UI: adapter tests and fault-injection must pass before a
 * user-facing write action is considered.
 */
export async function writeSharedPolicyWithBaseline<TFileLike>(
  vault: SharedPolicyVaultProcessAdapter<TFileLike>,
  file: TFileLike,
  baseline: string,
  candidate: string,
): Promise<SharedPolicyWriteResult> {
  const validation = parseSharedPluginPolicy(candidate);
  if (!validation.ok || !validation.policy) {
    return { status: "invalid-candidate", errors: validation.errors };
  }

  let callbackInvoked = false;
  let staleCurrent: string | null = null;
  try {
    await vault.process(file, (current) => {
      callbackInvoked = true;
      if (current !== baseline) {
        staleCurrent = current;
        return current;
      }
      return candidate;
    });
    if (!callbackInvoked) {
      return { status: "failed", message: "Vault.process completed without invoking its callback." };
    }
    if (staleCurrent !== null) return { status: "stale", current: staleCurrent };

    const actual = await vault.read(file);
    if (actual !== candidate) return { status: "verification-failed", actual };
    return { status: "written" };
  } catch (error) {
    return {
      status: "failed",
      message: error instanceof Error ? error.message : "Unknown Vault process/read failure.",
    };
  }
}


export const SHARED_POLICY_BACKUP_DIRECTORY = "PluginManager/backups";
export const MAX_SHARED_POLICY_BACKUP_BYTES = 128 * 1024;

export interface SharedPolicyBackupEnvelope {
  schema_version: 1;
  target_path: string;
  created_at: string;
  original_content: string;
  original_sha256: string;
}

export type SharedPolicyBackupValidation =
  | { ok: true; backup: SharedPolicyBackupEnvelope }
  | { ok: false; errors: string[] };

/**
 * Creates a deterministic, checksummed recovery envelope in memory.
 * The caller must persist it separately and verify it before mutating the
 * primary policy. This function does not create folders or write Vault files.
 */
export async function createSharedPolicyBackupEnvelope(
  originalContent: string,
  createdAt: string,
): Promise<SharedPolicyBackupEnvelope> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(originalContent),
  );
  const original_sha256 = Array.from(
    new Uint8Array(digest),
    (byte) => byte.toString(16).padStart(2, "0"),
  ).join("");
  return {
    schema_version: 1,
    target_path: "PluginManager/shared-policy.json",
    created_at: createdAt,
    original_content: originalContent,
    original_sha256,
  };
}

/** Strictly validates a backup envelope and its exact original bytes. */
export async function validateSharedPolicyBackupEnvelope(
  raw: string,
): Promise<SharedPolicyBackupValidation> {
  if (new TextEncoder().encode(raw).byteLength > MAX_SHARED_POLICY_BACKUP_BYTES) {
    return { ok: false, errors: ["Backup exceeds the 128 KiB size limit."] };
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { ok: false, errors: ["Backup is not valid JSON."] };
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ok: false, errors: ["Backup root must be an object."] };
  }
  const item = value as Record<string, unknown>;
  if (Object.keys(item).sort().join(",") !== "created_at,original_content,original_sha256,schema_version,target_path") {
    return { ok: false, errors: ["Backup has missing or unsupported fields."] };
  }
  if (item.schema_version !== 1 || item.target_path !== "PluginManager/shared-policy.json") {
    return { ok: false, errors: ["Backup schema or target path is unsupported."] };
  }
  if (typeof item.created_at !== "string" || !/^\d{4}-\d{2}-\d{2}T/.test(item.created_at) ||
      !Number.isFinite(Date.parse(item.created_at))) {
    return { ok: false, errors: ["Backup created_at must be a valid ISO timestamp."] };
  }
  if (typeof item.original_content !== "string" || typeof item.original_sha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(item.original_sha256)) {
    return { ok: false, errors: ["Backup content or SHA-256 digest is invalid."] };
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(item.original_content),
  );
  const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actual !== item.original_sha256) {
    return { ok: false, errors: ["Backup content does not match its SHA-256 digest."] };
  }
  return {
    ok: true,
    backup: {
      schema_version: 1,
      target_path: "PluginManager/shared-policy.json",
      created_at: item.created_at,
      original_content: item.original_content,
      original_sha256: item.original_sha256,
    },
  };
}

/** Stable filename component; caller supplies an ISO timestamp and verified digest. */
export function buildSharedPolicyBackupFileName(createdAt: string, sha256: string): string | null {
  if (!Number.isFinite(Date.parse(createdAt)) || !/^[a-f0-9]{64}$/.test(sha256)) return null;
  const stamp = createdAt.replace(/[^0-9TZ]/g, "-");
  return `shared-policy-${stamp}-${sha256.slice(0, 12)}.backup.json`;
}


export type SharedPolicyBackupPersistResult =
  | { status: "created"; path: string }
  | { status: "already-exists"; path: string }
  | { status: "failed"; message: string }
  | { status: "verification-failed"; path: string; message: string };

/**
 * Persist a new immutable backup file, then read it back and validate exact
 * serialized content. Existing paths are never overwritten. This confirms
 * Vault-level read-back only; it does not prove remote sync durability.
 */
export async function persistSharedPolicyBackup<TFileLike>(
  vault: SharedPolicyBackupVaultAdapter<TFileLike>,
  originalContent: string,
  createdAt: string,
): Promise<SharedPolicyBackupPersistResult> {
  try {
    const envelope = await createSharedPolicyBackupEnvelope(originalContent, createdAt);
    const serialized = JSON.stringify(envelope, null, 2) + "\n";
    if (new TextEncoder().encode(serialized).byteLength > MAX_SHARED_POLICY_BACKUP_BYTES) {
      return { status: "failed", message: "Backup exceeds the 128 KiB size limit." };
    }
    const fileName = buildSharedPolicyBackupFileName(createdAt, envelope.original_sha256);
    if (!fileName) return { status: "failed", message: "Backup timestamp or digest is invalid." };
    if (!vault.folderExists(SHARED_POLICY_BACKUP_DIRECTORY)) {
      await vault.createFolder(SHARED_POLICY_BACKUP_DIRECTORY);
    }
    const path = `${SHARED_POLICY_BACKUP_DIRECTORY}/${fileName}`;
    const existing = vault.getFile(path);
    if (existing) {
      const existingRaw = await vault.read(existing);
      if (existingRaw === serialized) return { status: "already-exists", path };
      return { status: "failed", message: "Backup path already exists with different content; it was not overwritten." };
    }
    const created = await vault.create(path, serialized);
    const actual = await vault.read(created);
    const checked = await validateSharedPolicyBackupEnvelope(actual);
    if (actual !== serialized || !checked.ok || checked.backup.original_content !== originalContent) {
      return {
        status: "verification-failed",
        path,
        message: "Created backup could not be read back byte-for-byte and validated. The file was preserved for inspection.",
      };
    }
    return { status: "created", path };
  } catch (error) {
    return {
      status: "failed",
      message: error instanceof Error ? error.message : "Unknown backup persistence failure.",
    };
  }
}


export type SharedPolicyBackupScanItem =
  | { status: "valid"; path: string; size: number; backup: SharedPolicyBackupEnvelope; policyValid: true }
  | { status: "invalid-policy"; path: string; size: number; backup: SharedPolicyBackupEnvelope; policyErrors: string[] }
  | { status: "invalid-backup"; path: string; size: number; errors: string[] }
  | { status: "oversized"; path: string; size: number; errors: string[] };

/**
 * Read-only scan of backup files. It never changes the Vault and preserves
 * invalid/oversized entries as visible diagnostics rather than skipping them.
 */
export async function scanSharedPolicyBackups<TFileLike>(
  vault: SharedPolicyBackupVaultAdapter<TFileLike>,
): Promise<SharedPolicyBackupScanItem[]> {
  let files: Array<{ path: string; file: TFileLike; size: number }>;
  try {
    files = vault.listFiles().sort((a, b) => b.path.localeCompare(a.path));
  } catch {
    return [{
      status: "invalid-backup",
      path: SHARED_POLICY_BACKUP_DIRECTORY,
      size: 0,
      errors: ["Backup directory could not be listed."],
    }];
  }
  const results: SharedPolicyBackupScanItem[] = [];
  for (const entry of files) {
    if (entry.size > MAX_SHARED_POLICY_BACKUP_BYTES) {
      results.push({
        status: "oversized",
        path: entry.path,
        size: entry.size,
        errors: ["Backup exceeds the 128 KiB scan limit; it was not read."],
      });
      continue;
    }
    try {
      const raw = await vault.read(entry.file);
      const checked = await validateSharedPolicyBackupEnvelope(raw);
      if (!checked.ok) {
        results.push({
          status: "invalid-backup",
          path: entry.path,
          size: entry.size,
          errors: checked.errors,
        });
        continue;
      }
      const policy = parseSharedPluginPolicy(checked.backup.original_content);
      if (!policy.ok || !policy.policy) {
        results.push({
          status: "invalid-policy",
          path: entry.path,
          size: entry.size,
          backup: checked.backup,
          policyErrors: policy.errors,
        });
        continue;
      }
      results.push({
        status: "valid",
        path: entry.path,
        size: entry.size,
        backup: checked.backup,
        policyValid: true,
      });
    } catch (error) {
      results.push({
        status: "invalid-backup",
        path: entry.path,
        size: entry.size,
        errors: [error instanceof Error ? error.message : "Backup read failed."],
      });
    }
  }
  return results;
}

export type SharedPolicyRestorePreviewResult =
  | { status: "ready"; target_path: string; backup_created_at: string; backup_sha256: string; restored_policy_revision: string; restored_plugin_count: number; restore_content: string }
  | { status: "stale"; message: string }
  | { status: "invalid-backup"; errors: string[] }
  | { status: "invalid-policy"; errors: string[] };

/**
 * Builds a restore preview only. The caller supplies the exact current content
 * captured when the user began reviewing and the freshly re-read content.
 * Any intervening edit (including missing/present transitions) blocks preview.
 * This function never writes or creates a Vault file.
 */
export async function prepareSharedPolicyRestorePreview(
  backup: SharedPolicyBackupEnvelope,
  reviewedCurrentContent: string | null,
  currentContentNow: string | null,
): Promise<SharedPolicyRestorePreviewResult> {
  if (reviewedCurrentContent !== currentContentNow) {
    return {
      status: "stale",
      message: "The current shared policy changed after it was reviewed. Reload and compare again before considering recovery.",
    };
  }
  const checked = await validateSharedPolicyBackupEnvelope(JSON.stringify(backup));
  if (!checked.ok) return { status: "invalid-backup", errors: checked.errors };
  const parsed = parseSharedPluginPolicy(checked.backup.original_content);
  if (!parsed.ok || !parsed.policy) {
    return { status: "invalid-policy", errors: parsed.errors };
  }
  return {
    status: "ready",
    target_path: checked.backup.target_path,
    backup_created_at: checked.backup.created_at,
    backup_sha256: checked.backup.original_sha256,
    restored_policy_revision: parsed.policy.revision,
    restored_plugin_count: parsed.policy.plugins.length,
    restore_content: checked.backup.original_content,
  };
}

export type SharedPolicyRestoreTransactionResult =
  | { status: "restored"; backup_path: string }
  | { status: "confirmation-required" }
  | { status: "stale"; current: string; backup_path?: string }
  | { status: "backup-failed"; result: SharedPolicyBackupPersistResult }
  | { status: "invalid-backup"; errors: string[] }
  | { status: "invalid-policy"; errors: string[] }
  | { status: "write-failed"; message: string; backup_path: string }
  | { status: "verification-failed"; actual: string; backup_path: string; rollback: "restored" | "failed" | "not-needed" }
  | { status: "rollback-failed"; message: string; backup_path: string };

/**
 * Executes an explicitly confirmed restore of an existing policy file.
 * A verified backup of the exact current bytes is persisted before the write.
 * Vault.process performs the final local baseline comparison. If post-write
 * verification fails, a best-effort rollback is attempted only if the file
 * still contains the restore candidate; concurrent content is never replaced.
 *
 * This remains an isolated helper: it is not wired to UI/commands and does not
 * provide cross-device compare-and-swap or remote sync durability.
 */
export async function restoreSharedPolicyWithBackup<TFileLike>(
  policyVault: SharedPolicyVaultProcessAdapter<TFileLike>,
  backupVault: SharedPolicyBackupVaultAdapter<TFileLike>,
  file: TFileLike,
  selectedBackup: SharedPolicyBackupEnvelope,
  reviewedCurrentContent: string,
  currentContentNow: string,
  createdAt: string,
  explicitlyConfirmed: boolean,
): Promise<SharedPolicyRestoreTransactionResult> {
  if (!explicitlyConfirmed) return { status: "confirmation-required" };
  if (reviewedCurrentContent !== currentContentNow) {
    return { status: "stale", current: currentContentNow };
  }

  const checked = await validateSharedPolicyBackupEnvelope(JSON.stringify(selectedBackup));
  if (!checked.ok) return { status: "invalid-backup", errors: checked.errors };
  const restorePolicy = parseSharedPluginPolicy(checked.backup.original_content);
  if (!restorePolicy.ok || !restorePolicy.policy) {
    return { status: "invalid-policy", errors: restorePolicy.errors };
  }

  const currentBackup = await persistSharedPolicyBackup(backupVault, reviewedCurrentContent, createdAt);
  if (currentBackup.status !== "created" && currentBackup.status !== "already-exists") {
    return { status: "backup-failed", result: currentBackup };
  }

  let callbackInvoked = false;
  let staleCurrent: string | null = null;
  try {
    await policyVault.process(file, (current) => {
      callbackInvoked = true;
      if (current !== reviewedCurrentContent) {
        staleCurrent = current;
        return current;
      }
      return checked.backup.original_content;
    });
    if (!callbackInvoked) {
      return { status: "write-failed", message: "Vault.process completed without invoking its callback.", backup_path: currentBackup.path };
    }
    if (staleCurrent !== null) {
      return { status: "stale", current: staleCurrent, backup_path: currentBackup.path };
    }

    const actual = await policyVault.read(file);
    if (actual === checked.backup.original_content) {
      return { status: "restored", backup_path: currentBackup.path };
    }

    let rollbackInvoked = false;
    let rollbackStale = false;
    try {
      await policyVault.process(file, (current) => {
        rollbackInvoked = true;
        if (current !== checked.backup.original_content) {
          rollbackStale = true;
          return current;
        }
        return reviewedCurrentContent;
      });
      if (!rollbackInvoked || rollbackStale) {
        return {
          status: "verification-failed",
          actual,
          backup_path: currentBackup.path,
          rollback: "failed",
        };
      }
      const afterRollback = await policyVault.read(file);
      return {
        status: "verification-failed",
        actual,
        backup_path: currentBackup.path,
        rollback: afterRollback === reviewedCurrentContent ? "restored" : "failed",
      };
    } catch {
      return {
        status: "verification-failed",
        actual,
        backup_path: currentBackup.path,
        rollback: "failed",
      };
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown restore write/read failure.";
    // A process/read exception may occur after the adapter has already changed
    // the file. Re-read before deciding whether a conditional rollback is safe.
    try {
      const afterFailure = await policyVault.read(file);
      if (afterFailure === checked.backup.original_content) {
        let rollbackInvoked = false;
        let rollbackStale = false;
        await policyVault.process(file, (current) => {
          rollbackInvoked = true;
          if (current !== checked.backup.original_content) {
            rollbackStale = true;
            return current;
          }
          return reviewedCurrentContent;
        });
        if (!rollbackInvoked || rollbackStale) {
          return { status: "rollback-failed", message, backup_path: currentBackup.path };
        }
        const verifiedRollback = await policyVault.read(file);
        if (verifiedRollback !== reviewedCurrentContent) {
          return { status: "rollback-failed", message, backup_path: currentBackup.path };
        }
        return {
          status: "verification-failed",
          actual: afterFailure,
          backup_path: currentBackup.path,
          rollback: "restored",
        };
      }
      return {
        status: "write-failed",
        message,
        backup_path: currentBackup.path,
      };
    } catch {
      return { status: "rollback-failed", message, backup_path: currentBackup.path };
    }
  }
}
