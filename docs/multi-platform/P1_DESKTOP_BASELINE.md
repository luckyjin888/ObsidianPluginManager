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

A source inventory of the current `tests/` directory found **120 unittest test methods** across 10 test modules:

| Test module | Test methods |
|---|---:|
| `test_audit.py` | 10 |
| `test_cli_guidance.py` | 10 |
| `test_installer_rate_limit_budget.py` | 1 |
| `test_interactions.py` | 8 |
| `test_obsidian_startup.py` | 12 |
| `test_plugin_update_subscription.py` | 20 |
| `test_quickadd_shortcuts.py` | 25 |
| `test_ssl.py` | 14 |
| `test_vault_init.py` | 9 |
| `test_windows.py` | 11 |
| **Total** | **120** |

These tests include Windows install discovery and CLI selection, macOS/Linux install-layout checks, Vault directory safety, Obsidian startup and CLI readiness, plugin inventory, consent behavior, QuickAdd configuration safety, HTTPS/TLS validation, and update-subscription caching/rate limits.

## Existing GitHub Actions baseline

The existing workflow `.github/workflows/tests.yml` runs a 3 × 3 matrix:

- Runners: Ubuntu, macOS, Windows
- Python: 3.10, 3.11, 3.12
- Total: **9 CI jobs**

Each job checks the Bash launcher executable bit, installs optional TLS providers, compiles `obsidian_manager.py`, and runs unittest discovery. Bash syntax validation runs on non-Windows runners.

### Observed PR #14 baseline run

The initial Draft PR commit `717501b738dd8a4da807d0065db00e955a0972a9` triggered GitHub Actions run [45964211338](https://github.com/luckyjin888/ObsidianPluginManager/actions/runs/45964211338).

- Result: **9/9 jobs passed**
- Python compilation: passed in the matrix
- Existing unittest suite: passed in the matrix
- Bash launcher executable-mode check: passed in the matrix
- Bash syntax check: passed on Ubuntu/macOS; intentionally skipped on Windows

This is CI evidence for the unchanged desktop baseline. It is not a claim that every real Windows/macOS installation layout or Obsidian version has been manually tested on physical machines.

## Non-regression rules for the mobile work

1. Do not delete, rename, or replace the existing Python core or Windows/macOS launchers as part of mobile implementation.
2. Keep the current Python CI matrix and unit tests running throughout the work.
3. Add new mobile code in a separate package/directory; do not import mobile code into the Python desktop entry point.
4. Any future changes to shared catalogue or policy data must include Python regression tests where the desktop manager consumes that data.
5. A change is not considered desktop-verified solely because it compiles; the full CI matrix must pass.
6. Record physical-device checks separately from CI and simulator checks.

## P1 outcome

The existing automated desktop baseline is inventoried and the first PR CI run is green. No existing desktop source files have been changed by this P1 record.

**Remaining validation limitation:** CI uses hosted operating-system runners and mocks/fixtures for many application behaviors. Before release, perform hands-on smoke tests with the user's actual Windows and macOS Obsidian installations.
