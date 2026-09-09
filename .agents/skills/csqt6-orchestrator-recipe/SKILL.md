---
name: csqt6-orchestrator-recipe
description: >-
  Manages, audits, and maintains the csQt6 build recipe powered by csOrchestrator.
  Use when inspecting or updating the Qt 6 build pipeline, validating recipe consistency
  (extra files, versions, and scripts), re-generating the GitHub Actions CI workflow,
  or running pre-commit and quality checks.
---

# csQt6 Orchestrator Recipe Management

## Overview

This skill guides the agent in inspecting, auditing consistency, updating, and maintaining the **csQt6** build recipe. `csQt6` uses the `csOrchestrator` framework to define cross-platform Qt 6 build pipelines in Python and generate corresponding GitHub Actions CI workflows.

## Dependencies

- **Python**: `>= 3.11` in active `.venv`
- **csOrchestrator**: Available as an editable package in the local environment
- **Tools**: `pre-commit`, `ruff`, `mypy`, `pytest`

## Quick Start

To audit recipe consistency and re-generate the GitHub Actions CI workflow:

```bash
# 1. Re-generate GitHub Actions workflow from qt6.py
./qt6.py generate-github-workflow

# 2. Run quality checks and ensure git hygiene
pre-commit run --all-files
```

## Workflow

Follow these steps when interacting with or modifying the `csQt6` build recipe:

### 1. Recipe & Consistency Audit
Inspect the core configuration files before making changes or upon request:
- [`qt6.py`](file:///home/sceriani/myWorkspace/csQt6/qt6.py): Core pipeline definition and phases.
- [`utils/build_matrix.py`](file:///home/sceriani/myWorkspace/csQt6/utils/build_matrix.py): OS, architecture, and generator matrix.
- [`utils/scripts.py`](file:///home/sceriani/myWorkspace/csQt6/utils/scripts.py): Shell and PowerShell build command templates.
- [`utils/apt_packages_list.py`](file:///home/sceriani/myWorkspace/csQt6/utils/apt_packages_list.py): System packages for Ubuntu.
- [`csQt6/cs_orchestrator_config.py`](file:///home/sceriani/myWorkspace/csQt6/csQt6/cs_orchestrator_config.py): Compiler and toolchain mappings.
- [`pyproject.toml`](file:///home/sceriani/myWorkspace/csQt6/pyproject.toml): Project metadata and versioning.

**Verification Checklist (Strict Fail-Loud Policy):**
- **Extra Files**: Check every path passed to `additional_files_list` in `create_default_orchestrator()` (e.g. `Path("csQt6/cs_orchestrator_config.py")`). Verify that every referenced file exists on disk.
- **Version Alignment**: Verify that `qt_version_tag` in `qt6.py` (e.g. `v6.11.1`) aligns with `version` in `pyproject.toml` (e.g. `6.11.1`) and artifact package versions.
- **Script References**: Verify that all script functions invoked in `qt6.py` are properly defined and imported from `utils/scripts.py`.
- **Platform Matrix Coverage**: Ensure that `qt6_mapping()` in `csQt6/cs_orchestrator_config.py` handles all operating systems present in `utils/build_matrix.py`.

> [!IMPORTANT]
> If any consistency check fails (missing extra file, mismatched version, unmapped OS variant), **fail loudly**. Report the exact discrepancies to the user for guidance rather than silently continuing or guessing.

### 2. Local Execution Policy (Build Guard)
- **DO NOT run full local builds of Qt 6** (e.g., executing all phases of `./qt6.py` locally). Compiling Qt 6 requires multiple hours, significant disk space, and dozens of gigabytes of RAM.
- Only run unit tests (`pytest`) or dry-run validation when checking local configuration logic.

### 3. CI Workflow Re-generation
Whenever `qt6.py`, build matrix settings, or execution phases are modified, re-generate the GitHub Actions workflow:

```bash
./qt6.py generate-github-workflow
```

- Verify that [`.github/workflows/Qt6.yml`](file:///home/sceriani/myWorkspace/csQt6/.github/workflows/Qt6.yml) has been updated with the modified phases and matrix.
- Inspect the git diff using `git diff .github/workflows/Qt6.yml` to ensure changes match expectations.

### 4. Code Quality & Pre-commit Verification
Before concluding any changes, run the repository's validation hooks:

```bash
pre-commit run --all-files
```

If hooks report formatting errors or auto-fix lines:
1. Review the modified files.
2. Re-run `pre-commit run --all-files` to ensure all checks pass cleanly (`Passed`).

### 5. Documentation Synchronization
If recipe arguments, build matrix configurations, or commands were updated:
- Update [`README.md`](file:///home/sceriani/myWorkspace/csQt6/README.md) to keep the matrix table, execution phases, and command instructions accurate.

## Rate Limiting

Not applicable. This skill operates entirely on local filesystem artifacts, repository tools, and git workflows.

## Common Mistakes

1. **Attempting a full local build**: Running `./qt6.py` without understanding that it will attempt to download and build all of Qt 6 from source. Full builds are meant for CI runners or dedicated build machines.
2. **Forgetting to re-generate the workflow**: Modifying `qt6.py` or `utils/` without running `./qt6.py generate-github-workflow`, leaving `.github/workflows/Qt6.yml` out of sync with the Python recipe.
3. **Missing extra files in release**: Adding a file to `additional_files_list` in `qt6.py` that does not exist or has a typo in its relative path, causing release packaging jobs to fail in CI.
4. **Version mismatch**: Updating `qt_version_tag` in `qt6.py` without updating `version` in `pyproject.toml` or the release artifact tags.
