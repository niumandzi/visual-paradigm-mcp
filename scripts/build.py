#!/usr/bin/env python3
"""Build the plugin and fixed OpenAPI dispatcher; never touches an installed plugin."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VP = Path('/Applications/Visual Paradigm.app/Contents/Resources/app')


def build(vp_home=None):
    vp = Path(vp_home or os.environ.get('VP_HOME', DEFAULT_VP)).expanduser().resolve()
    jar = vp / 'lib/openapi.jar'
    if not jar.is_file():
        raise SystemExit(f'OpenAPI jar missing: {jar}; set VP_HOME or --vp-home')
    compiler = os.environ.get('JAVAC')
    if not compiler:
        homebrew = Path('/opt/homebrew/opt/openjdk@21/bin/javac')
        compiler = str(homebrew) if homebrew.is_file() else shutil.which('javac')
    if not compiler:
        raise SystemExit('JDK 11+ javac required; set JAVAC')
    targets = [('src/local/codex/Bridge.java', 'plugin/classes'),
               ('src/operations/Command.java', 'jobs')]
    with tempfile.TemporaryDirectory(prefix='.compile-', dir=ROOT) as temp:
        staging = Path(temp)
        for source, output in targets:
            target = staging / output
            target.mkdir(parents=True, exist_ok=True)
            subprocess.run([compiler, '--release', '11', '-encoding', 'UTF-8', '-cp', str(jar),
                            '-d', str(target), str(ROOT / source)], check=True)
        for artifact in staging.rglob('*.class'):
            target = ROOT / artifact.relative_to(staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(artifact, target)
    print('Built plugin/classes and jobs/Command.class (Java 11 bytecode)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vp-home', help='VP directory containing lib/openapi.jar')
    build(parser.parse_args().vp_home)
