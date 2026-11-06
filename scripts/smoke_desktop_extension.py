"""Exercise the packaged MCP over stdio in a fresh directory without real credentials."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def smoke() -> None:
    with tempfile.TemporaryDirectory(prefix='flin-mcpb-') as directory:
        with ZipFile(ROOT / 'dist/flin-linkedin-ads-mcp-macos.mcpb') as archive:
            archive.extractall(directory)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('LINKEDIN_', 'UV_PROJECT_', 'PYTHONPATH', 'VIRTUAL_ENV'))}
        env['LINKEDIN_TOKEN_FILE'] = str(Path(directory) / 'unused-tokens.json')
        env['PYTHONNOUSERSITE'] = '1'
        manifest = json.loads((Path(directory) / 'manifest.json').read_text())
        config = manifest['server']['mcp_config']
        args = [arg.replace('${__dirname}', directory) for arg in config['args']]
        params = StdioServerParameters(command=shutil.which('uv') or 'uv', args=args, env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert len(names) == 16, names
                assert {'linkedin_login', 'get_creative_media', 'search_ad_library'} <= names
                status = await session.call_tool('linkedin_login_status', {})
                result = json.loads(status.content[0].text)
                assert result['data']['status'] == 'not_connected', result
                denied = await session.call_tool('list_ad_accounts', {})
                assert json.loads(denied.content[0].text)['error']['code'] == 'auth_error'
        print('Packaged MCP: initialize, 16 tools, login status and unauthenticated access passed')


if __name__ == '__main__':
    asyncio.run(smoke())
