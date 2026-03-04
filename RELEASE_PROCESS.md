# Release Process

This document describes the CI/CD pipeline for solace-ai-connector across three stages: pull requests, merges to `main`, and releases to PyPI.

---

## Pull Request / Push to `main` (`ci.yaml`)

Triggered on:
- Pull request opened or updated (`synchronize`)
- Push to `main`

Concurrent runs for the same PR or workflow are cancelled automatically.

Two jobs run in **parallel**:

### 1. FOSSA Scan
- Resolves all non-test dependencies (`all` extra from `pyproject.toml`) using `uv pip compile`
- Generates `requirements.txt` and submits to FOSSA via the `sca-scan-and-guard` reusable workflow
- Results are reported as a **diff against the latest scan on `main`** — only new issues introduced by the PR are flagged, not pre-existing ones
- Policy (defined in `.github/workflow-config.json`):
  - **Blocks** on license policy conflicts or unlicensed dependencies
  - **Reports** critical/high vulnerabilities (does not block)

### 2. Build & Test (`hatch_ci`)
- Runs the full test matrix on Python 3.10 and 3.13
- Runs SonarQube analysis
- Runs WhiteSource (Mend) scan

Both jobs must pass for a PR to be mergeable (subject to branch protection rules).

---

## Release (`release.yaml`)

Triggered manually via `workflow_dispatch` with the following inputs:

| Input | Required | Description |
|-------|----------|-------------|
| `version_bump_type` | Yes | `patch`, `minor`, or `major` (default: `patch`) |
| `version` | No | Exact version string (e.g. `1.13.2`). Overrides `version_bump_type` if provided. |
| `skip_security_checks` | No | Skip FOSSA and other security checks (default: `false`) |
| `skip_pypi_publish` | No | Run the release steps but skip the PyPI publish (default: `false`) |

### Job Flow

```
version_prep
     ├── fossa_scan          (parallel, skippable)
     └── other_security_checks (parallel, skippable)
              └── release (needs all above)
```

### Job Details

#### `version_prep`
- Checks out the repo with full history
- Runs `hatch-release-prep` to bump the version in source and commit it
- Outputs: `new_version`, `current_version`, `skip_bump`, `commit_hash`

#### `fossa_scan` (parallel)
- Skipped if `skip_security_checks` is `true`
- Scans the commit SHA produced by `version_prep` (tag is not yet pushed at this point)
- Generates `requirements.txt` via:
  ```bash
  uv pip compile pyproject.toml --extra all --no-header -o requirements.txt
  ```
  This includes all non-test optional dependencies (the `all` group in `pyproject.toml`).
- Must pass before the release job runs

#### `other_security_checks` (parallel)
- Skipped if `skip_security_checks` is `true`
- Runs SonarQube hotspot check
- Runs WhiteSource (Mend) scan
- FOSSA is **not** run here (handled by the dedicated `fossa_scan` job)

#### `release`
- Runs only when `fossa_scan` and `other_security_checks` both succeed (or are skipped)
- Re-runs `hatch-release-prep` on the release branch to apply the version bump
- Publishes to PyPI using [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (skipped if `skip_pypi_publish` is `true`)
- Runs `hatch-release-post` to finalize the release (creates GitHub release, pushes tag, etc.)

---

## Manual FOSSA Scan (`fossa-scan.yaml`)

A standalone workflow for ad-hoc FOSSA scanning. Triggered manually via `workflow_dispatch`.

| Input | Required | Description |
|-------|----------|-------------|
| `git_ref` | No | Branch, tag, or SHA to scan. Defaults to the current branch. |

Uses the same dependency export method as the CI and release workflows:
```bash
uv pip compile pyproject.toml --extra all --no-header -o requirements.txt
```

Useful for scanning feature branches before opening a PR, or for re-running a scan against a specific tag.

---

## FOSSA Policy

Configured in `.github/workflow-config.json`:

| Check | Mode | Behavior |
|-------|------|----------|
| License compliance | `BLOCK` | Blocks on policy conflicts or unlicensed dependencies |
| Vulnerabilities | `REPORT` | Reports critical and high severity findings |

The FOSSA project ID is `SolaceLabs_solace-ai-connector`, assigned to team `sam`.

---

## Dependency Scope for FOSSA

Only the `all` optional dependency group from `pyproject.toml` is included in FOSSA scans. This covers all production optional dependencies but excludes:
- `test` — pytest and test tooling
- `integration-test` — integration test tooling
- `*_ext_release` groups — pre-flattened transitive dep lists (redundant when `all` is included)

Core mandatory dependencies (from `[project] dependencies`) are always included as they are a subset of what `uv pip compile --extra all` resolves.
