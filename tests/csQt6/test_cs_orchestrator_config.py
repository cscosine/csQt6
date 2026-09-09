from copy import deepcopy

from csorchestrator.domain.context.context_compiler_generator import (
    Compiler,
    ContextCompilerGenerator,
    GeneratorWithType,
)
from csorchestrator.domain.context.context_os_architecture import OS
from csorchestrator.frontend.cscmake_presets.supported_variants import get_supported_context_os_architecture_list

from csQt6.cs_orchestrator_config import qt6_mapping


def test_cs_orchestrator_config() -> None:

    all = get_supported_context_os_architecture_list()

    for config in all:
        res = qt6_mapping(deepcopy(config))  # deep copy to be sure
        assert res is not None

        if config.context_os_architecture.os == OS.LINUX:
            assert res.context_os_architecture == config.context_os_architecture
            assert res.context_compiler_generator == ContextCompilerGenerator(
                compiler_family=Compiler.GCC,
                compiler_version=ContextCompilerGenerator.COMPILER_VERSION_DEFAULT,
                build_generator=GeneratorWithType.NINJA,
            )
        elif config.context_os_architecture.os == OS.WINDOWS:
            assert res.context_compiler_generator == ContextCompilerGenerator(
                compiler_family=Compiler.MSVC,
                compiler_version=ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17,
                build_generator=GeneratorWithType.NINJA,
            )
        else:
            raise AssertionError("non expected config")
