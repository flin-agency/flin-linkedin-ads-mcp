# Release policy

- Every server release must be published to **both PyPI and GitHub**. This is an explicit
  user requirement: existing PyPI/uvx installations depend on PyPI releases for updates.
- Do not report a release as complete until the exact version and distribution hashes have
  been verified on PyPI and the GitHub installation assets are available.
- Use `.github/workflows/release.yml` and its `pypi` environment for Trusted Publishing.
  The workflow can recover an existing tag through `workflow_dispatch` with `release_tag`.
- A queued macOS runner must not block PyPI: the release builder runs on Linux, while
  macOS checks run separately in CI. Do not cancel publishing and deliver GitHub only.
- Preserve published tags and files. For code changes, create a new version; for a failed
  publication, recover the existing version without changing its source or artifacts.
- Distinguish PyPI updates from the update behavior of the desktop extension. Do not claim
  that a bundled, locked MCPB automatically updates its server through PyPI.
