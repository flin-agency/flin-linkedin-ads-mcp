# MCP v2 Compatibility Hotfix Design

## Goal

Restore `uvx flin-linkedin-ads-mcp` startup after MCP SDK 2.0 became the default resolver choice.

## Root Cause

The package declares `mcp>=1.0.0`, so a fresh `uvx` installation now selects MCP SDK 2.0.0. The server uses the MCP SDK v1 low-level decorators `Server.list_tools()` and `Server.call_tool()`, which were removed in v2. A developer's ignored local lockfile still resolved MCP 1.26.0, so local tests did not exercise the incompatible dependency resolution.

## Approaches Considered

1. Constrain MCP to the supported v1 line. This is the smallest safe repair and follows the MCP SDK's own migration guidance for projects not yet migrated to v2.
2. Migrate the low-level server handlers to MCP SDK v2. This broadens the change into a protocol SDK migration and requires adapting handler signatures, result models, and transport-level tests.
3. Add a compatibility adapter for both SDK major versions. This avoids a hard constraint but creates two runtime paths and substantially increases test and maintenance cost.

## Approved Design

Use approach 1. Change the runtime dependency to `mcp>=1.26,<2`, keeping the oldest version aligned with the repository's previously tested dependency set. Add a packaging regression test that proves MCP 1.26 is accepted and MCP 2.0 is rejected. Bump the package patch version to 0.1.2. The repository intentionally ignores `uv.lock`, so use `uv lock` only as a local resolver check and do not publish the generated lockfile.

No server behavior or LinkedIn API behavior changes. A future MCP SDK v2 migration should be handled separately with dedicated integration coverage.

## Verification

- Observe the new dependency-bound test fail against the current metadata.
- Apply the metadata change and observe the targeted test pass.
- Run all unit tests, Ruff, and mypy.
- Build wheel and source distribution from a clean tracked-file snapshot and inspect the wheel metadata.
- Install the wheel in a fresh environment and complete an MCP initialize/tools-list handshake.
- Push commit and release tag `v0.1.2`, then monitor the CI and release workflows. If a release gate fails before publication, fix the gate and use the next patch version rather than rewriting the failed tag.

## Release Recovery

The `v0.1.2` workflows exposed a Ruff version-skew failure before any package was published: local Ruff 0.15.7 passed, while CI resolved Ruff 0.16.1 and applied expanded defaults to pre-existing code. Preserve the project's intended lint gate explicitly with `select = ["E4", "E7", "E9", "F"]`, protect it with a metadata test, and publish the recovered package as 0.1.3.
