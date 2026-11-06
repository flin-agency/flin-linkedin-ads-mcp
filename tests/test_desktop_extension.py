from __future__ import annotations

import hashlib
import importlib.util
import json
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
        expected = {'manifest.json', 'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE', 'server/main.py'}
        expected.update('server/' + p.relative_to(ROOT / 'src').as_posix()
                        for p in (ROOT / 'src').rglob('*.py'))
        assert set(archive.namelist()) == expected
        for path in (ROOT / 'src').rglob('*.py'):
            assert archive.read('server/' + path.relative_to(ROOT / 'src').as_posix()) == path.read_bytes()
        manifest = json.loads(archive.read('manifest.json'))
        args = manifest['server']['mcp_config']['args']
        assert '--locked' in args
        assert not any('upgrade' in arg or 'refresh' in arg for arg in args)
        assert manifest['user_config']['client_secret']['sensitive'] is True
