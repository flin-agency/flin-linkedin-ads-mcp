from __future__ import annotations

import hashlib
import importlib.util
import json
import tomllib
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_is_reproducible_and_contains_only_release_files(tmp_path):
    spec = importlib.util.spec_from_file_location('build_desktop', ROOT / 'scripts/build_desktop_extension.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = module.build(tmp_path)
    first = bundle.read_bytes()
    assert module.build(tmp_path).read_bytes() == first
    assert (tmp_path / 'SHA256SUMS').read_text().startswith(hashlib.sha256(first).hexdigest())
    with ZipFile(bundle) as archive:
        expected = {'manifest.json', 'pyproject.toml', 'README.md', 'LICENSE', 'server/main.py'}
        # Bundled code would shadow PyPI and silently prevent automatic updates.
        assert set(archive.namelist()) == expected
        manifest = json.loads(archive.read('manifest.json'))
        args = manifest['server']['mcp_config']['args']
        assert '--locked' not in args
        assert args[args.index('--upgrade-package') + 1] == 'flin-linkedin-ads-mcp'
        assert args[args.index('--refresh-package') + 1] == 'flin-linkedin-ads-mcp'
        assert args[args.index('--prerelease') + 1] == 'disallow'
        assert manifest['user_config']['client_secret']['sensitive'] is True
        for line in (tmp_path / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split()
            assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
        assert (tmp_path / 'flin-linkedin-ads-mcp.mcpb').read_bytes() == first
        release_version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
        assert (tmp_path / f"flin-linkedin-ads-mcp-{release_version}-macos.mcpb").read_bytes() == first


def test_launcher_updates_stable_package_on_restart(tmp_path):
    """A cached install must upgrade without importing shadowing bundled modules."""
    import os
    import shutil
    import subprocess
    import pytest

    uv = shutil.which('uv')
    if not uv:
        pytest.skip('UV is required for the desktop update integration test')
    extension = tmp_path / 'extension'
    shutil.copytree(ROOT / 'desktop-extension', extension,
                    ignore=shutil.ignore_patterns('.venv', 'uv.lock', '__pycache__'))
    wheels = tmp_path / 'wheels'
    wheels.mkdir()

    def wheel(version):
        distribution = f'flin_linkedin_ads_mcp-{version}'
        info = distribution + '.dist-info'
        with ZipFile(wheels / (distribution + '-py3-none-any.whl'), 'w') as archive:
            archive.writestr('flin_linkedin_ads_mcp/__init__.py', '')
            archive.writestr('flin_linkedin_ads_mcp/server.py', f'def main(): print("{version}")\n')
            archive.writestr(info + '/METADATA',
                             f'Metadata-Version: 2.3\nName: flin-linkedin-ads-mcp\nVersion: {version}\n')
            archive.writestr(info + '/WHEEL',
                             'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
            archive.writestr(info + '/RECORD', '\n'.join(
                f'{name},,' for name in [*archive.namelist(), info + '/RECORD']) + '\n')

    manifest = json.loads((extension / 'manifest.json').read_text())
    args = [arg.replace('${__dirname}', str(extension))
            for arg in manifest['server']['mcp_config']['args']]
    env = dict(os.environ, UV_NO_INDEX='1', UV_FIND_LINKS=str(wheels),
               UV_CACHE_DIR=str(tmp_path / 'cache'))
    env.pop('VIRTUAL_ENV', None)
    env.pop('PYTHONPATH', None)
    base = manifest['version']
    major, minor, patch = map(int, base.split('.'))
    newer = f'{major}.{minor}.{patch + 1}'
    prerelease = f'{major}.{minor}.{patch + 2}rc1'
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text(json.dumps({'client_id': 'test-app', 'client_secret': 'fixture-secret'}))
    token_file = tmp_path / 'tokens.json'
    token_file.write_text(json.dumps({'access_token': 'fixture-token', 'client_id': 'test-app'}))
    before_settings, before_token = settings_file.read_bytes(), token_file.read_bytes()
    env.update(LINKEDIN_TOKEN_FILE=str(token_file), LINKEDIN_CLIENT_ID='test-app',
               LINKEDIN_CLIENT_SECRET='fixture-secret', PYTHONNOUSERSITE='1', PYTHONPATH='')
    # A user-level UV config must not redirect resolution for the packaged launcher.
    config = tmp_path / 'config' / 'uv'
    config.mkdir(parents=True)
    (config / 'uv.toml').write_text('resolution = "lowest"\n')
    env['XDG_CONFIG_HOME'] = str(config.parent)
    wheel(base)
    first = subprocess.run([uv, *args], env=env, text=True, capture_output=True, check=True)
    assert first.stdout.strip() == base
    wheel(newer)
    wheel(prerelease)
    wheel('1.0.0')
    second = subprocess.run([uv, *args], env=env, text=True, capture_output=True, check=True)
    assert second.stdout.strip() == newer, second.stderr
    assert settings_file.read_bytes() == before_settings
    assert token_file.read_bytes() == before_token
    assert '1.0.0' not in second.stdout
    # Explicit recovery after installation; does not contact an index or update packages.
    fallback = [uv, 'run', '--no-config', '--directory', str(extension), '--offline',
                '--no-sync', 'server/main.py']
    cached = subprocess.run(fallback, env=env, text=True, capture_output=True, check=True)
    assert cached.stdout.strip() == newer
