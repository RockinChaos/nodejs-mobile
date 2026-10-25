#!/usr/bin/env python3
"""Check the reconstructed source and run the upstream GYP unit tests."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from prepare import ROOT, git


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / '.build/node')
    parser.add_argument('--unit-tests', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    lock = json.loads((ROOT / 'node-source.json').read_text())
    if git(source, 'write-tree').decode().strip() != lock['tree']:
        parser.exit(1, 'The source index does not match the reconstructed tree.\n')
    if git(source, 'diff', '--name-only'):
        parser.exit(1, 'The reconstructed source contains unstaged edits.\n')
    header = (source / 'src/node_version.h').read_text()
    version = '.'.join(re.search(rf'#define NODE_{part}_VERSION\s+(\d+)', header).group(1)
                       for part in ('MAJOR', 'MINOR', 'PATCH'))
    if version != lock['version']:
        parser.exit(1, f'Wrong upstream version: {version}\n')
    changed = [Path(os.fsdecode(path)) for path in
               git(source, 'diff', 'HEAD', '--name-only', '-z').split(b'\0') if path]
    for path in changed:
        if path.suffix in ('.gyp', '.gypi'):
            ast.literal_eval((source / path).read_text())
        elif path.suffix == '.py':
            ast.parse((source / path).read_text(), filename=str(path))
    for path in (ROOT / 'scripts').glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    git(source, 'diff', 'HEAD', '--check')
    print(f'Verified Node {version}, {len(changed)} mobile source files, GYP/Python syntax and whitespace.')
    if args.unit_tests:
        env = dict(os.environ, PYTHONPATH=str(source / 'tools/gyp/pylib'))
        subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                        '-s', str(source / 'tools/gyp/pylib/gyp'), '-p', '*_test.py'],
                       cwd=source, env=env, check=True)


if __name__ == '__main__':
    main()
