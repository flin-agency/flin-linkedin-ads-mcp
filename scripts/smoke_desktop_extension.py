"""Exercise the packaged MCP over stdio in a fresh directory without real credentials."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import tomllib
from zipfile import ZipFile

from packaging.version import Version
from packaging.requirements import Requirement

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def smoke(wheel: Path | None = None, upgrade_from: str | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix='flin-mcpb-') as directory:
        with ZipFile(ROOT / 'dist/flin-linkedin-ads-mcp-macos.mcpb') as archive:
            archive.extractall(directory)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('LINKEDIN_', 'UV_PROJECT_', 'PYTHONPATH', 'VIRTUAL_ENV'))}
        env['LINKEDIN_TOKEN_FILE'] = str(Path(directory) / 'unused-tokens.json')
        env['PYTHONNOUSERSITE'] = '1'
        if wheel is not None:
            # Prepublication integration test only; shipped manifest is unchanged.
            env['UV_FIND_LINKS'] = str(wheel.resolve().parent)
        manifest = json.loads((Path(directory) / 'manifest.json').read_text())
        config = manifest['server']['mcp_config']
        args = [arg.replace('${__dirname}', directory) for arg in config['args']]
        params = StdioServerParameters(command=shutil.which('uv') or 'uv', args=args, env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert len(names) == 17, names
                assert {'linkedin_login', 'get_creative_media', 'search_ad_library'} <= names
                status = await session.call_tool('connection_status', {})
                connection = json.loads(status.content[0].text)['data']
                assert connection['configuration_status'] == 'incomplete'
                assert connection['auth_status'] == 'unauthenticated'
                assert connection['live_access'] == 'not_checked'
                status = await session.call_tool('linkedin_login_status', {})
                result = json.loads(status.content[0].text)
                assert result['data']['status'] == 'not_connected', result
                denied = await session.call_tool('list_ad_accounts', {})
                assert json.loads(denied.content[0].text)['error']['code'] == 'auth_error'
        python = Path(directory) / '.venv' / 'bin' / 'python'
        installed = subprocess.check_output([
            str(python), '-c',
            'from importlib.metadata import version; print(version("flin-linkedin-ads-mcp"))',
        ], env=env, text=True).strip()
        assert connection['server_version'] == installed
        requirement = Requirement(tomllib.loads((Path(directory) / 'pyproject.toml').read_text())
                                  ['project']['dependencies'][0])
        assert Version(installed) in requirement.specifier
        assert not Version(installed).is_prerelease
        if upgrade_from is not None:
            token_file = Path(env['LINKEDIN_TOKEN_FILE'])
            token_file.write_text(json.dumps({
                'client_id': 'fixture-app', 'access_token': 'fixture-token',
                'expires_at': time.time() + 3600,
            }))
            token_file.chmod(0o600)
            before = token_file.read_bytes()
            env.update(LINKEDIN_CLIENT_ID='fixture-app', LINKEDIN_CLIENT_SECRET='fixture-secret')
            # This file represents client-owned settings, outside the installed server package.
            settings_file = Path(directory) / 'client-settings.json'
            settings_file.write_text(json.dumps({key: env[key] for key in (
                'LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET', 'LINKEDIN_TOKEN_FILE')}))
            before_settings = settings_file.read_bytes()
            project = Path(directory) / 'pyproject.toml'
            original_project = project.read_text()
            requirement = tomllib.loads(original_project)['project']['dependencies'][0]
            project.write_text(original_project.replace(requirement, f'flin-linkedin-ads-mcp=={upgrade_from}'))

            async def check_saved_login(expected_version, has_connection_status):
                configured_params = StdioServerParameters(command=params.command, args=args, env=env)
                async with stdio_client(configured_params) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()
                        result = await session.call_tool('linkedin_login_status', {})
                        data = json.loads(result.content[0].text)['data']
                        assert data['status'] == 'token_available' and data['oauth_configured']
                        if has_connection_status:
                            result = await session.call_tool('connection_status', {})
                            data = json.loads(result.content[0].text)['data']
                            assert data['server_version'] == expected_version
                            assert data['auth_status'] == 'unknown' and data['live_access'] == 'not_checked'
                actual = subprocess.check_output([
                    str(python), '-c',
                    'from importlib.metadata import version; print(version("flin-linkedin-ads-mcp"))',
                ], env=env, text=True).strip()
                assert actual == expected_version, (actual, expected_version)
                assert token_file.read_bytes() == before
                assert token_file.stat().st_mode & 0o777 == 0o600
                assert settings_file.read_bytes() == before_settings

            await check_saved_login(upgrade_from, False)
            project.write_text(original_project)
            await check_saved_login(installed, True)
            print(f'Existing install upgraded: {upgrade_from} -> {installed}; settings/token bytes preserved')
        print(f'Installed stable server: {installed}')
        print('Packaged MCP: initialize, 17 tools, login status and unauthenticated access passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheel', type=Path, help='Test a local wheel before PyPI publication')
    parser.add_argument('--upgrade-from', help='Verify existing installed version and saved login survive an update')
    options = parser.parse_args()
    asyncio.run(smoke(options.wheel, options.upgrade_from))
