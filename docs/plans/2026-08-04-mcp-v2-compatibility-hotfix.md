# MCP v2 Compatibility Hotfix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore fresh `uvx` startup by preventing the v1-based server from resolving MCP SDK 2.x.

**Architecture:** Keep the existing MCP SDK v1 server implementation unchanged and enforce its supported major-version boundary in package metadata. Protect the boundary with a test that evaluates the declared requirement semantically, then validate the built wheel in a fresh environment.

**Tech Stack:** Python 3.11+, `tomllib`, `packaging`, `pytest`, `uv`, MCP Python SDK v1

---

### Task 1: Add the dependency-bound regression test

**Files:**
- Create: `tests/test_package_metadata.py`
- Modify: `pyproject.toml` dev dependencies

**Step 1: Write the failing test**

Parse `pyproject.toml`, locate the MCP requirement with `packaging.requirements.Requirement`, and assert that version 1.26.0 is included while version 2.0.0 is excluded.

Declare `packaging` directly in the `dev` extra because the regression test imports it.

**Step 2: Run the targeted test and verify RED**

Run: `pytest tests/test_package_metadata.py -q`

Expected: FAIL because the current `mcp>=1.0.0` requirement accepts 2.0.0.

### Task 2: Constrain the SDK and prepare patch release metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Step 1: Write the minimal metadata fix**

Change the runtime requirement to `mcp>=1.26,<2` and bump the project version from 0.1.1 to 0.1.2.

**Step 2: Check dependency resolution locally**

Run: `uv lock`

Expected: the generated local lock reflects version 0.1.2 and the upper bound, with MCP remaining on a compatible v1 release. `uv.lock` is ignored by repository policy and must not be staged.

**Step 3: Run the targeted test and verify GREEN**

Run: `pytest tests/test_package_metadata.py -q`

Expected: PASS.

### Task 3: Verify source and package behavior

**Files:**
- Verify: all source, tests, and distribution metadata

**Step 1: Run the complete local quality gates**

Run: `pytest -q`, `ruff check .`, and `mypy src`.

Expected: all commands exit successfully.

**Step 2: Build the distributions**

Run: `uv build` from a clean tracked-file snapshot.

Expected: wheel and source distribution for 0.1.2 are created.

**Step 3: Inspect wheel metadata**

Confirm the wheel declares `Requires-Dist: mcp<2,>=1.26`.

**Step 4: Exercise a fresh install**

Install the wheel into an isolated environment and send MCP `initialize` and `tools/list` requests over stdio with a dummy LinkedIn token.

Expected: the process stays up through initialization and returns the registered tools without the `Server.list_tools` crash.

### Task 4: Publish the patch release

**Files:**
- Stage only the metadata, test, and plan documents from this hotfix. Do not stage the ignored local lockfile.

**Step 1: Review the final diff and secret scan**

Run: `git status --short`, `git diff --check`, and inspect the staged diff.

**Step 2: Commit**

Run: `git commit -m "fix: constrain MCP SDK to v1"`.

**Step 3: Push the commit**

Run: `git push origin main`.

**Step 4: Trigger the release action**

Create annotated tag `v0.1.2` and push it to origin. The tag triggers `.github/workflows/release.yml`.

**Step 5: Monitor GitHub Actions**

Wait for both CI and Release workflows and report their final conclusions and release URL.

### Task 5: Recover from version-sensitive Ruff defaults if required

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_package_metadata.py`

**Step 1: Reproduce with the CI Ruff version**

Run: `uvx ruff@0.16.1 check .`

Expected before the fix: FAIL because Ruff 0.16.1 enables additional rules over pre-existing source.

**Step 2: Add a failing lint-policy metadata test**

Assert that `[tool.ruff.lint]` explicitly selects `E4`, `E7`, `E9`, and `F`.

**Step 3: Make the lint policy explicit**

Add the explicit rule selection and bump the unpublished recovery release to 0.1.3.

**Step 4: Verify with both local and CI Ruff versions**

Run the metadata test, `ruff check .`, and `uvx ruff@0.16.1 check .`.

Expected: all commands pass with the same rule policy.

**Step 5: Publish recovery release**

Push `main`, create tag `v0.1.3`, and monitor CI and Release through PyPI publication and GitHub Release creation.

### Task 6: Repair the standalone CI build step

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_package_metadata.py`

**Step 1: Reproduce in an isolated dev environment**

Run: `uv run --isolated --extra dev python -m build`.

Expected before the fix: FAIL with `No module named build`.

**Step 2: Add a failing workflow contract test**

Assert that CI installs the `build` frontend before invoking `python -m build`.

**Step 3: Install the missing CI-only frontend**

Add `build` to the CI pip install command without changing published package dependencies.

**Step 4: Verify and push**

Run the full local quality gates, push `main`, and monitor the new main CI run to completion. No new release tag is required because the 0.1.3 Release workflow already succeeded.
