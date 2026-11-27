export const SHARED_POLICY_PATH = "PluginManager/shared-policy.json";
export const MAX_SHARED_POLICY_BYTES = 64 * 1024;
export const MAX_SHARED_POLICY_PLUGINS = 200;

export interface SharedPolicyEntry {
  id: string;
  note?: string;
}

export interface SharedPluginPolicy {
  schema_version: 1;
  revision: string;
  plugins: SharedPolicyEntry[];
}

export interface SharedPolicyValidation {
  ok: boolean;
  policy: SharedPluginPolicy | null;
  errors: string[];
}

/**
 * Strict, side-effect-free parser for the shared desired-plugin policy.
 * It never accepts URLs, paths, code, settings, credentials, or device state.
 */
export function parseSharedPluginPolicy(raw: string): SharedPolicyValidation {
  const errors: string[] = [];
  if (new TextEncoder().encode(raw).byteLength > MAX_SHARED_POLICY_BYTES) {
    return { ok: false, policy: null, errors: ["Policy file exceeds the 64 KiB size limit."] };
  }

  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { ok: false, policy: null, errors: ["Policy file is not valid JSON."] };
  }

  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ok: false, policy: null, errors: ["Policy root must be a JSON object."] };
  }

  const root = value as Record<string, unknown>;
  const rootKeys = Object.keys(root).sort().join(",");
  if (rootKeys !== "plugins,revision,schema_version") {
    errors.push("Policy contains missing or unsupported top-level fields.");
  }
  if (root.schema_version !== 1) errors.push("Unsupported policy schema_version; expected 1.");
  if (typeof root.revision !== "string" || root.revision.length < 1 || root.revision.length > 100) {
    errors.push("Policy revision must be a string of 1–100 characters.");
  }
  if (!Array.isArray(root.plugins)) {
    errors.push("Policy plugins must be an array.");
  } else {
    if (root.plugins.length > MAX_SHARED_POLICY_PLUGINS) {
      errors.push("Policy contains more than 200 plugin entries.");
    }
    const seen = new Set<string>();
    for (const [index, item] of root.plugins.entries()) {
      if (typeof item !== "object" || item === null || Array.isArray(item)) {
        errors.push(`Plugin entry ${index + 1} must be an object.`);
        continue;
      }
      const entry = item as Record<string, unknown>;
      const keys = Object.keys(entry).sort().join(",");
      if (keys !== "id" && keys !== "id,note") {
        errors.push(`Plugin entry ${index + 1} has missing or unsupported fields.`);
      }
      if (typeof entry.id !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(entry.id)) {
        errors.push(`Plugin entry ${index + 1} has an invalid plugin ID.`);
        continue;
      }
      if (seen.has(entry.id)) errors.push(`Duplicate plugin ID: ${entry.id}.`);
      seen.add(entry.id);
      if (entry.note !== undefined && (typeof entry.note !== "string" || entry.note.length > 500)) {
        errors.push(`Plugin ${entry.id} note must be text no longer than 500 characters.`);
      }
    }
  }

  if (errors.length > 0 || !Array.isArray(root.plugins) || typeof root.revision !== "string") {
    return { ok: false, policy: null, errors };
  }

  const plugins = root.plugins as Record<string, unknown>[];
  return {
    ok: true,
    policy: {
      schema_version: 1,
      revision: root.revision,
      plugins: plugins.map((entry) => ({
        id: entry.id as string,
        ...(typeof entry.note === "string" ? { note: entry.note } : {}),
      })),
    },
    errors: [],
  };
}

/**
 * Conservative sibling-name heuristic. Any similarly named file is surfaced
 * for manual review; this is not proof that a sync provider created a conflict.
 */
export function findPolicyConflictCandidates(paths: string[]): string[] {
  const exactPath = SHARED_POLICY_PATH.toLowerCase();
  const exactName = "shared-policy.json";
  return paths.filter((path) => {
    const normalized = path.replace(/\\/g, "/").toLowerCase();
    const name = normalized.split("/").pop() ?? "";
    return normalized !== exactPath && name !== exactName &&
      name.includes("shared-policy") &&
      (name.endsWith(".json") || name.includes("conflict") || name.includes("conflicted"));
  }).sort();
}

/** SHA-256 fingerprint for display/comparison; it does not lock the file. */
export async function fingerprintSharedPolicy(raw: string): Promise<string> {
  const bytes = new TextEncoder().encode(raw);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
