# P1 — Desktop Regression Baseline

**Baseline source:** `main` at `2c1ac3572dc00208c51f5212be0a81aee0564f26`  
**Baseline recorded on:** 2026-11-27  
**Scope:** Existing Windows and macOS desktop workflows, plus the current Linux CI runner.

## Existing desktop entry points (must remain)

| File | Platform / role | Baseline behavior |
|---|---|---|
| `obsidian_manager.py` | Shared Python core | Existing manager implementation; Python 3.10+ |
| `obsidian_manager.ps1` | Windows PowerShell launcher | Prefers `py -3`, falls back to `python`, passes arguments and exit code through |
| `obsidian_manager.sh` | macOS/Linux Bash launcher | Resolves its own directory and runs `python3 obsidian_manager.py` |
| `plugin_update_subscription.py` | Desktop-side update subscription utility | Separate opt-in CLI utility |

The current project does not contain a TypeScript/Obsidian mobile plugin package, `package.json`, or mobile build pipeline at this baseline.

## Existing automated test inventory

The `main` baseline contains **120 unittest test methods** across 10 modules. P1 adds a separate four-test desktop entry-point regression guard, bringing the feature branch inventory to **124 test methods across 11 modules**.

| Test module | Test methods on feature branch |
|---|---:|
| `test_audit.py` | 10 |
| `test_cli_guidance.py` | 10 |
| `test_desktop_entrypoints.py` (new P1 guard) | 4 |
| `test_installer_rate_limit_budget.py` | 1 |
| `test_interactions.py` | 8 |
| `test_obsidian_startup.py` | 12 |
| `test_plugin_update_subscription.py` | 20 |
| `test_quickadd_shortcuts.py` | 25 |
| `test_ssl.py` | 14 |
| `test_vault_init.py` | 9 |
| `test_windows.py` | 11 |
| **Total** | **124** |

The new guard checks that the Python core, Windows PowerShell launcher, macOS/Linux Bash launcher, and separate update-subscription utility remain present, and that the launchers still point to the existing Python core. It does not replace platform-specific smoke testing.

The existing tests include Windows install discovery and CLI selection, macOS/Linux install-layout checks, Vault directory safety, Obsidian startup and CLI readiness, plugin inventory, consent behavior, QuickAdd configuration safety, HTTPS/TLS validation, and update-subscription caching/rate limits.

## Existing GitHub Actions baseline

The existing workflow `.github/workflows/tests.yml` runs a 3 × 3 matrix:

- Runners: Ubuntu, macOS, Windows
- Python: 3.10, 3.11, 3.12
- Total: **9 CI jobs**

Each job checks the Bash launcher executable bit, installs optional TLS providers, compiles `obsidian_manager.py`, and runs unittest discovery. Bash syntax validation runs on non-Windows runners.

### Observed initial PR #14 run

The initial Draft PR commit `717501b738dd8a4da807d0065db00e955a0972a9` triggered GitHub Actions run [45964211338](https://github.com/luckyjin888/ObsidianPluginManager/actions/runs/45964211338).

- Result: **9/9 jobs passed**
- Python compilation: passed in the matrix
- Original unittest suite: passed in the matrix
- Bash launcher executable-mode check: passed in the matrix
- Bash syntax check: passed on Ubuntu/macOS; intentionally skipped on Windows

This initial run validates the original 120-test baseline. The new four-test guard was added afterward and must be confirmed by the next CI run.

This is CI evidence for the desktop baseline. It is not a claim that every real Windows/macOS installation layout or Obsidian version has been manually tested on physical machines.

## Non-regression rules for the mobile work

1. Do not delete, rename, or replace the existing Python core or Windows/macOS launchers as part of mobile implementation.
2. Keep the current Python CI matrix and unit tests running throughout the work.
3. Add new mobile code in a separate package/directory; do not import mobile code into the Python desktop entry point.
4. Any future changes to shared catalogue or policy data must include Python regression tests where the desktop manager consumes that data.
5. A change is not considered desktop-verified solely because it compiles; the full CI matrix must pass.
6. Record physical-device checks separately from CI and simulator checks.

## P1 outcome

The desktop baseline is inventoried and a dedicated regression guard has been added. The initial CI run is green for the original test suite; the next CI run must validate the new guard on the full matrix.

**Remaining validation limitation:** CI uses hosted operating-system runners and mocks/fixtures for many application behaviors. Before release, perform hands-on smoke tests with the user's actual Windows and macOS Obsidian installations.
