#!/usr/bin/env python3
"""Build and package the pinned mobile library, or combine CI artifacts."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shlex
import shutil
import struct
import subprocess
import sys

from prepare import ROOT, git, prepare
from versions import dependency_versions

ANDROID = {
    'arm': ('armeabi-v7a', 'armv7a-linux-androideabi'),
    'arm64': ('arm64-v8a', 'aarch64-linux-android'),
    'x64': ('x86_64', 'x86_64-linux-android'),
}
OPENSSL_ARCHS = {'linux-elf', 'linux-armv4', 'linux-aarch64', 'linux-x86_64',
                 'darwin64-arm64-cc', 'darwin64-x86_64-cc'}
EXPORTS = ('napi_get_cb_info', 'napi_create_string_utf8', 'napi_throw_error', 'uv_loop_init')


def output_path(path):
    path = path.resolve()
    if path.exists():
        raise RuntimeError(f'Output already exists: {path}')
    if not path.is_relative_to(ROOT) or path.relative_to(ROOT).parts[0] in ('.git', 'node'):
        raise RuntimeError('Output must be inside the workspace, outside .git and node.')
    return path


def run(args, **kwargs):
    print(shlex.join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def config(path):
    return ast.literal_eval(path.read_text())['variables']


def copy_headers(source, destination):
    run([sys.executable, source / 'tools/install.py', 'install', '--headers-only',
         '--silent', '--prefix', '/', '--dest-dir', destination], cwd=source)
    headers = destination / 'include/node'
    # Keep the public V8 headers historically shipped by nodejs-mobile;
    # tools/install.py has a narrower allowlist.
    for path in (source / 'deps/v8/include').glob('v8*.h'):
        shutil.copyfile(path, headers / path.name)
    for path in (headers / 'openssl/archs').iterdir():
        if path.is_dir() and path.name not in OPENSSL_ARCHS:
            shutil.rmtree(path)
    shutil.copyfile(source / 'src/node_mobile_version.h', headers / 'node_mobile_version.h')
    shutil.copyfile(source / 'LICENSE', destination / 'LICENSE')
    shutil.copyfile(ROOT / 'LICENSE', destination / 'LICENSE-nodejs-mobile')
    for name in ('node.h', 'node_api.h', 'common.gypi', 'config.gypi', 'v8-fast-api-calls.h'):
        if not (headers / name).is_file():
            raise RuntimeError(f'Missing public header: {name}')


def compiler_environment():
    env = os.environ.copy()
    env['CC_host'] = shutil.which('clang') or ''
    env['CXX_host'] = shutil.which('clang++') or ''
    if not env['CC_host'] or not env['CXX_host']:
        raise RuntimeError('Host clang and clang++ are required.')
    if not shutil.which('ninja'):
        raise RuntimeError('Ninja is required on PATH.')
    env['AR_host'] = shutil.which('ar') or 'ar'
    return env


def set_compiler_commands(env):
    for name in ('CC', 'CXX', 'CC_host', 'CXX_host'):
        env[name] = shlex.quote(env[name])
    env['CC_target'] = env['CC']
    env['CXX_target'] = env['CXX']


def verify_elf(path, arch):
    data = path.read_bytes()
    expected_machine = {'arm': 40, 'arm64': 183, 'x64': 62}[arch]
    if data[:4] != b'\x7fELF' or data[5] != 1:
        raise RuntimeError('Expected a little-endian Android ELF library.')
    if struct.unpack_from('<H', data, 18)[0] != expected_machine:
        raise RuntimeError(f'Wrong ELF architecture for {arch}')
    if data[4] == 2:
        offset = struct.unpack_from('<Q', data, 32)[0]
        size, count = struct.unpack_from('<HH', data, 54)
        align_offset, align_format = 48, '<Q'
    else:
        offset = struct.unpack_from('<I', data, 28)[0]
        size, count = struct.unpack_from('<HH', data, 42)
        align_offset, align_format = 28, '<I'
    loads = 0
    for index in range(count):
        start = offset + index * size
        if struct.unpack_from('<I', data, start)[0] == 1:
            loads += 1
            if struct.unpack_from(align_format, data, start + align_offset)[0] < 16384:
                raise RuntimeError('ELF LOAD segment is not 16 KB aligned.')
    if not loads:
        raise RuntimeError('ELF has no LOAD segments.')


def verify_exports(command, prefix=''):
    output = subprocess.check_output([str(arg) for arg in command], text=True)
    names = set()
    for line in output.splitlines():
        fields = line.split()
        if not fields or 'UND' in fields:
            continue
        if fields[0].endswith(':') and (len(fields) < 8 or fields[3] != 'FUNC'
                                       or fields[4] not in ('GLOBAL', 'WEAK')
                                       or fields[5] not in ('DEFAULT', 'PROTECTED')):
            continue
        names.add(fields[-1].split('@')[0])
    missing = {prefix + name for name in EXPORTS} - names
    if missing:
        raise RuntimeError(f'Missing dynamic exports: {sorted(missing)}')


def strip_android(library, symbols, toolchain):
    symbols.parent.mkdir(parents=True)
    run([toolchain / 'bin/llvm-objcopy', '--only-keep-debug', library, symbols])
    run([toolchain / 'bin/llvm-strip', '--strip-unneeded', library])
    run([toolchain / 'bin/llvm-objcopy', f'--add-gnu-debuglink={symbols}', library])
    size = library.stat().st_size / (1024 * 1024)
    print(f'{library}: {size:.2f} MiB after stripping.', flush=True)


def record(destination, source, target):
    lock = json.loads((ROOT / 'node-source.json').read_text())
    lock['target'] = target
    lock['versions'] = dependency_versions(source, config(source / 'config.gypi'))
    lock['config_sha256'] = hashlib.sha256((source / 'config.gypi').read_bytes()).hexdigest()
    lock['binary_sha256'] = {path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in destination.rglob('*') if path.is_file()
                             and not path.is_relative_to(destination / 'symbols')
                             and (path.name == 'libnode.so' or path.name == 'NodeMobile')}
    lock['symbols_sha256'] = {path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (destination / 'symbols').rglob('*') if path.is_file()}
    (destination / 'build-info.json').write_text(json.dumps(lock, indent=2) + '\n')


def build_android(args):
    if platform.system() != 'Linux':
        raise RuntimeError('Android builds currently require a Linux host.')
    if args.api < 24:
        raise RuntimeError('The minimum Android API is 24.')
    output = output_path(args.output)
    ndk = args.ndk.resolve()
    toolchain = ndk / 'toolchains/llvm/prebuilt/linux-x86_64'
    abi, triple = ANDROID[args.arch]
    env = compiler_environment()
    env['CC'] = str(toolchain / f'bin/{triple}{args.api}-clang')
    env['CXX'] = str(toolchain / f'bin/{triple}{args.api}-clang++')
    env['AR'] = env['AR_target'] = str(toolchain / 'bin/llvm-ar')
    env['NM_target'] = str(toolchain / 'bin/llvm-nm')
    env['READELF_target'] = str(toolchain / 'bin/llvm-readelf')
    if not Path(env['CC']).is_file():
        raise RuntimeError(f'Invalid NDK or API: {env["CC"]}')
    env['GYP_DEFINES'] = shlex.join([
        f'target_arch={args.arch}', f'v8_target_arch={args.arch}',
        f'android_target_arch={args.arch}', 'host_os=linux', 'OS=android',
        f'android_ndk_path={ndk}', f'android_ndk_sysroot={toolchain / "sysroot"}',
    ])
    env['LDFLAGS'] = '-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 -Wl,--build-id=sha1'
    set_compiler_commands(env)
    for name in ('CC', 'CXX'):
        run([*shlex.split(env[name]), '--version'], env=env)
    source = prepare(args.source)
    run([sys.executable, source / 'configure.py', '--dest-os=android', f'--dest-cpu={args.arch}',
         '--cross-compiling', '--shared', '--openssl-no-asm', '--with-intl=none',
         '--without-npm', '--without-corepack', '--ninja'], cwd=source, env=env)
    git(source, 'diff', '--quiet', '--no-ext-diff', '--no-textconv')
    run(['ninja', '-C', source / 'out/Release', '-j', args.jobs, 'libnode'], env=env)
    candidates = [source / 'out/Release' / name for name in
                  ('lib/libnode.so', 'lib.target/libnode.so', 'obj.target/libnode.so', 'libnode.so')]
    library = next((path for path in candidates if path.is_file()), None)
    if library is None:
        raise RuntimeError('The libnode target did not produce libnode.so.')
    verify_elf(library, args.arch)
    verify_exports([toolchain / 'bin/llvm-readelf', '--dyn-syms', '--wide', library])
    variables = config(source / 'config.gypi')
    if (variables['OS'], variables['target_arch'], variables['node_shared']) != ('android', args.arch, 'true'):
        raise RuntimeError('The Android build configuration does not match the requested target.')
    (output / 'bin' / abi).mkdir(parents=True)
    packaged = output / 'bin' / abi / 'libnode.so'
    shutil.copyfile(library, packaged)
    strip_android(packaged, output / 'symbols' / abi / 'libnode.so.debug', toolchain)
    verify_elf(packaged, args.arch)
    verify_exports([toolchain / 'bin/llvm-readelf', '--dyn-syms', '--wide', packaged])
    copy_headers(source, output)
    record(output, source, abi)


def build_ios(args):
    if platform.system() != 'Darwin':
        raise RuntimeError('iOS builds require macOS and Xcode.')
    output = output_path(args.output)
    arch = 'x64' if args.target == 'x64-simulator' else 'arm64'
    if arch == 'x64' and platform.machine() != 'x86_64':
        raise RuntimeError('Build the x64 simulator slice on an Intel Mac.')
    simulator = args.target.endswith('-simulator')
    sdk = 'iphonesimulator' if simulator else 'iphoneos'
    sdk_path = subprocess.check_output(['xcrun', '--sdk', sdk, '--show-sdk-path'], text=True).strip()
    cpu = 'x86_64' if arch == 'x64' else 'arm64'
    triple = f'{cpu}-apple-ios14.0' + ('-simulator' if simulator else '')
    env = compiler_environment()
    env['CC'] = env['CC_host']
    env['CXX'] = env['CXX_host']
    env['GYP_DEFINES'] = f'target_arch={arch} host_os=mac target_os=ios'
    set_compiler_commands(env)
    source = prepare(args.source)
    flags = ['--dest-os=ios', f'--dest-cpu={arch}', '--cross-compiling', '--openssl-no-asm',
             '--with-intl=none', '--without-node-code-cache', '--without-node-snapshot',
             '--v8-options=--jitless', '--without-npm', '--without-corepack', '--ninja']
    if simulator:
        flags.append('--ios-simulator')
    run([sys.executable, source / 'configure.py', *flags], cwd=source, env=env)
    git(source, 'diff', '--quiet', '--no-ext-diff', '--no-textconv')
    variables = config(source / 'config.gypi')
    if (variables['OS'], variables['target_arch'], variables['node_shared']) != ('ios', arch, 'false'):
        raise RuntimeError('The iOS configuration does not match the requested target.')
    build_dir = source / 'out' / ('Release-iphonesimulator' if simulator else 'Release-iphoneos')
    dependency_output = source / 'out'
    run([sys.executable, source / 'tools/gyp_node.py', '--no-parallel',
         '-Dconfiguring_node=1', f'-Dpython={sys.executable}',
         '-f', 'dump_dependency_json-ios', f'-Goutput_dir={dependency_output}'], cwd=source, env=env)
    graph = json.loads((dependency_output / 'dump.json').read_text())
    pending = [next(name for name in graph if name.endswith(':libnode#target'))]
    targets = set()
    while pending:
        target = pending.pop()
        if target in targets or not target.endswith('#target'):
            continue
        targets.add(target)
        pending.extend(graph[target])
    run(['ninja', '-C', build_dir, '-j', args.jobs,
         *sorted(target.rsplit(':', 1)[1].removesuffix('#target') for target in targets)], env=env)
    archives = sorted(build_dir.glob('*.a'))
    if not any(path.name == 'libnode.a' for path in archives):
        raise RuntimeError('The iOS build did not produce libnode.a.')
    framework = output / 'NodeMobile.framework'
    (framework / 'Headers').mkdir(parents=True)
    (framework / 'Modules').mkdir()
    run(['xcrun', '--sdk', sdk, 'clang++', '-std=c++20', '-target', triple,
         '-isysroot', sdk_path, '-dynamiclib', '-Wl,-all_load', *archives,
         source / 'tools/ios-framework/NodeMobile.cpp',
         '-I', source / 'src', '-I', source / 'deps/v8/include',
         '-I', source / 'deps/uv/include', '-framework', 'Foundation',
         '-framework', 'CoreFoundation', '-framework', 'Security', '-lz',
         '-install_name', '@rpath/NodeMobile.framework/NodeMobile',
         '-current_version', '1', '-compatibility_version', '1',
         '-o', framework / 'NodeMobile'])
    verify_exports(['xcrun', 'nm', '-gU', framework / 'NodeMobile'], '_')
    exports = subprocess.check_output(['xcrun', 'nm', '-gU', framework / 'NodeMobile'], text=True)
    if '_node_start' not in exports.split():
        raise RuntimeError('The framework does not export node_start.')
    shutil.copyfile(source / 'tools/ios-framework/NodeMobile.h', framework / 'Headers/NodeMobile.h')
    (framework / 'Modules/module.modulemap').write_text(
        'framework module NodeMobile {\n  umbrella header "NodeMobile.h"\n  export *\n}\n')
    with (framework / 'Info.plist').open('wb') as stream:
        plistlib.dump({'CFBundleExecutable': 'NodeMobile', 'CFBundleName': 'NodeMobile',
                       'CFBundleIdentifier': 'com.janeasystems.NodeMobile', 'CFBundlePackageType': 'FMWK',
                       'CFBundleDevelopmentRegion': 'en', 'CFBundleInfoDictionaryVersion': '6.0',
                       'NSHumanReadableCopyright': 'Copyright Node.js contributors.\nModifications copyright (c) Janea Systems, Inc.\nMIT license.',
                       'CFBundleVersion': '1', 'CFBundleShortVersionString': json.loads((ROOT / 'node-source.json').read_text())['version'],
                       'MinimumOSVersion': '14.0',
                       'CFBundleSupportedPlatforms': ['iPhoneSimulator' if simulator else 'iPhoneOS']}, stream)
    copy_headers(source, output)
    record(output, source, args.target)


def combine(args):
    output = output_path(args.output)
    input_paths = [path for path in sorted(args.inputs.resolve().iterdir()) if path.is_dir()]
    inputs = {json.loads((path / 'build-info.json').read_text())['target']: path for path in input_paths}
    if len(inputs) != len(input_paths):
        raise RuntimeError('Duplicate artifact targets.')
    expected = (['armeabi-v7a', 'arm64-v8a', 'x86_64'] if args.platform == 'android'
                else ['arm64', 'arm64-simulator', 'x64-simulator'])
    if sorted(inputs) != sorted(expected):
        raise RuntimeError(f'Expected exactly {expected}; found {sorted(inputs)}')
    lock = json.loads((ROOT / 'node-source.json').read_text())
    records = []
    reference_headers = None
    for name in expected:
        record_data = json.loads((inputs[name] / 'build-info.json').read_text())
        if any(record_data[key] != lock[key] for key in ('version', 'commit', 'tree')):
            raise RuntimeError(f'Stale or mismatched input: {name}')
        header_config = inputs[name] / 'include/node/config.gypi'
        if hashlib.sha256(header_config.read_bytes()).hexdigest() != record_data['config_sha256']:
            raise RuntimeError(f'Modified configuration: {name}')
        binary_name = (f'bin/{name}/libnode.so' if args.platform == 'android'
                       else 'NodeMobile.framework/NodeMobile')
        if set(record_data['binary_sha256']) != {binary_name}:
            raise RuntimeError(f'Missing or unexpected binary manifest: {name}')
        for relative, expected_hash in record_data['binary_sha256'].items():
            if hashlib.sha256((inputs[name] / relative).read_bytes()).hexdigest() != expected_hash:
                raise RuntimeError(f'Modified binary: {name}/{relative}')
        symbols = {path.relative_to(inputs[name]).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in (inputs[name] / 'symbols').rglob('*') if path.is_file()}
        if symbols != record_data.get('symbols_sha256', {}):
            raise RuntimeError(f'Missing or modified debugging symbols: {name}')
        headers = {path.relative_to(inputs[name] / 'include').as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in (inputs[name] / 'include').rglob('*')
                   if path.is_file() and path.name != 'config.gypi'}
        if reference_headers is not None and headers != reference_headers:
            raise RuntimeError(f'Public headers differ between targets: {name}')
        reference_headers = headers
        records.append(record_data)
    output.mkdir(parents=True)
    if args.platform == 'android':
        for arch, (abi, _) in ANDROID.items():
            library = inputs[abi] / 'bin' / abi / 'libnode.so'
            verify_elf(library, arch)
            variables = config(inputs[abi] / 'include/node/config.gypi')
            if (variables['OS'], variables['target_arch'], variables['node_shared']) != ('android', arch, 'true'):
                raise RuntimeError(f'Wrong build configuration: {abi}')
            (output / 'bin' / abi).mkdir(parents=True)
            shutil.copyfile(library, output / 'bin' / abi / 'libnode.so')
        header_source = inputs['x86_64']
    else:
        for name, path in inputs.items():
            variables = config(path / 'include/node/config.gypi')
            arch = 'x64' if name == 'x64-simulator' else 'arm64'
            if (variables['OS'], variables['target_arch'], variables['node_shared']) != ('ios', arch, 'false'):
                raise RuntimeError(f'Wrong iOS build configuration: {name}')
        simulator = output / 'simulator/NodeMobile.framework'
        shutil.copytree(inputs['arm64-simulator'] / 'NodeMobile.framework', simulator)
        run(['xcrun', 'lipo', '-create',
             inputs['arm64-simulator'] / 'NodeMobile.framework/NodeMobile',
             inputs['x64-simulator'] / 'NodeMobile.framework/NodeMobile',
             '-output', simulator / 'NodeMobile'])
        run(['xcodebuild', '-create-xcframework', '-framework',
             inputs['arm64'] / 'NodeMobile.framework', '-framework', simulator,
             '-output', output / 'NodeMobile.xcframework'])
        shutil.rmtree(output / 'simulator')
        header_source = inputs['arm64']
    for path in inputs.values():
        if (path / 'symbols').is_dir():
            shutil.copytree(path / 'symbols', output / 'symbols', dirs_exist_ok=True)
    shutil.copytree(header_source / 'include', output / 'include')
    shutil.copyfile(header_source / 'LICENSE', output / 'LICENSE')
    shutil.copyfile(header_source / 'LICENSE-nodejs-mobile', output / 'LICENSE-nodejs-mobile')
    if [path.relative_to(output).as_posix() for path in output.rglob('config.gypi')] != ['include/node/config.gypi']:
        raise RuntimeError('Only include/node/config.gypi may be distributed.')
    (output / 'build-info.json').write_text(json.dumps({'source': lock, 'slices': records}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='platform', required=True)
    for name in ('android', 'ios'):
        command = commands.add_parser(name)
        command.add_argument('--source', type=Path, default=ROOT / '.build/node')
        command.add_argument('--output', type=Path, required=True)
        command.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
        if name == 'android':
            command.add_argument('--ndk', type=Path, required=True)
            command.add_argument('--api', type=int, default=24)
            command.add_argument('--arch', choices=ANDROID, required=True)
        else:
            command.add_argument('--target', choices=('arm64', 'arm64-simulator', 'x64-simulator'), required=True)
    for name in ('combine-android', 'combine-ios'):
        command = commands.add_parser(name)
        command.add_argument('--inputs', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.platform == 'android':
            build_android(args)
        elif args.platform == 'ios':
            build_ios(args)
        else:
            args.platform = args.platform.removeprefix('combine-')
            combine(args)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
