## Make-Handoff.ps1

Generate a ChatGPT continuation header (v2) to paste as the first message in a new chat.

Usage:
  pwsh tools/Make-Handoff.ps1
  pwsh tools/Make-Handoff.ps1 -Feature risk_governor

Tip:
  You can also run `handoff -Feature risk_governor` (profile function).
## Make-Handoff.ps1

Print a v2 handoff header from repo state.

**Usage**
  pwsh tools/Make-Handoff.ps1 [-Feature name] [-WithLogs] [-Logs N] [-Minimal]

**Examples**
  pwsh tools/Make-Handoff.ps1 -Feature risk_governor
  pwsh tools/Make-Handoff.ps1 -Feature risk_governor -WithLogs -Logs 10
  pwsh tools/Make-Handoff.ps1 -Minimal

Fields included: repo, state path, branch/commit (live), project/phase/owner/ai_guard/last_synced (from state.json),
lock status, latest session summary (manifest), generated_at, plus warnings on mismatches.
