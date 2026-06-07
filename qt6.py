#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from typing import Sequence, TypeAlias

from csorchestrator.core.report import Report
from csorchestrator.context.context_os_architecture import OS, UBUNTU_STRING_PREFIX
from csorchestrator.step.step_utils import StepExecuteOnlyOn
from csorchestrator.orchestrator.orchestrator import (
    Orchestrator,
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
from csorchestrator.utils.presets.supported_variants import BuildConfig
from csorchestrator.core.optional_result_with_report import OptionalResultWithReport
from csorchestrator.cli.cli import orchestrator_main_with_default_run
from csorchestrator.context.context_os_architecture_compiler_generator import (
    ExecutionMatrixOsArchCompilerGenerator,
)
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
    qt_version_tag = "v6.10.2"

    o = create_orchestrator_factory_all_supported_cases(
        "Qt6", version=qt_version_tag, execution_matrix_name="orchestrator-matrix"
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

    p = o.create_phase("Repo Update")
    if flag_repo_update:
        p.add_step(
            StepGetRepositoryGitHub(
                name="qt6",
                description=f"Clone or pull-ff qt6",
                target_directory=(base_target_dir / "qt6").as_posix(),
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
            ],
            dry_run=dry_run,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p = o.create_phase(f"Configure-Build-Test-Install (Linux-Ubuntu)")
    p.add_step(
        StepBashScriptCommand(
            name="init repo (Linux-Ubuntu)",
            description="init repo",
            cmd=["cd workspace/qt6", "./init-repository"],
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
                'FOLDER_NAME="$CS_DIR_FROM_MATRIX"',
                'GENERATOR_TYPE="$CS_GENERATOR_TYPE"',
                'GENERATOR_TYPE_SINGLECONFIG="$CS_GENERATOR_TYPE_SINGLECONFIG"',
                'GENERATOR_TYPE_MULTICONFIG="$CS_GENERATOR_TYPE_MULTICONFIG"',
                'GENERATOR_CMAKE="$CS_GENERATOR_CMAKE"',
                'C_COMPILER="$CS_C_COMPILER"',
                'CPP_COMPILER="$CS_CPP_COMPILER"',
                "",
                ': "${FOLDER_NAME:?missing FOLDER_NAME}"',
                ': "${GENERATOR_TYPE:?missing GENERATOR_TYPE}"',
                ': "${GENERATOR_TYPE_SINGLECONFIG:?missing GENERATOR_TYPE_SINGLECONFIG}"',
                ': "${GENERATOR_TYPE_MULTICONFIG:?missing GENERATOR_TYPE_MULTICONFIG}"',
                ': "${GENERATOR_CMAKE:?missing GENERATOR_CMAKE}"',
                "",
                'mkdir -p "install/${FOLDER_NAME}/qt6"',
                "",
                'if [[ "${GENERATOR_TYPE}" == "${GENERATOR_TYPE_SINGLECONFIG}" ]]; then',
                '    mkdir -p "build/${FOLDER_NAME}/qt6/debug"',
                '    cd "build/${FOLDER_NAME}/qt6/debug"',
                '    "${WORKSPACE_ROOT}/qt6/configure" -debug -cmake-generator "${GENERATOR_CMAKE}" ${C_COMPILER:+-DCMAKE_C_COMPILER="${C_COMPILER}"} ${CPP_COMPILER:+-DCMAKE_CXX_COMPILER="${CPP_COMPILER}"} -prefix "${WORKSPACE_ROOT}/install/${FOLDER_NAME}/qt6"',
                "    cmake --build . --parallel",
                "    cmake --install .",
                "",
                '    cd "${WORKSPACE_ROOT}"',
                "",
                '    mkdir -p "build/${FOLDER_NAME}/qt6/release"',
                '    cd "build/${FOLDER_NAME}/qt6/release"',
                '    "${WORKSPACE_ROOT}/qt6/configure" -release -cmake-generator "${GENERATOR_CMAKE}" ${C_COMPILER:+-DCMAKE_C_COMPILER="${C_COMPILER}"} ${CPP_COMPILER:+-DCMAKE_CXX_COMPILER="${CPP_COMPILER}"} -prefix "${WORKSPACE_ROOT}/install/${FOLDER_NAME}/qt6"',
                "    cmake --build . --parallel",
                "    cmake --install .",
                "",
                'elif [[ "${GENERATOR_TYPE}" == "${GENERATOR_TYPE_MULTICONFIG}" ]]; then',
                '    mkdir -p "build/${FOLDER_NAME}/qt6"',
                '    cd "build/${FOLDER_NAME}/qt6"',
                '    "${WORKSPACE_ROOT}/qt6/configure" -cmake-generator "${GENERATOR_CMAKE}" ${C_COMPILER:+-DCMAKE_C_COMPILER="${C_COMPILER}"} ${CPP_COMPILER:+-DCMAKE_CXX_COMPILER="${CPP_COMPILER}"} -prefix "${WORKSPACE_ROOT}/install/${FOLDER_NAME}/qt6"',
                "    cmake --build . --config Debug --parallel",
                "    cmake --build . --config Release --parallel",
                "    cmake --install . --config Debug",
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

    p = o.create_phase(f"Configure-Build-Test-Install (Windows)")
    p.add_step(
        StepWinPSCommand(
            name="init repo (Windows)",
            description="init repo",
            cmd=["cd workspace/qt6", "./init-repository.bat"],
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
                "cd workspace",
                "",
                "$WORKSPACE_ROOT = Get-Location",
                '$FOLDER_NAME = "$CS_DIR_FROM_MATRIX"',
                '$GENERATOR_TYPE = "$CS_GENERATOR_TYPE"',
                '$GENERATOR_TYPE_SINGLECONFIG = "$CS_GENERATOR_TYPE_SINGLECONFIG"',
                '$GENERATOR_TYPE_MULTICONFIG = "$CS_GENERATOR_TYPE_MULTICONFIG"',
                '$GENERATOR_CMAKE = "$CS_GENERATOR_CMAKE"',
                '$C_COMPILER = "$CS_C_COMPILER"',
                '$CPP_COMPILER = "$CS_CPP_COMPILER"',
                "",
                'New-Item -ItemType Directory -Force -Path "$WORKSPACE_ROOT/install/$FOLDER_NAME/qt6" | Out-Null',
                "",
                "$CMAKE_ARGS = @()",
                'if ($C_COMPILER) { $CMAKE_ARGS += "-DCMAKE_C_COMPILER=$C_COMPILER" }',
                'if ($CPP_COMPILER) { $CMAKE_ARGS += "-DCMAKE_CXX_COMPILER=$CPP_COMPILER" }',
                "",
                "if ($GENERATOR_TYPE -eq $GENERATOR_TYPE_SINGLECONFIG) {",
                "",
                '    $DEBUG_DIR = "$WORKSPACE_ROOT/build/$FOLDER_NAME/qt6/debug"',
                "    New-Item -ItemType Directory -Force -Path $DEBUG_DIR | Out-Null",
                "    Set-Location $DEBUG_DIR",
                "",
                '    & "$WORKSPACE_ROOT/qt6/configure.bat" -debug -cmake-generator $GENERATOR_CMAKE @CMAKE_ARGS -prefix "$WORKSPACE_ROOT/install/$FOLDER_NAME/qt6"',
                "    cmake --build . --parallel",
                "    cmake --install .",
                "",
                '    $RELEASE_DIR = "$WORKSPACE_ROOT/build/$FOLDER_NAME/qt6/release"',
                "    New-Item -ItemType Directory -Force -Path $RELEASE_DIR | Out-Null",
                "    Set-Location $RELEASE_DIR",
                "",
                '    & "$WORKSPACE_ROOT/qt6/configure.bat" -release -cmake-generator $GENERATOR_CMAKE @CMAKE_ARGS -prefix "$WORKSPACE_ROOT/install/$FOLDER_NAME/qt6"',
                "    cmake --build . --parallel",
                "    cmake --install .",
                "",
                "}",
                "elseif ($GENERATOR_TYPE -eq $GENERATOR_TYPE_MULTICONFIG) {",
                "",
                '    $BUILD_DIR = "$WORKSPACE_ROOT/build/$FOLDER_NAME/qt6"',
                "    New-Item -ItemType Directory -Force -Path $BUILD_DIR | Out-Null",
                "    Set-Location $BUILD_DIR",
                "",
                '    & "$WORKSPACE_ROOT/qt6/configure.bat" -cmake-generator $GENERATOR_CMAKE @CMAKE_ARGS -prefix "$WORKSPACE_ROOT/install/$FOLDER_NAME/qt6"',
                "",
                "    cmake --build . --config Debug --parallel",
                "    cmake --build . --config Release --parallel",
                "",
                "    cmake --install . --config Debug",
                "    cmake --install . --config Release",
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

    # TODO build
    # old build command, as bck
    ## mkdir -p ../build/linux-gcc/qt6/
    ## mkdir -p ../install/linux-gcc/qt6/

    ## cd ../build/linux-gcc/qt6/
    ## ../../../qt6/configure -prefix ../../../install/linux-gcc/qt6/
    ## cmake --build . --parallel 4
    ## cmake --install .

    p = o.create_phase(f"Create and Upload Artifacts")

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
