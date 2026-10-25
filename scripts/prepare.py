#!/usr/bin/env python3
"""Reconstruct a mobile source tree without changing the upstream submodule."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(directory, *args, **kwargs):
    return subprocess.check_output(
        ['git', '-c', 'core.longpaths=true', '-C', str(directory), *args],
        **kwargs,
    )


def series():
    names = [line.strip() for line in (ROOT / 'patches/series').read_text().splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if len(names) != len(set(names)):
        raise RuntimeError('Duplicate patch in patches/series')
    for name in names:
        if Path(name).name != name or not name.endswith('.patch'):
            raise RuntimeError(f'Invalid patch name: {name}')
    return names


def overlay_files():
    paths = git(ROOT, 'ls-files', '-z', '--cached', '--others',
                '--exclude-standard', '--', 'src', 'tools').split(b'\0')
    return sorted({Path(os.fsdecode(path)) for path in paths if path})


def source_inputs_digest():
    digest = hashlib.sha256()
    paths = [Path('node-source.json'), Path('patches/series')]
    paths += [Path('patches') / name for name in series()]
    paths += overlay_files()
    for path in paths:
        digest.update(path.as_posix().encode() + b'\0')
        digest.update((ROOT / path).read_bytes())
    return digest.hexdigest()


def prepare(destination, update_lock=False):
    destination = destination.resolve()
    if destination.exists():
        raise RuntimeError(f'Output already exists: {destination}. Use a new output directory.')
    if (not destination.is_relative_to(ROOT) or '.git' in destination.relative_to(ROOT).parts
            or destination.is_relative_to(ROOT / 'node')):
        raise RuntimeError('The output must be inside this workspace, outside .git and node.')
    upstream = ROOT / 'node'
    lock = json.loads((ROOT / 'node-source.json').read_text())
    if not (upstream / '.git').exists():
        raise RuntimeError('Initialize upstream first: git submodule update --init --depth 1')
    actual = git(upstream, 'rev-parse', 'HEAD').decode().strip()
    recorded = git(ROOT, 'ls-files', '--stage', '--', 'node').decode().split()
    if actual != lock['commit'] or recorded[:2] != ['160000', lock['commit']]:
        raise RuntimeError('The submodule, gitlink and node-source.json must pin the same commit.')
    if git(upstream, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError('The upstream submodule must be pristine. Edit the generated tree instead.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--quiet', str(destination)], check=True)
    # Share the initialized submodule's immutable objects. A local clone of a
    # shallow repository can repack its entire object store on Windows.
    objects = git(upstream, 'rev-parse', '--path-format=absolute', '--git-path', 'objects').decode().strip()
    (destination / '.git/objects/info/alternates').write_text(
        Path(objects).as_posix() + '\n', encoding='utf-8', newline='\n')
    shallow = Path(git(upstream, 'rev-parse', '--path-format=absolute', '--git-path', 'shallow').decode().strip())
    if shallow.is_file():
        shutil.copyfile(shallow, destination / '.git/shallow')
    git(destination, 'config', 'core.longpaths', 'true')
    git(destination, 'config', 'core.autocrlf', 'false')
    git(destination, 'config', 'core.filemode', 'false' if os.name == 'nt' else 'true')
    git(destination, 'checkout', '--quiet', '--detach', lock['commit'])
    for name in series():
        patch = str(ROOT / 'patches' / name)
        git(destination, 'apply', '--check', '--index', '--whitespace=error-all', patch)
        git(destination, 'apply', '--index', '--whitespace=error-all', patch)
        print(f'Applied {name}', flush=True)
    upstream_paths = set(git(destination, 'ls-tree', '-rz', '--name-only', 'HEAD').split(b'\0'))
    for path in overlay_files():
        name = path.as_posix()
        if os.fsencode(name) in upstream_paths:
            raise RuntimeError(f'Overlay shadows an upstream file; use a patch: {name}')
        source = ROOT / path
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        git(destination, 'add', '-f', '--', name)
    tree = git(destination, 'write-tree').decode().strip()
    if update_lock:
        lock['tree'] = tree
        (ROOT / 'node-source.json').write_text(json.dumps(lock, indent=2) + '\n',
                                             encoding='utf-8', newline='\n')
    elif tree != lock['tree']:
        raise RuntimeError(f'Reconstructed tree {tree} differs from pinned tree {lock["tree"]}')
    (destination / '.git/mobile-source.json').write_text(
        json.dumps({'tree': tree, 'source_inputs_sha256': source_inputs_digest()}) + '\n',
        encoding='utf-8', newline='\n',
    )
    print(f'Verified Node {lock["version"]}: {tree}\nSource: {destination}', flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.build/node')
    parser.add_argument('--update-lock', action='store_true',
                        help='explicitly record a newly reviewed reconstructed tree')
    args = parser.parse_args()
    try:
        prepare(args.output, args.update_lock)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
