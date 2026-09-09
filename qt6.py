#!/usr/bin/env python3
import sys
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent

from csorchestrator.application.cli.cli import orchestrator_main_with_default_run
from csorchestrator.application.factory.factory import OptionalOrchestratorWithReport
from csorchestrator.application.recipes.checkout_build import create_and_upload_artifacts
from csorchestrator.application.recipes.create_orchestrator import (
    create_default_execution_matrix,
    create_default_orchestrator,
)
from csorchestrator.domain.context.context_os_architecture import OS, UBUNTU_STRING_PREFIX
from csorchestrator.foundation.core.report import Report
from csorchestrator.foundation.git.resolve_url import RepoUrlParts
from csorchestrator.frontend.github_workflow_translation.github_workflow_matrix_constants import (
    MatrixOsArchCompilerGeneratorGithubConstants,
)
from csorchestrator.frontend.local_execution.step_utils import (
    StepExecuteOnlyOn,
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
)
from csorchestrator.frontend.step.step_custom_command import (
    StepBashScriptCommand,
    StepInstallAptPackages,
    StepWinPSCommand,
)
from csorchestrator.frontend.step.step_get_repository import StepGetRepositoryExtraDepthOne, StepGetRepositoryGitHub
from csorchestrator.frontend.step.step_github_action import StepAddGitHubAction
from csorchestrator.portable.package_version import PackageVersion

from utils.atp_packages_list import get_atp_packages_list
from utils.build_matrix import populate_build_matrix
from utils.scripts import (
    build_linux_script,
    build_windows_script,
    configure_repo_script_linux,
    configure_repo_script_windows,
    free_disk_script,
    init_repo_script_linux,
    init_repo_script_windows,
    show_msvc_version_script,
)


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")

    # please keep version aligned with qt version
    qt_version_tag = "v6.11.1"

    o = create_default_orchestrator(
        name="Qt6",
        version=qt_version_tag,
        base_install_dir=base_install_dir,
        populate_default_matrix=False,
        additional_files_list=[Path("csQt6/cs_orchestrator_config.py")],
    )

    o.execution_matrix = create_default_execution_matrix(populate_build_matrix())

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
            packages=get_atp_packages_list(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

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
    p.add_step(
        StepBashScriptCommand(
            name="init repo (Linux-Ubuntu)",
            description="init repo",
            cmd=dedent(init_repo_script_linux(repo_name)).strip().splitlines(),
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    p.add_step(
        StepBashScriptCommand(
            name="Configure (Linux-Ubuntu)",
            description="configure repo",
            cmd=dedent(configure_repo_script_linux(repo_name)).strip().splitlines(),
        ).add_extra(StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX))
    )

    p.add_step(
        StepBashScriptCommand(
            name="Build (Linux-Ubuntu)",
            description="build and install repo",
            cmd=dedent(build_linux_script(repo_name)).strip().splitlines(),
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

    p.add_step(
        StepWinPSCommand(
            name="init repo (Windows)",
            description="init repo",
            cmd=dedent(init_repo_script_windows(repo_name)).strip().splitlines(),
            dry_run=False,
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
            cmd=dedent(configure_repo_script_windows(repo_name)).strip().splitlines(),
            dry_run=False,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    p.add_step(
        StepWinPSCommand(
            name="Build (Windows)",
            description="build and install repo",
            cmd=dedent(build_windows_script(repo_name)).strip().splitlines(),
            dry_run=False,
        ).add_extra(
            StepExecuteOnlyOn(
                os=OS.WINDOWS,
            )
        )
    )

    create_and_upload_artifacts(
        orchestrator=o,
        base_install_dir=base_install_dir,
        repos_version_list=[PackageVersion(repo_name, qt_version_tag)],
    )

    return OptionalOrchestratorWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
