"""Build a deterministic MCPB from an explicit allowlist, never from the worktree root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def build(output_dir: Path | None = None) -> Path:
    extension = ROOT / 'desktop-extension'
    manifest = json.loads((extension / 'manifest.json').read_text())
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    launcher = tomllib.loads((extension / 'pyproject.toml').read_text())
    versions = {manifest['version'], project['project']['version'], launcher['project']['version']}
    if len(versions) != 1:
        raise ValueError('Server and extension versions must match')
    files = {name: extension / name for name in (
        'manifest.json', 'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE', 'server/main.py',
    )}
    source = ROOT / 'src'
    files.update({f'server/{path.relative_to(source).as_posix()}': path
                  for path in sorted((source / 'flin_linkedin_ads_mcp').rglob('*.py'))})
    output_dir = output_dir or ROOT / 'dist'
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / 'flin-linkedin-ads-mcp-macos.mcpb'
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as bundle:
        for name, path in sorted(files.items()):
            if path.is_symlink():
                raise ValueError(f'Refusing symlink: {name}')
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output_dir / 'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    print(build())
