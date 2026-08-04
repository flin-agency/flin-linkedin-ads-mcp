from __future__ import annotations

from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.version import Version


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_dependency_accepts_supported_v1_and_rejects_v2() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    requirements = [Requirement(value) for value in pyproject["project"]["dependencies"]]
    mcp_requirement = next(requirement for requirement in requirements if requirement.name == "mcp")

    assert Version("1.26.0") in mcp_requirement.specifier
    assert Version("2.0.0") not in mcp_requirement.specifier


def test_metadata_test_dependencies_are_declared_directly() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    dev_requirements = [
        Requirement(value) for value in pyproject["project"]["optional-dependencies"]["dev"]
    ]

    assert any(requirement.name == "packaging" for requirement in dev_requirements)


def test_ruff_uses_stable_explicit_rule_selection() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    assert pyproject["tool"]["ruff"].get("lint", {}).get("select") == ["E4", "E7", "E9", "F"]


def test_ci_installs_build_frontend_before_running_it() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    install_command = 'python -m pip install -e ".[dev]" build'
    build_command = "run: python -m build"

    assert install_command in workflow
    assert build_command in workflow
    assert workflow.index(install_command) < workflow.index(build_command)
