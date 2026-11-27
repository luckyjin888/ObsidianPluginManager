import type { TFile, Vault } from "obsidian";
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
  if (typeof item.created_at !== "string" || !/^\\d{4}-\\d{2}-\\d{2}T/.test(item.created_at) ||
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
