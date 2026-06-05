#!/usr/bin/env python3
import sys
from pathlib import Path
from typing import Sequence, TypeAlias

from csorchestrator.core.report import Report
from csorchestrator.orchestrator.orchestrator import Orchestrator, OptionalOrchestratorWithReport, create_orchestrator_factory_all_supported_cases
from csorchestrator.step.step_get_repository import RepoUrlParts, StepGetRepositoryGitHub, StepGetRepositoryExecuteOnlyOncePerMatrix,StepGetRepositoryExtraDepthOne
from csorchestrator.step.step_cmake_command import StepCMakeWorkflow
from csorchestrator.step.step_custom_command import StepBashScriptCommand, StepInstallAptPackages
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
from csorchestrator.step.step_get_versions_from_cmake_config_package_version import StepGetVersionsFromCMakeConfigPackageVersion, CMakeConfigPackageVersionGrep
from csorchestrator.step.step_create_archives import StepCreateArchives
from csorchestrator.step.step_upload_artifacts import StepUploadArtifacts

def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")

    # please keep version aligned with qt version
    qt_version_tag = "v6.10.2"

    o = create_orchestrator_factory_all_supported_cases("Qt6", version=qt_version_tag, execution_matrix_name = "orchestrator-matrix")
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
        job=
        JobReleaseCreationFromArifacts(
            name="release-from-artifacts",
            needs="orchestrator-matrix",
            runs_on="ubuntu-latest",
            if_str="${{ github.ref_type == 'tag' }}"
        )
    )

    flag_repo_update = True

    p = o.create_phase("Repo Update")
    if flag_repo_update:
        p.add_step(
            StepGetRepositoryGitHub(
                name="qt6",
                description=f"Clone or pull-ff qt6",
                target_directory=str(base_target_dir / "qt6"),
                repo_url_parts= RepoUrlParts(
                    repo_base_url=StepGetRepositoryGitHub.GITHUB_BASE_URL_SSH,
                    repo_org="qt",
                    repo_name="qt5" + ".git",                        
                ),
                repo_ref=qt_version_tag,
            ).add_extra(
                StepGetRepositoryExtraDepthOne(
                    on_local_checkout=True, # shallow copy, huge repo
                    on_github_action_checkout=True,
                )
            ).add_extra(
                StepGetRepositoryExecuteOnlyOncePerMatrix()
            )
        )

    p = o.create_phase("Install Requirements")
    p.add_step(StepInstallAptPackages(
        name = 'install apt packages',
        description = 'install apt packages if not already installed in the system',
        packages = [
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
        ]
    )) # TODO use smt like StepGetRepositoryExecuteOnlyOncePerMatrix() --> generalize to smt generic? mabe based on (phase-step) as unique id for detecting single exec

    p = o.create_phase(f"Configure-Build-Test-Install")
    p.add_step(StepBashScriptCommand(
        name = 'init repo',
        description = 'init repo',
        cmd=['cd workspace/qt6','./init-repository']
    )) # TODO repo init need also single exec in matrix

    # TODO build
    # old build command, as bck
    ## mkdir -p ../build/linux-gcc/qt6/
    ## mkdir -p ../install/linux-gcc/qt6/

    ## cd ../build/linux-gcc/qt6/
    ## ../../../qt6/configure -prefix ../../../install/linux-gcc/qt6/
    ## cmake --build . --parallel 4
    ## cmake --install .        

    p = o.create_phase(f"Create and Upload Artifacts")

    # p.add_step(
    #     StepCreateArchives(
    #         name = "Create Archives",
    #         description= "Create archives with libs and versions",
    #         input_id = "versions",
    #         input_dict = "packages",
    #         base_install_dir = base_install_dir,
    #     )
    # )

    # p.add_step(
    #     StepUploadArtifacts(
    #         name = "Upload Artifacts",
    #         description= "Upload Artifacts with libs and versions",
    #         base_install_dir = base_install_dir,
    #     )
    # )

    return OptionalResultWithReport.createResultAndReport(o, report)

def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())