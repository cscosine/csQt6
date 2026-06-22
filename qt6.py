#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Sequence, TypeAlias

from csorchestrator.context.context_compiler_generator import Compiler, ContextCompilerGenerator
from csorchestrator.core.report import Report
from csorchestrator.context.context_os_architecture import OS, UBUNTU_STRING_PREFIX
from csorchestrator.step.step_utils import StepExecuteOnlyOn
from csorchestrator.orchestrator.orchestrator import (
    OptionalOrchestratorWithReport,
    create_orchestrator_factory_all_supported_cases,
)
from csorchestrator.step.step_get_repository import (
    RepoUrlParts,
    StepGetRepositoryGitHub,
    StepGetRepositoryExtraDepthOne,
)
from csorchestrator.step.step_utils import (
    StepExecuteOnlyOn,
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
)
from csorchestrator.step.step_custom_command import (
    StepBashScriptCommand,
    StepWinPSCommand,
    StepInstallAptPackages,
)
from csorchestrator.ci.github.github_workflow_config import MatrixOsArchCompilerGeneratorRunnerEntryInclude

from csorchestrator.step.step_github_action import StepAddGitHubAction

from csorchestrator.utils.presets.supported_variants import BuildConfig
from csorchestrator.core.optional_result_with_report import OptionalResultWithReport
from csorchestrator.cli.cli import orchestrator_main_with_default_run
from csorchestrator.ci.github.github_workflow_config import (
    CreateGitHubWorkflowConfig,
    Cron,
    DayOfWeek,
    JobReleaseCreationFromArifacts,
)
from csorchestrator.step.step_get_versions_from_cmake_config_package_version import (
    StepGetVersionsFromCMakeConfigPackageVersion,
    CMakeConfigPackageVersion,
)
from csorchestrator.step.step_create_archives import StepCreateArchives
from csorchestrator.step.step_upload_artifacts import StepUploadArtifacts


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")

    # please keep version aligned with qt version
    qt_version_tag = "v6.11.1"

    o = create_orchestrator_factory_all_supported_cases(
        "Qt6",
        version=qt_version_tag,
        execution_matrix_name="orchestrator-matrix",
        use_ninja_for_windows=True,
        use_ninja=True,
        use_ninjamulti=False,
    )

    # strip non used matrix configs
    new_list = []
    for entry in o.execution_matrix.os_architecture_compiler_generator_list:
        if entry.context_os_architecture.os == OS.LINUX and entry.context_compiler_generator.compiler_family == Compiler.GCC:
            new_list += [entry]
        if entry.context_os_architecture.os == OS.WINDOWS \
            and entry.context_compiler_generator.compiler_family == Compiler.MSVC \
            and entry.context_compiler_generator.compiler_version == ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17:
            new_list += [entry]
    

    o.execution_matrix.os_architecture_compiler_generator_list = new_list

    o.create_default_github_workflow(
        config=CreateGitHubWorkflowConfig(
            on_push_branches=["main", "dev"],
            on_push_tags=["'v*.*.*'"],
            on_pull_request_branches=["main"],
            on_dispatch=True,
            on_schedule=Cron.weekly(DayOfWeek.MON, hour=3),
        )
    )

    o.default_github_wf.on_job(
        job=JobReleaseCreationFromArifacts(
            name="release-from-artifacts",
            needs="orchestrator-matrix",
            runs_on="ubuntu-latest",
            if_str="${{ github.ref_type == 'tag' }}",
        )
    )

    flag_repo_update = True
    dry_run = False

    repo_name = "qt6"

    p = o.create_phase("Repo Update")
    if flag_repo_update:
        p.add_step(
            StepGetRepositoryGitHub(
                name=repo_name,
                description=f"Clone or pull-ff {repo_name}",
                target_directory=(base_target_dir / repo_name).as_posix(),
                repo_url_parts=RepoUrlParts(
                    repo_base_url=StepGetRepositoryGitHub.GITHUB_BASE_URL_SSH,
                    repo_org="qt",
                    repo_name="qt5" + ".git",
                ),
                repo_ref=qt_version_tag,
            )
            .add_extra(
                StepGetRepositoryExtraDepthOne(
                    on_local_checkout=True,  # shallow copy, huge repo
                    on_github_action_checkout=True,
                )
            )
            .add_extra(StepExecuteOnlyOncePerMatrix())
        )

    # ----------------- LINUX -----------------

    p = o.create_phase("Install Requirements (Linux-Ubuntu)")
    p.add_step(
        StepInstallAptPackages(
            name="install apt packages",
            description="install apt packages if not already installed in the system",
            packages=[
                "libfontconfig1-dev",
                "libfreetype-dev",
                "libgtk-3-dev",
                "libx11-dev",
                "libx11-xcb-dev",
                "libxcb-cursor-dev",
                "libxcb-glx0-dev",
                "libxcb-icccm4-dev",
                "libxcb-image0-dev",
                "libxcb-keysyms1-dev",
                "libxcb-randr0-dev",
                "libxcb-render-util0-dev",
                "libxcb-shape0-dev",
                "libxcb-shm0-dev",
                "libxcb-sync-dev",
                "libxcb-util-dev",
                "libxcb-xfixes0-dev",
                "libxcb-xkb-dev",
                "libxcb1-dev",
                "libxext-dev",
                "libxfixes-dev",
                "libxi-dev",
                "libxkbcommon-dev",
                "libxkbcommon-x11-dev",
                "libopenjp2-7",
                "libxss-dev",
                "libudev-dev",
                "libwayland-dev",
                "libnss3-dev",
                "gperf",
                "doxygen",
                "python3-html5lib",
            ],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Free disk space (Linux-Ubuntu)",
            description="init repo",
            cmd=[
                "set -euo pipefail",
                '',
                "# Show available space",
                "df -h",
                '',
                "# Remove unnecessary tools/packages (do not fail if they are not installed)",
                "sudo apt-get remove -y '^ghc-8.*' '^dotnet-.*' '^mongodb.*' 'mysql-.*' 'php.*' 'powershell' 'snap.*' || true",
                "sudo apt-get autoremove -y",
                "sudo apt-get clean",
                '',
                "# Remove large directories",
                "sudo rm -rf /usr/local/lib/android || true",
                "sudo rm -rf /opt/hostedtoolcache || true",
                '',
                "# Show available space",
                "df -h",
            ],
            dry_run=dry_run,
        )
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
        .add_extra(StepSkipExecutionOnLocal())
    )

    p = o.create_phase(f"Configure-Build-Test-Install (Linux-Ubuntu)")
    p.add_step(
        StepBashScriptCommand(
            name="init repo (Linux-Ubuntu)",
            description="init repo",
            cmd=[
                'set -euo pipefail',
                '',
                f'cd workspace/{repo_name}', 
                './init-repository'
                ],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Configure (Linux-Ubuntu)",
            description="configure repo",
            cmd=[
                'set -euo pipefail',
                '',
                'ROOT_FOLDER=$(pwd)',
                '',
                'FOLDER_NAME="$CS_DIR_FROM_MATRIX"',
                ': "${FOLDER_NAME:?missing FOLDER_NAME}"',
                '',
                f'REPO_FOLDER="${{ROOT_FOLDER}}/workspace/{repo_name}"',
                f'BUILD_FOLDER="${{ROOT_FOLDER}}/workspace/build/${{FOLDER_NAME}}/{repo_name}/release"',
                f'INSTALL_FOLDER="${{ROOT_FOLDER}}/workspace/install/${{FOLDER_NAME}}/{repo_name}"',
                '',
                'mkdir -p "${INSTALL_FOLDER}"',
                'mkdir -p "${BUILD_FOLDER}"',
                '',
                'cd "${BUILD_FOLDER}"',
                '',
                '"${REPO_FOLDER}/configure" -no-pch -skip qtwebengine -release -prefix "${INSTALL_FOLDER}"',
            ]
        ).add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Build (Linux-Ubuntu)",
            description="build repo",
            cmd=[
                'set -euo pipefail',
                '',
                'ROOT_FOLDER=$(pwd)',
                '',
                'FOLDER_NAME="$CS_DIR_FROM_MATRIX"',
                ': "${FOLDER_NAME:?missing FOLDER_NAME}"',
                '',
                f'BUILD_FOLDER="${{ROOT_FOLDER}}/workspace/build/${{FOLDER_NAME}}/{repo_name}/release"',
                '',
                'cd "${BUILD_FOLDER}"',
                '',
                'cmake --build .',
            ]
        ).add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Install (Linux-Ubuntu)",
            description="build repo",
            cmd=[
                'set -euo pipefail',
                '',
                'ROOT_FOLDER=$(pwd)',
                '',
                'FOLDER_NAME="$CS_DIR_FROM_MATRIX"',
                ': "${FOLDER_NAME:?missing FOLDER_NAME}"',
                '',
                f'BUILD_FOLDER="${{ROOT_FOLDER}}/workspace/build/${{FOLDER_NAME}}/{repo_name}/release"',
                '',
                'cd "${BUILD_FOLDER}"',
                '',
                'cmake --install .',
            ]
        ).add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    # ----------------- WINDOWS -----------------
    p = o.create_phase(f"Configure-Build-Test-Install (Windows)")

    p.add_step(
        StepAddGitHubAction(
            name="Setup MSVC",
            description="setup MSVC environment",
            uses="TheMrMilchmann/setup-msvc-dev@v4",
            with_list=[
                f"arch: {MatrixOsArchCompilerGeneratorRunnerEntryInclude.MATRIX_ARCHITECTURE_EMBRACED}"
            ]
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="Show MSVC Version (Windows)",
            description="show msvc verison",
            cmd=[
                'Write-Host "=== Visual Studio ==="',
                '',
                '& "${env:ProgramFiles(x86)}\\Microsoft Visual Studio\\Installer\\vswhere.exe" `',
                "    -latest `",
                "    -products * `",
                "    -property installationName",
                '',
                '& "${env:ProgramFiles(x86)}\\Microsoft Visual Studio\\Installer\\vswhere.exe" `',
                "    -latest `",
                "    -products * `",
                "    -property catalog_productDisplayVersion",
                '',
                'Write-Host ""',
                'Write-Host "=== MSVC ==="',
                '',
                "$cl = Get-Command cl.exe -ErrorAction Stop",
                '',
                'Write-Host "cl.exe:"',
                "Write-Host $cl.Source",
             ],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="init repo (Windows)",
            description="init repo",
            cmd=[
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = 'Stop'",
                '',
                "cd workspace/" + repo_name, 
                './init-repository.bat'],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="Configure (Windows)",
            description="configure repo",
            cmd=[
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = 'Stop'",
                '',
                'if (!(Test-Path ".venv")) {',
                "    python -m venv .venv",
                "}",
                '& ".\\.venv\\Scripts\\Activate.ps1"',
                "python -m pip install --upgrade pip",
                "pip install html5lib",
                '',
                "$ROOT_FOLDER = Get-Location",
                '',
                '$FOLDER_NAME = "$CS_DIR_FROM_MATRIX"',
                '$BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"',                
                '',
                f'$REPO_FOLDER="$ROOT_FOLDER/workspace/{repo_name}"',
                f'$BUILD_FOLDER="$ROOT_FOLDER/workspace/build/$BUILD_FOLDER_NAME/{repo_name}/release"',
                f'$INSTALL_FOLDER="$ROOT_FOLDER/workspace/install/$FOLDER_NAME/{repo_name}"',
                '',
                'New-Item -ItemType Directory -Force -Path "$INSTALL_FOLDER" | Out-Null',
                'New-Item -ItemType Directory -Force -Path "$BUILD_FOLDER" | Out-Null',
                '',
                "Set-Location $BUILD_FOLDER",
                '',
                '& "$REPO_FOLDER/configure.bat" -no-pch -skip qtwebengine -release -prefix "$INSTALL_FOLDER"',
                "if ($LASTEXITCODE) { exit $LASTEXITCODE }",
            ],
            dry_run=dry_run,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="Build (Windows)",
            description="build repo",
            cmd=[
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = 'Stop'",
                '',
                "$ROOT_FOLDER = Get-Location",
                '',
                '$BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"',                
                '',
                f'$BUILD_FOLDER="$ROOT_FOLDER/workspace/build/$BUILD_FOLDER_NAME/{repo_name}/release"',
                '',
                '',
                "Set-Location $BUILD_FOLDER",
                '',
                "cmake --build .",
                "if ($LASTEXITCODE) { exit $LASTEXITCODE }",
            ],
            dry_run=dry_run,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="Install (Windows)",
            description="build repo",
            cmd=[
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = 'Stop'",
                '',
                "$ROOT_FOLDER = Get-Location",
                '',
                '$BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"',                
                '',
                f'$BUILD_FOLDER="$ROOT_FOLDER/workspace/build/$BUILD_FOLDER_NAME/{repo_name}/release"',
                '',
                '',
                "Set-Location $BUILD_FOLDER",
                '',
                "cmake --install . ",
                "if ($LASTEXITCODE) { exit $LASTEXITCODE }",
            ],
            dry_run=dry_run,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )
    p = o.create_phase(f"Create and Upload Artifacts")

    p.add_step(
        StepGetVersionsFromCMakeConfigPackageVersion(
            name="Get Versions",
            description="Get Versions for all libs",
            repos_version=[CMakeConfigPackageVersion(repo_name, qt_version_tag)],
            base_install_dir=base_install_dir,
            id="versions",
            output_dict_name="packages",
        )
    )

    p.add_step(
        StepCreateArchives(
            name="Create Archives",
            description="Create archives with libs and versions",
            input_id="versions",
            input_dict="packages",
            base_install_dir=base_install_dir,
        ).add_extra(StepSkipExecutionOnLocal())
    )

    p.add_step(
        StepUploadArtifacts(
            name="Upload Artifacts",
            description="Upload Artifacts with libs and versions",
            base_install_dir=base_install_dir,
        ).add_extra(StepSkipExecutionOnLocal())
    )

    return OptionalResultWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
