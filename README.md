# csQt6

Automated cross-platform build system and CI pipeline recipe for **Qt 6** (targeting **v6.11.1**), powered by [**csOrchestrator**](https://github.com/cscosine/csOrchestrator).

---

## Getting Started

### Prerequisites

* Python `>= 3.11`
* Git
* [csOrchestrator](https://github.com/cscosine/csOrchestrator) cloned as a peer directory (`../csOrchestrator`)

### Environment Setup

Bootstrap the local virtual environment, install dev dependencies, link `csOrchestrator` in editable mode, and install git hooks:

**Linux / macOS:**
```bash
./setup.sh
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\setup.ps1
.\.venv\Scripts\Activate.ps1
```

### Running the Orchestrator Locally

Execute the orchestrator script to run pipeline steps locally:

```bash
./qt6.py
# or
python qt6.py
```

### Re-generating the GitHub Workflow

To re-generate the GitHub Actions CI workflow (`.github/workflows/Qt6.yml`) from the definition in [`qt6.py`](qt6.py):

```bash
./qt6.py generate-github-workflow
# or
python qt6.py generate-github-workflow
```

### Development & Quality Checks

Run linting, static type checking, and test suites:

```bash
# Code formatting and linting
ruff check .
ruff format .

# Strict type checking
python -m mypy . --config-file=pyproject.toml

# Unit tests
pytest

# Run all pre-commit hooks
pre-commit run --all-files
```

---

## Overview

Building Qt 6 from source across multiple platforms (Linux and Windows) and architectures (`x64` and `arm64`) can be complex and error-prone. **csQt6** defines a declarative build and packaging recipe in Python using the `csOrchestrator` framework.

With this setup:
- The build pipeline, dependencies, and configuration flags are defined in Python code.
- Cross-platform CI workflows (e.g. [`.github/workflows/Qt6.yml`](.github/workflows/Qt6.yml)) are automatically generated.
- Build artifacts, manifests, and release archives (`.tar.gz` bundles) are assembled consistently across environments.

---

## Architecture & Build Pipeline

The core build recipe is defined in [`qt6.py`](qt6.py) and executed across the matrix defined in [`utils/build_matrix.py`](utils/build_matrix.py).

### Execution Phases

1. **Repo Update**:
   - Performs a shallow clone (`depth=1`) of `qt/qt5.git` at tag `v6.11.1` into `workspace/qt6`.
2. **Install Requirements (Linux-Ubuntu)**:
   - Cleans disk space on CI runners to ensure sufficient storage for large Qt builds.
   - Installs system packages required for Qt 6 GUI, Wayland, X11/XCB, and font rendering (see [`utils/apt_packages_list.py`](utils/apt_packages_list.py)).
3. **Configure & Build (Linux-Ubuntu)**:
   - Runs `./init-repository` inside the cloned Qt directory.
   - Configures Qt with `-no-pch -skip qtwebengine -release -prefix <INSTALL_FOLDER>`.
   - Compiles and installs Qt via `cmake --build .` and `cmake --install .`.
4. **Configure & Build (Windows)**:
   - Configures the MSVC developer environment using `setup-msvc-dev@v4`.
   - Verifies compiler versions (`vswhere.exe` and `cl.exe`).
   - Runs `init-repository.bat`.
   - Prepares a Python virtual environment with `html5lib`.
   - Configures and compiles Qt with MSVC and Ninja.
5. **Artifacts & Release Bundling**:
   - Packages build outputs into tarball archives.
   - Generates `.csOrchestratorManifest` metadata and release bundles (`Qt6-v6.11.1-bundle.tar.gz`).

---

## Supported Build Matrix

The target execution matrix is configured in [`utils/build_matrix.py`](utils/build_matrix.py):

| OS | Version | Architecture | Compiler | Generator |
|---|---|---|---|---|
| **Linux** | Ubuntu 22.04 | `x64` | GCC (default) | Ninja |
| **Linux** | Ubuntu 22.04 | `arm64` | GCC (default) | Ninja |
| **Linux** | Ubuntu 24.04 | `x64` | GCC (default) | Ninja |
| **Linux** | Ubuntu 24.04 | `arm64` | GCC (default) | Ninja |
| **Windows** | Windows 10 | `x64` | MSVC 2022 (v17) | Ninja |

Toolchain mappings for each platform are provided in [`csQt6/cs_orchestrator_config.py`](csQt6/cs_orchestrator_config.py).

---

## Repository Structure

```
csQt6/
├── .agents/skills/
│   └── csqt6-orchestrator-recipe/  # Agent skill for auditing recipes & re-generating workflows
├── qt6.py                          # Main orchestrator pipeline recipe (source of truth)
├── pyproject.toml                  # Project packaging, Ruff, MyPy, and Pytest configuration
├── setup.sh / setup.ps1            # Environment bootstrap scripts (Linux / Windows)
├── open-code.sh / open-code.ps1    # Helper scripts to launch VS Code inside the virtualenv
├── .pre-commit-config.yaml         # Pre-commit checks (Ruff, MyPy, Actionlint)
├── csQt6/
│   └── cs_orchestrator_config.py   # Toolchain and compiler mapping logic (included in release)
├── utils/
│   ├── build_matrix.py             # OS, architecture, and generator matrix definitions
│   ├── scripts.py                  # Bash and PowerShell script templates for build phases
│   └── apt_packages_list.py        # System package dependencies for Ubuntu
├── csorchestratorsdk/portable/     # [Autogenerated / Vendored] Standalone SDK synced from csOrchestrator
├── tests/
│   └── csQt6/                      # Unit tests for configuration mappings
└── .github/workflows/
    └── Qt6.yml                     # [Autogenerated] GitHub Actions CI workflow (emitted by qt6.py)
```

### Autogenerated Files Lifecycle

| Path | Origin / Trigger | Maintenance Policy |
|---|---|---|
| [`.github/workflows/Qt6.yml`](.github/workflows/Qt6.yml) | Autogenerated by running `./qt6.py generate-github-workflow`. | **Never edit manually.** Edit `qt6.py` or files in `utils/`, then re-run the generator command. |
| [`csorchestratorsdk/portable/`](csorchestratorsdk/portable/) | Autogenerated & exported by `csOrchestrator`. | Synced from `csOrchestrator` to provide lightweight release manifest utilities on CI runners without requiring `pip install csorchestrator`. |
| `workspace/` *(gitignored)* | Created at runtime when running `./qt6.py` locally. | Holds cloned Qt sources (`workspace/qt6`), temporary build directories, and install outputs. Can be safely deleted to reset local state. |

---

## Agent Skills

This repository includes a project-specific agent skill under [`.agents/skills/`](.agents/skills/):

* [**`csqt6-orchestrator-recipe`**](.agents/skills/csqt6-orchestrator-recipe/SKILL.md): Guides AI coding assistants in auditing recipe consistency (checking that extra files exist, verifying version alignment, and validating script imports), re-generating the GitHub Actions workflow (`./qt6.py generate-github-workflow`), and running pre-commit quality checks.

### How to Use the Skill

* **Automatic Activation (Natural Language)**: When using an AI coding assistant (e.g. Antigravity, Codex, Claude Code), the assistant automatically indexes `.agents/skills/` and follows this skill when given relevant prompts, such as:
  * *"Audit the Qt6 recipe consistency"*
  * *"Update Qt version to v6.11.2 and re-generate the workflow"*
  * *"Add a new build target to the matrix and update CI"*
* **Explicit Invocation**: Prompt the assistant directly:
  * *"Use the `csqt6-orchestrator-recipe` skill to audit the build recipe"*
  * Or use the slash command `/csqt6-orchestrator-recipe` (if supported by your client)
* **Human Developer Runbook (Standard Operating Procedure / SOP)**: For manual work without an AI assistant, [`.agents/skills/csqt6-orchestrator-recipe/SKILL.md`](.agents/skills/csqt6-orchestrator-recipe/SKILL.md) serves as a concise checklist for extra files, version alignment, and workflow re-generation commands.

---

## TODO & Future Ideas

- [ ] **Compiler Caching (`ccache` on Linux / `sccache` on Windows)**:
  - Integrate compiler caching into CI via GitHub Actions caching (`actions/cache`).
  - *Mechanism & Trade-offs*: Even though CI runners start from scratch, `actions/cache` restores cached object files at the start of the job, allowing `ccache` to skip recompiling unchanged translation units. This can significantly speed up iterative runs on `main` and `dev` branches, though it must be monitored against GitHub's **10 GB repository cache quota** due to the size of Qt 6 builds.

---

## License

This project is licensed under the [MIT License](LICENSE).
