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

export interface SharedPolicyPluginDiff {
  onlyInCandidate: string[];
  onlyInCurrent: string[];
}

export function compareSharedPolicyPluginIds(
  current: SharedPluginPolicy,
  candidate: SharedPluginPolicy,
): SharedPolicyPluginDiff {
  const currentIds = new Set(current.plugins.map((entry) => entry.id));
  const candidateIds = new Set(candidate.plugins.map((entry) => entry.id));
  return {
    onlyInCandidate: [...candidateIds].filter((id) => !currentIds.has(id)).sort(),
    onlyInCurrent: [...currentIds].filter((id) => !candidateIds.has(id)).sort(),
  };
}


export type PolicyResolutionChoice = "current" | "candidate" | "remove";

export interface SharedPolicyResolutionPreview {
  ok: boolean;
  policy: SharedPluginPolicy | null;
  json: string | null;
  unresolvedIds: string[];
  invalidChoices: string[];
}

/**
 * Builds a deterministic in-memory merge preview only.
 * Every ID in either input must have an explicit source/removal choice.
 * No Vault access or file mutation occurs here.
 */
export function buildSharedPolicyResolutionPreview(
  current: SharedPluginPolicy,
  candidate: SharedPluginPolicy,
  choices: Record<string, PolicyResolutionChoice>,
  revision: string,
): SharedPolicyResolutionPreview {
  const currentEntries = new Map(current.plugins.map((entry) => [entry.id, entry]));
  const candidateEntries = new Map(candidate.plugins.map((entry) => [entry.id, entry]));
  const allIds = [...new Set([...currentEntries.keys(), ...candidateEntries.keys()])].sort();
  const unresolvedIds = allIds.filter((id) => !Object.prototype.hasOwnProperty.call(choices, id));
  const invalidChoices: string[] = [];
  const selected: SharedPolicyEntry[] = [];

  for (const id of allIds) {
    const choice = choices[id];
    if (choice === undefined) continue;
    if (choice !== "current" && choice !== "candidate" && choice !== "remove") {
      invalidChoices.push(id);
      continue;
    }
    if (choice === "remove") continue;
    const source = choice === "current" ? currentEntries : candidateEntries;
    const entry = source.get(id);
    if (!entry) {
      invalidChoices.push(id);
      continue;
    }
    selected.push({ id, ...(entry.note !== undefined ? { note: entry.note } : {}) });
  }

  if (revision.length < 1 || revision.length > 100) invalidChoices.push("<revision>");
  if (unresolvedIds.length || invalidChoices.length) {
    return { ok: false, policy: null, json: null, unresolvedIds, invalidChoices };
  }

  const policy: SharedPluginPolicy = { schema_version: 1, revision, plugins: selected };
  const validation = parseSharedPluginPolicy(JSON.stringify(policy));
  if (!validation.ok || !validation.policy) {
    return { ok: false, policy: null, json: null, unresolvedIds: [], invalidChoices: ["<validation>"] };
  }
  return {
    ok: true,
    policy: validation.policy,
    json: JSON.stringify(validation.policy, null, 2) + "\n",
    unresolvedIds: [],
    invalidChoices: [],
  };
}
