#!/usr/bin/env node
// Standard MCP stdio client. It never imports handlers or accesses VP's IPC files.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

export async function connect() {
  const child = spawn(process.env.VP_MCP_PYTHON || 'python3',
    [fileURLToPath(new URL('./mcp_server.py', import.meta.url))], { stdio: ['pipe', 'pipe', 'pipe'] });
  child.stderr.pipe(process.stderr);
  const pending = new Map();
  let nextId = 0;
  const fail = error => {
    for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(error); }
    pending.clear();
  };
  child.on('error', fail);
  child.on('exit', code => fail(new Error(`MCP server exited (${code})`)));
  const lines = createInterface({ input: child.stdout });
  lines.on('line', line => {
    try {
      const message = JSON.parse(line);
      const entry = pending.get(message.id);
      if (!entry) return;
      pending.delete(message.id);
      clearTimeout(entry.timer);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
      else entry.resolve(message.result);
    } catch (error) { fail(error); }
  });
  function rpc(method, params = {}) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`MCP timeout: ${method}; a write's outcome may be unknown. Do not replay it.`));
      }, 45000);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    });
  }
  const close = () => {
    child.stdin.end();
    lines.close();
    fail(new Error('MCP client closed'));
    const timer = setTimeout(() => child.kill(), 1000);
    timer.unref();
  };
  try {
    await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {},
      clientInfo: { name: 'visual-paradigm-stdio-client', version: '1.0.0' } });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
    return { rpc, close };
  } catch (error) { close(); throw error; }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const client = await connect();
  try {
    const [operation, name, rawArguments] = process.argv.slice(2);
    let result;
    if (operation === 'list') result = await client.rpc('tools/list');
    else if (operation === 'call') {
      const catalog = await client.rpc('tools/list');
      if (!catalog.tools.some(tool => tool.name === name)) throw new Error(`Unknown MCP tool: ${name}`);
      result = await client.rpc('tools/call', { name, arguments: JSON.parse(rawArguments || '{}') });
      if (result.isError) process.exitCode = 1;
    } else throw new Error('Usage: mcp_client.mjs list | call TOOL JSON_ARGUMENTS');
    console.log(JSON.stringify(result, null, 2));
  } finally { client.close(); }
}
