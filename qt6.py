#!/usr/bin/env python3
import sys
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent

from csorchestrator.application.cli.cli import orchestrator_main_with_default_run
from csorchestrator.application.factory.factory import (
    OptionalOrchestratorWithReport,
)
from csorchestrator.application.recipes.create_orchestrator import create_default_orchestrator
from csorchestrator.domain.context.context_compiler_generator import (
    Compiler,
    ContextCompilerGenerator,
    GeneratorWithType,
)
from csorchestrator.domain.context.context_os_architecture import (
    ARCHITECTURE_VARIANT_GENERIC,
    OS,
    UBUNTU_STRING_PREFIX,
    Architecture,
    ContextOsArchitecture,
)
from csorchestrator.domain.context.context_os_architecture_compiler_generator import (
    ContextOsArchitectureCompilerGenerator,
)
from csorchestrator.foundation.core.report import Report
from csorchestrator.foundation.git.resolve_url import RepoUrlParts
from csorchestrator.frontend.cscmake_presets.supported_variants import (
    get_supported_os_version_list,
)
from csorchestrator.frontend.github_workflow_translation.github_workflow_matrix_constants import (
    MatrixOsArchCompilerGeneratorGithubConstants,
)
from csorchestrator.frontend.local_execution.step_utils import (
    StepExecuteOnlyOn,
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
)
from csorchestrator.frontend.step.step_create_archives import StepCreateArchives
from csorchestrator.frontend.step.step_custom_command import (
    StepBashScriptCommand,
    StepInstallAptPackages,
    StepWinPSCommand,
)
from csorchestrator.frontend.step.step_get_repository import StepGetRepositoryExtraDepthOne, StepGetRepositoryGitHub
from csorchestrator.frontend.step.step_get_versions_from_cmake_config_package_version import (
    StepGetVersionsFromCMakeConfigPackageVersion,
)
from csorchestrator.frontend.step.step_github_action import StepAddGitHubAction
from csorchestrator.frontend.step.step_upload_artifacts import (
    StepUploadArtifacts,
    create_artifact_prefix_from_orchestrator_name_version,
)
from csorchestrator.portable.package_version import PackageVersion


def populate_build_matrix() -> list[ContextOsArchitectureCompilerGenerator]:
    retList: list[ContextOsArchitectureCompilerGenerator] = []

    ## LINUX. use multi-config for x64 arch, use single config for arm64 arch
    for os_version in get_supported_os_version_list(OS.LINUX):
        for arch in [Architecture.X64, Architecture.ARM64]:
            os_arch = ContextOsArchitecture(
                os=OS.LINUX,
                os_version=os_version,
                architecture=arch,
                architecture_variant=ARCHITECTURE_VARIANT_GENERIC,
            )
            generator = GeneratorWithType.NINJA
            compiler = Compiler.GCC

            ccg = ContextCompilerGenerator(
                compiler_family=compiler,
                compiler_version=ContextCompilerGenerator.COMPILER_VERSION_DEFAULT,
                build_generator=generator,
            )
            retList.append(
                ContextOsArchitectureCompilerGenerator(context_os_architecture=os_arch, context_compiler_generator=ccg)
            )

    ## WINDOWS, need to use ninja generator on msvc 2022
    for os_version in get_supported_os_version_list(OS.WINDOWS):
        os_arch = ContextOsArchitecture(
            os=OS.WINDOWS,
            os_version=os_version,
            architecture=Architecture.X64,
            architecture_variant=ARCHITECTURE_VARIANT_GENERIC,
        )

        generator = GeneratorWithType.NINJA
        compiler = Compiler.MSVC
        version = ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17

        ccg = ContextCompilerGenerator(
            compiler_family=compiler,
            compiler_version=version,
            build_generator=generator,
        )
        retList.append(
            ContextOsArchitectureCompilerGenerator(context_os_architecture=os_arch, context_compiler_generator=ccg)
        )

    return retList


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")

    # please keep version aligned with qt version
    qt_version_tag = "v6.11.1"

    o = create_default_orchestrator(
        name="Qt6", version=qt_version_tag, base_install_dir=base_install_dir, populate_default_matrix=False
    )

    o.execution_matrix.os_architecture_compiler_generator_list = populate_build_matrix()

    repo_name = "qt6"

    p = o.create_phase("Repo Update")
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
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    free_disk_script = r"""
    set -euo pipefail

    # Show available space
    df -h

    # Remove unnecessary tools/packages (do not fail if they are not installed)
    sudo apt-get remove -y '^ghc-8.*' '^dotnet-.*' '^mongodb.*' 'mysql-.*' 'php.*' 'powershell' 'snap.*' || true
    sudo apt-get autoremove -y
    sudo apt-get clean

    # Remove large directories
    sudo rm -rf /usr/local/lib/android || true
    sudo rm -rf /opt/hostedtoolcache || true

    # Show available space
    df -h
    """

    p.add_step(
        StepBashScriptCommand(
            name="Free disk space (Linux-Ubuntu)",
            description="Free disk space by removing unnecessary packages and directories",
            cmd=dedent(free_disk_script).strip().splitlines(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
        .add_extra(StepSkipExecutionOnLocal())
    )

    p = o.create_phase("Configure-Build-Test-Install (Linux-Ubuntu)")
    init_repo_script_linux = rf"""
    set -euo pipefail

    cd workspace/{repo_name}
    ./init-repository
    """
    p.add_step(
        StepBashScriptCommand(
            name="init repo (Linux-Ubuntu)",
            description="init repo",
            cmd=dedent(init_repo_script_linux).strip().splitlines(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    configure_repo_script = rf"""
    set -euo pipefail

    ROOT_FOLDER=$(pwd)

    FOLDER_NAME="$CS_DIR_FROM_MATRIX"
    : "${{FOLDER_NAME:?missing FOLDER_NAME}}"

    REPO_FOLDER="${{ROOT_FOLDER}}/workspace/{repo_name}"
    BUILD_FOLDER="${{ROOT_FOLDER}}/workspace/build/${{FOLDER_NAME}}/{repo_name}/release"
    INSTALL_FOLDER="${{ROOT_FOLDER}}/workspace/install/${{FOLDER_NAME}}/{repo_name}"

    mkdir -p "${{INSTALL_FOLDER}}"
    mkdir -p "${{BUILD_FOLDER}}"

    cd "${{BUILD_FOLDER}}"

    "${{REPO_FOLDER}}/configure" -no-pch -skip qtwebengine -release -prefix "${{INSTALL_FOLDER}}"
    """
    p.add_step(
        StepBashScriptCommand(
            name="Configure (Linux-Ubuntu)",
            description="configure repo",
            cmd=dedent(configure_repo_script).strip().splitlines(),
        ).add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    build_linux_script = rf"""
    set -euo pipefail

    ROOT_FOLDER=$(pwd)

    FOLDER_NAME="$CS_DIR_FROM_MATRIX"
    : "${{FOLDER_NAME:?missing FOLDER_NAME}}"

    BUILD_FOLDER="${{ROOT_FOLDER}}/workspace/build/${{FOLDER_NAME}}/{repo_name}/release"

    cd "${{BUILD_FOLDER}}"

    cmake --build .
    cmake --install .
    """
    p.add_step(
        StepBashScriptCommand(
            name="Build (Linux-Ubuntu)",
            description="build and install repo",
            cmd=dedent(build_linux_script).strip().splitlines(),
        ).add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    # ----------------- WINDOWS -----------------
    p = o.create_phase("Configure-Build-Test-Install (Windows)")

    p.add_step(
        StepAddGitHubAction(
            name="Setup MSVC",
            description="setup MSVC environment",
            uses="TheMrMilchmann/setup-msvc-dev@v4",
            with_list={"arch": f"{MatrixOsArchCompilerGeneratorGithubConstants.MATRIX_ARCHITECTURE_EMBRACED}"},
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    show_msvc_version_script = r"""
    Write-Host "=== Visual Studio ==="

    & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" `
        -latest `
        -products * `
        -property installationName

    & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" `
        -latest `
        -products * `
        -property catalog_productDisplayVersion

    Write-Host ""
    Write-Host "=== MSVC ==="

    $cl = Get-Command cl.exe -ErrorAction Stop

    Write-Host "cl.exe:"
    Write-Host $cl.Source
    """
    p.add_step(
        StepWinPSCommand(
            name="Show MSVC Version (Windows)",
            description="show msvc verison",
            cmd=dedent(show_msvc_version_script).strip().splitlines(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    init_repo_script_windows = rf"""
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    cd workspace/{repo_name}
    ./init-repository.bat
    """
    p.add_step(
        StepWinPSCommand(
            name="init repo (Windows)",
            description="init repo",
            cmd=dedent(init_repo_script_windows).strip().splitlines(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    configure_repo_script_windows = rf"""
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    if (!(Test-Path ".venv")) {{
        python -m venv .venv
    }}
    & ".\.venv\Scripts\Activate.ps1"
    python -m pip install --upgrade pip
    pip install html5lib

    $ROOT_FOLDER = Get-Location

    $FOLDER_NAME = "$CS_DIR_FROM_MATRIX"
    $BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"

    $REPO_FOLDER="$ROOT_FOLDER/workspace/{repo_name}"
    $BUILD_FOLDER="$ROOT_FOLDER/workspace/build/$BUILD_FOLDER_NAME/{repo_name}/release"
    $INSTALL_FOLDER="$ROOT_FOLDER/workspace/install/$FOLDER_NAME/{repo_name}"

    New-Item -ItemType Directory -Force -Path "$INSTALL_FOLDER" | Out-Null
    New-Item -ItemType Directory -Force -Path "$BUILD_FOLDER" | Out-Null

    Set-Location $BUILD_FOLDER

    & "$REPO_FOLDER/configure.bat" -no-pch -skip qtwebengine -release -prefix "$INSTALL_FOLDER"
    if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}
    """

    p.add_step(
        StepWinPSCommand(
            name="Configure (Windows)",
            description="configure repo",
            cmd=dedent(configure_repo_script_windows).strip().splitlines(),
            dry_run=False,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    build_windows_script = rf"""
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    $ROOT_FOLDER = Get-Location

    $BUILD_FOLDER_NAME = "build-$CS_MATRIX_EXEC_ID"

    $BUILD_FOLDER="$ROOT_FOLDER/workspace/build/$BUILD_FOLDER_NAME/{repo_name}/release"


    Set-Location $BUILD_FOLDER

    cmake --build .
    if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}
    cmake --install .
    if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}
    """

    p.add_step(
        StepWinPSCommand(
            name="Build (Windows)",
            description="build and install repo",
            cmd=dedent(build_windows_script).strip().splitlines(),
            dry_run=False,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p = o.create_phase("Create and Upload Artifacts")

    p.add_step(
        StepGetVersionsFromCMakeConfigPackageVersion(
            name="Get Versions",
            description="Get Versions for all libs",
            repos_version=[PackageVersion(repo_name, qt_version_tag)],
            base_install_dir=base_install_dir,
        )
    )

    p.add_step(
        StepCreateArchives(
            name="Create Archives",
            description="Create archives with libs and versions",
            base_install_dir=base_install_dir,
        ).add_extra(StepSkipExecutionOnLocal())
    )

    p.add_step(
        StepUploadArtifacts(
            name="Upload Artifacts",
            description="Upload Artifacts with libs and versions",
            base_install_dir=base_install_dir,
            artifact_prefix=create_artifact_prefix_from_orchestrator_name_version(o),
        ).add_extra(StepSkipExecutionOnLocal())
    )

    return OptionalOrchestratorWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
