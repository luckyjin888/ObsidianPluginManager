import { parseSharedPluginPolicy } from "./shared-policy";

/**
 * Minimal public-Vault surface used by the guarded policy writer.
 * This helper is intentionally not wired to any command or UI.
 */
export interface SharedPolicyVaultProcessAdapter<TFileLike> {
  process(file: TFileLike, fn: (current: string) => string): Promise<void>;
  read(file: TFileLike): Promise<string>;
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
