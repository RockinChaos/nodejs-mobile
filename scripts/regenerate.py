#!/usr/bin/env python3
"""Export edits in a generated tree back to the existing patch series."""

import argparse
import json
import os
from pathlib import Path
import subprocess

from prepare import ROOT, git, overlay_files, series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / '.build/node')
    args = parser.parse_args()
    source = args.source.resolve()
    lock = json.loads((ROOT / 'node-source.json').read_text())
    if git(source, 'rev-parse', 'HEAD').decode().strip() != lock['commit']:
        parser.exit(1, 'The generated source is not based on the pinned upstream commit.\n')
    owned = set()
    updates = []
    for name in series():
        patch = ROOT / 'patches' / name
        header = patch.read_bytes().split(b'diff --git ', 1)[0]
        stats = git(source, 'apply', '--numstat', '-z', str(patch)).split(b'\0')
        paths = [os.fsdecode(row.split(b'\t', 2)[2]) for row in stats if row]
        if owned.intersection(paths):
            parser.exit(1, 'Each upstream file must belong to exactly one patch.\n')
        owned.update(paths)
        diff = git(source, 'diff', 'HEAD', '--binary', '--full-index',
                   '--no-textconv', '--no-ext-diff', '--', *paths)
        if not diff:
            parser.exit(1, f'{name} is now empty. Remove it from the series explicitly.\n')
        updates.append((patch, header + diff))
    overlays = overlay_files()
    changed = {os.fsdecode(path) for path in git(source, 'diff', 'HEAD', '--name-only', '-z').split(b'\0') if path}
    unexpected = changed - owned - {path.as_posix() for path in overlays}
    untracked = git(source, 'ls-files', '--others', '--exclude-standard').decode().strip()
    if unexpected or untracked:
        parser.exit(1, f'Unassigned source edits: {sorted(unexpected)}; untracked: {untracked}\n'
                    'Assign upstream files to a patch, or add new mobile files under src/ or tools/ first.\n')
    for patch, data in updates:
        patch.write_bytes(data)
    for path in overlays:
        (ROOT / path).write_bytes((source / path).read_bytes())
    # A separate index avoids staging the source tree or parent repository.
    index = source / '.git/mobile-export.index'
    if index.exists():
        parser.exit(1, f'Temporary index already exists: {index}\n')
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        git(source, 'read-tree', 'HEAD', env=env)
        git(source, 'add', '-f', '--', *sorted(owned), *[path.as_posix() for path in overlays], env=env)
        lock['tree'] = git(source, 'write-tree', env=env).decode().strip()
    finally:
        index.unlink(missing_ok=True)
    (ROOT / 'node-source.json').write_text(json.dumps(lock, indent=2) + '\n',
                                         encoding='utf-8', newline='\n')
    print(f'Exported {len(updates)} patches. Reconstruct a fresh tree to verify {lock["tree"]}.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
