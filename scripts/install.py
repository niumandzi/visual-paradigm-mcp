#!/usr/bin/env python3
"""Install a built plugin. Does not restart VP, register MCP, or open/save any project."""
import argparse
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def install(plugin_dir, replace=False):
    destination = Path(plugin_dir).expanduser().resolve() / 'local-codex-bridge'
    if not (ROOT / 'plugin/classes/local/codex/Bridge.class').is_file() or not (ROOT / 'jobs/Command.class').is_file():
        raise SystemExit('Run scripts/build.py first')
    if any((ROOT / 'ipc' / name).exists() for name in ['request.properties', 'inflight.json']):
        raise SystemExit('IPC request is pending; resolve it before installation')
    if destination.exists():
        if not replace:
            raise SystemExit('Plugin exists; save work, close VP, then use --replace')
        backup = ROOT / 'backups' / ('installed-plugin-' + uuid.uuid4().hex)
        backup.parent.mkdir(exist_ok=True)
        shutil.copytree(destination, backup)
        print(f'Previous installed plugin copied to {backup}')
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'plugin', destination, dirs_exist_ok=True)
    escaped = str(ROOT).replace('\\', '\\\\').replace(' ', '\\ ')
    (destination / 'bridge.properties').write_text(f'root={escaped}\n', encoding='utf-8')
    for name in ['ipc', 'jobs']:
        folder = ROOT / name
        folder.mkdir(exist_ok=True)
        folder.chmod(0o700)
    print(f'Installed to {destination}; restart VP after saving work to load the new plugin')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', required=True, help='Parent plugin directory shown by VP Install Plugin dialog')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    install(args.plugin_dir, args.replace)
