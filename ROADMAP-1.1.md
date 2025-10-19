# Alpha Factory v1.1 Roadmap

**Status:** planning
**Baseline:** v1.0.1 (tests green)
**Target window:** ~2–4 weeks (iterative releases)

## Objectives (what v1.1 improves)
1. **Alpha Factory UX**
   - CLI: clearer subcommands/help; consistent exit codes.
   - Better errors & docs snippets for common tasks (ingest, register, export).

2. **Registry & FeatureStore polish**
   - Rich search (by metric thresholds, tags, date ranges).
   - Provenance: capture run params & code hash in artifacts.
   - IO hardening (atomic writes; temp->final rename; Windows locks).

3. **Risk & Monitoring**
   - “Risk Governor” guardrails: parameter sanity checks & stop conditions.
   - Drift dashboard: daily/weekly refresh script; image + HTML artifacts.

4. **Packaging & CI**
   - Matrix CI (Win/Linux, Py 3.11): lint, unit, integration, packaging install.
   - CLI/docs smoke (mkdocs build best-effort).
   - Pre-commit cache opt-out on CI; stable line-endings.

5. **Reproducibility**
   - Deterministic seeds & fixed time windows for grid/backtests.
   - One-click “re-run last experiment” helper.

---

## Delivery Plan

### Milestone A (Week 1): CLI + Registry
- CLI: normalize help & subcommand layout.
- Registry: `search()` by metric min/max, tag, date; paging.
- Artifacts: write-to-temp then atomic rename to avoid partials.

**Exit**: unit + integration green; examples updated.

### Milestone B (Week 2): Risk & Drift
- Risk Governor v1: parameter guards; “fail fast” reasons.
- Drift dashboard job + artifacts (HTML + PNG); PS7 helper.

**Exit**: nightly drift run script produces artifacts.

### Milestone C (Week 3): CI Matrix + Packaging
- GH Actions: matrix {windows-latest, ubuntu-latest} × {3.11}.
- Steps: ruff/black, tests (unit/integration), build sdist/wheel, editable install.
- MkDocs smoke optional; ignore failures in docs job.

**Exit**: all PRs run matrix; artifacts uploaded on failure.

### Milestone D (Week 4, optional): Repro Suite
- Deterministic seeds; “rerun last” command.
- Long-run smoke with capped runtime.

**Exit**: reproducibility checklist passes locally + CI quick mode.

---

## “Definition of Done” for v1.1
- ✅ CI green on matrix.
- ✅ drift job produces artifacts & simple trend plots.
- ✅ registry search covers tags/metrics/date; docs show examples.
- ✅ risk guardrails triggered in tests + logged reason codes.
- ✅ mkdocs builds locally; critical pages linked in nav.
- ✅ CHANGELOG + migration notes (if any).

---

## Tickets (suggested)
- feat(cli): reorganize commands + error codes
- feat(registry): search(min, max, tags, date, limit, page)
- feat(risk): guardrails + fail-fast reasons
- feat(drift): daily job script + artifacts
- ci(matrix): win/linux 3.11; package & install checks
- docs: update examples + quick starts
