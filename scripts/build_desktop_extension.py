"""Build a deterministic MCPB from an explicit allowlist, never from the worktree root."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def build(output_dir: Path | None = None) -> Path:
    extension = ROOT / 'desktop-extension'
    manifest = json.loads((extension / 'manifest.json').read_text())
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    launcher = tomllib.loads((extension / 'pyproject.toml').read_text())
    if manifest['version'] != launcher['project']['version']:
        raise ValueError('Launcher project and extension versions must match')
    server_version = project['project']['version']
    requirement = Requirement(launcher['project']['dependencies'][0])
    if Version(server_version) not in requirement.specifier or Version(server_version).is_prerelease:
        raise ValueError('Released server must be a stable version supported by the launcher')
    files = {name: extension / name for name in (
        'manifest.json', 'pyproject.toml', 'README.md', 'LICENSE', 'server/main.py',
    )}
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
    names = [archive.name, 'flin-linkedin-ads-mcp.mcpb',
             f"flin-linkedin-ads-mcp-{server_version}-macos.mcpb"]
    for name in names[1:]:
        (output_dir / name).write_bytes(archive.read_bytes())
    (output_dir / 'SHA256SUMS').write_text(''.join(f'{checksum}  {name}\n' for name in names))
    return archive


if __name__ == '__main__':
    print(build())
