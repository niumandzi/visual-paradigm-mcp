#!/usr/bin/env python3
"""Internal single-writer transport. Agents use MCP, never import this module."""
import fcntl
import json
from pathlib import Path
import os
import time
import uuid

ROOT = Path(os.environ.get('VP_MCP_ROOT', Path(__file__).resolve().parent)).resolve()
IPC = ROOT / 'ipc'


def properties(values):
    def escape(value):
        return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace(' ', '\\ ').replace('=', '\\=').replace(':', '\\:')
    return ''.join(f'{key}={escape(value)}\n' for key, value in values.items())


def request(op='snapshot', job=None, parameters=None):
    with (IPC / 'client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ready = IPC / 'ready.json'
        if not ready.exists():
            raise RuntimeError('Visual Paradigm bridge is not running')
        if (IPC / 'request.properties').exists() or (IPC / 'inflight.json').exists():
            raise RuntimeError('A request is pending; inspect its outcome before retrying')
        if parameters is not None:
            (IPC / 'command.properties').write_text(properties(parameters), encoding='utf-8')
        request_id = str(uuid.uuid4())
        values = {'id': request_id, 'op': op}
        if job is not None:
            values['class'] = job
        temp = IPC / 'request.tmp'
        temp.write_text(properties(values), encoding='utf-8')
        (IPC / 'inflight.json').write_text(json.dumps({'id': request_id, 'op': op, 'job': job}), encoding='utf-8')
        temp.replace(IPC / 'request.properties')
        result = IPC / f'{request_id}.json'
        deadline = time.monotonic() + 20
        while not result.exists():
            if time.monotonic() > deadline:
                raise TimeoutError(f'No response to {request_id}; outcome unknown, do not replay writes')
            time.sleep(0.1)
        data = json.loads(result.read_text(encoding='utf-8'))
        (IPC / 'inflight.json').unlink()
        if not data['ok']:
            raise RuntimeError(data['error'])
        return data['result']


if __name__ == '__main__':
    raise SystemExit('Internal transport. Use mcp_client.mjs or a registered MCP client.')
