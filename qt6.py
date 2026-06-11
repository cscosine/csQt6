#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Sequence, TypeAlias

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
    CMakeConfigPackageVersionGrep,
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
                "libxcb-render-util0-dev",
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
                "# Show available space",
                "df -h",
                "",
                "# Remove unnecessary tools/packages (do not fail if they are not installed)",
                "sudo apt-get remove -y '^ghc-8.*' '^dotnet-.*' '^mongodb.*' 'mysql-.*' 'php.*' 'powershell' 'snap.*' || true",
                'sudo apt-get autoremove -y',
                'sudo apt-get clean',
                "",
                "# Remove large directories",
                'sudo rm -rf /usr/local/lib/android || true',
                'sudo rm -rf /opt/hostedtoolcache || true',
                "",
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
            cmd=[f"cd workspace/{repo_name}", "./init-repository"],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="configure/build/install (Linux-Ubuntu)",
            description="init repo",
            cmd=[
                "set -euo pipefail",
                "",
                "cd workspace/",
                "",
                "WORKSPACE_ROOT=$(pwd)",
                'INSTALL_FOLDER_NAME="$CS_DIR_FROM_MATRIX"',
                'BUILD_FOLDER_NAME="build-$CS_MATRIX_EXEC_ID"',
                'GENERATOR_TYPE="$CS_GENERATOR_TYPE"',
                'GENERATOR_TYPE_SINGLECONFIG="$CS_GENERATOR_TYPE_SINGLECONFIG"',
                'GENERATOR_TYPE_MULTICONFIG="$CS_GENERATOR_TYPE_MULTICONFIG"',
                'GENERATOR_CMAKE="$CS_GENERATOR_CMAKE"',
                'C_COMPILER="$CS_C_COMPILER"',
                'CPP_COMPILER="$CS_CPP_COMPILER"',
                "",
                ': "${INSTALL_FOLDER_NAME:?missing INSTALL_FOLDER_NAME}"',
                ': "${BUILD_FOLDER_NAME:?missing BUILD_FOLDER_NAME}"',
                ': "${GENERATOR_TYPE:?missing GENERATOR_TYPE}"',
                ': "${GENERATOR_TYPE_SINGLECONFIG:?missing GENERATOR_TYPE_SINGLECONFIG}"',
                ': "${GENERATOR_TYPE_MULTICONFIG:?missing GENERATOR_TYPE_MULTICONFIG}"',
                ': "${GENERATOR_CMAKE:?missing GENERATOR_CMAKE}"',
                "",
                "CMAKE_ARGS=()",
                "",
                '[[ -n "$C_COMPILER"   ]] && CMAKE_ARGS+=("-DCMAKE_C_COMPILER=$C_COMPILER")',
                '[[ -n "$CPP_COMPILER" ]] && CMAKE_ARGS+=("-DCMAKE_CXX_COMPILER=$CPP_COMPILER")',
                "",
                'mkdir -p "install/${INSTALL_FOLDER_NAME}/' + repo_name + '"',
                "",
                'if [[ "${GENERATOR_TYPE}" == "${GENERATOR_TYPE_SINGLECONFIG}" ]]; then',
                "",
                '    cd "${WORKSPACE_ROOT}"',
                "",
                '    mkdir -p "build/${BUILD_FOLDER_NAME}/' + repo_name + '/release"',
                '    cd "build/${BUILD_FOLDER_NAME}/' + repo_name + '/release"',
                "",
                '    "${WORKSPACE_ROOT}/'
                + repo_name
                + '/configure" -no-pch -skip qtwebengine -release -cmake-generator "${GENERATOR_CMAKE}" "${CMAKE_ARGS[@]}" -prefix "${WORKSPACE_ROOT}/install/${INSTALL_FOLDER_NAME}/'
                + repo_name
                + '"',
                "",
                "    cmake --build .",
                "",
                "    cmake --install .",
                "",
                'elif [[ "${GENERATOR_TYPE}" == "${GENERATOR_TYPE_MULTICONFIG}" ]]; then',
                "",
                '    mkdir -p "build/${BUILD_FOLDER_NAME}/' + repo_name + '"',
                '    cd "build/${BUILD_FOLDER_NAME}/' + repo_name + '"',
                "",
                '    "${WORKSPACE_ROOT}/'
                + repo_name
                + '/configure" -no-pch -skip qtwebengine  -cmake-generator "${GENERATOR_CMAKE}" "${CMAKE_ARGS[@]}" -prefix "${WORKSPACE_ROOT}/install/${INSTALL_FOLDER_NAME}/'
                + repo_name
                + '"',
                "",
                "    cmake --build . --config Release",
                "",
                "    cmake --install . --config Release",
                "",
                "else",
                '    echo "Unknown generator_type: ${GENERATOR_TYPE}"',
                "    exit 1",
                "fi",
            ],
            dry_run=dry_run,
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
                "",
                '& "${env:ProgramFiles(x86)}\\Microsoft Visual Studio\\Installer\\vswhere.exe" `',
                "    -latest `",
                "    -products * `",
                "    -property installationName",
                "",
                '& "${env:ProgramFiles(x86)}\\Microsoft Visual Studio\\Installer\\vswhere.exe" `',
                "    -latest `",
                "    -products * `",
                "    -property catalog_productDisplayVersion",
                "",
                'Write-Host ""',
                'Write-Host "=== MSVC ==="',
                "",
                "$cl = Get-Command cl.exe -ErrorAction Stop",
                "",
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
            cmd=["cd workspace/" + repo_name, "./init-repository.bat"],
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
            name="configure/build/install (Windows)",
            description="init repo",
            cmd=[
                "Set-StrictMode -Version Latest",
                "$ErrorActionPreference = 'Stop'",
                "",
                "# Enable long path support (Windows 10+)",
                "try {",
                '    New-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\" -Name "LongPathsEnabled" -Value 1 -Force | Out-Null',
                "} catch {",
                '    Write-Host "Unable to enable long paths, continuing..."',
                "}",
                "",
                "cd workspace",
                "",
                'if (!(Test-Path ".venv")) {',
                "    python -m venv .venv",
                "}",
                "",
                '& ".\\.venv\\Scripts\\Activate.ps1"',
                "",
                "python -m pip install --upgrade pip",
                "",
                "pip install html5lib",
                "",
                "$WORKSPACE_ROOT = Get-Location",
                '$BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"',
                '$INSTALL_FOLDER_NAME = "$CS_DIR_FROM_MATRIX"',
                '$GENERATOR_TYPE = "$CS_GENERATOR_TYPE"',
                '$GENERATOR_TYPE_SINGLECONFIG = "$CS_GENERATOR_TYPE_SINGLECONFIG"',
                '$GENERATOR_TYPE_MULTICONFIG = "$CS_GENERATOR_TYPE_MULTICONFIG"',
                '$GENERATOR_CMAKE = "$CS_GENERATOR_CMAKE"',
                '$C_COMPILER = "$CS_C_COMPILER"',
                '$CPP_COMPILER = "$CS_CPP_COMPILER"',
                '$TOOLSET="$CS_TOOLSET"',
                "",
                'New-Item -ItemType Directory -Force -Path "$WORKSPACE_ROOT/install/$INSTALL_FOLDER_NAME/'
                + repo_name
                + '" | Out-Null',
                "",
                'if ($TOOLSET -eq "ClangCL") {',
                '    if (-not $C_COMPILER) {',
                '        $C_COMPILER = "clang-cl.exe"',
                '    }',
                '',
                '    if (-not $CPP_COMPILER) {',
                '        $CPP_COMPILER = "clang-cl.exe"',
                '    }',
                '}',
                "",
                "$CMAKE_ARGS = @()",
                #'$CMAKE_ARGS += "-DCMAKE_RC_COMPILER_INIT=rc.exe"',
                #'$CMAKE_ARGS += "-DCMAKE_RC_COMPILER=rc.exe"',
                #'$CMAKE_ARGS += "-DCMAKE_RC_USE_RESPONSE_FILE=ON"',
                'if ($C_COMPILER) { $CMAKE_ARGS += "-DCMAKE_C_COMPILER=$C_COMPILER" }',
                'if ($CPP_COMPILER) { $CMAKE_ARGS += "-DCMAKE_CXX_COMPILER=$CPP_COMPILER" }',
                #'$CMAKE_ARGS += \'-DCMAKE_CXX_FLAGS_INIT=/D_SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS\'',
                "",
                "if ($GENERATOR_TYPE -eq $GENERATOR_TYPE_SINGLECONFIG) {",
                "",
                '    $RELEASE_DIR = "$WORKSPACE_ROOT/build/$BUILD_FOLDER_NAME/'
                + repo_name
                + '/release"',
                "    New-Item -ItemType Directory -Force -Path $RELEASE_DIR | Out-Null",
                "    Set-Location $RELEASE_DIR",
                "",
                '    & "$WORKSPACE_ROOT/'
                + repo_name
                + '/configure.bat" -no-pch -skip qtwebengine -release -cmake-generator $GENERATOR_CMAKE @CMAKE_ARGS -prefix "$WORKSPACE_ROOT/install/$INSTALL_FOLDER_NAME/'
                + repo_name
                + '"',
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "    cmake --build . ",
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "    cmake --install .",
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "",
                "}",
                "elseif ($GENERATOR_TYPE -eq $GENERATOR_TYPE_MULTICONFIG) {",
                "",
                '    $BUILD_DIR = "$WORKSPACE_ROOT/build/$BUILD_FOLDER_NAME/'
                + repo_name
                + '"',
                "    New-Item -ItemType Directory -Force -Path $BUILD_DIR | Out-Null",
                "    Set-Location $BUILD_DIR",
                "",
                '    & "$WORKSPACE_ROOT/'
                + repo_name
                + '/configure.bat" -no-pch -skip qtwebengine -cmake-generator $GENERATOR_CMAKE @CMAKE_ARGS -prefix "$WORKSPACE_ROOT/install/$INSTALL_FOLDER_NAME/'
                + repo_name
                + '"',
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "",
                "    cmake --build . -config Release",
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "",
                "    cmake --install . --config Release",
                "    if ($LASTEXITCODE) { exit $LASTEXITCODE }",
                "",
                "}",
                "else {",
                '    Write-Host "Unknown generator_type: $GENERATOR_TYPE"',
                "    exit 1",
                "}",
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
            repos_auto_search_list=[repo_name],
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
