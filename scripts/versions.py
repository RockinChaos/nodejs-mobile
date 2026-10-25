#!/usr/bin/env python3
"""Read build-time dependency versions from a configured mobile source tree."""

import ast
import re


def dependency_versions(source, variables):
    def enabled(name):
        return variables.get(name) in (True, 1, '1', 'true')

    def macro(path, name):
        text = (source / path).read_text(encoding='utf-8')
        match = re.search(r'^\s*#\s*define\s+' + re.escape(name) + r'\s+([^\n]+)', text, re.M)
        if not match:
            raise RuntimeError(f'Missing version macro {name} in {path}')
        value = re.split(r'\s*(?://|/\*)', match[1], maxsplit=1)[0].strip()
        try:
            result = ast.literal_eval(value)
        except (ValueError, SyntaxError) as error:
            raise RuntimeError(f'Unsupported version macro {name} in {path}: {value}') from error
        if type(result) not in (str, int):
            raise RuntimeError(f'Invalid version macro {name} in {path}')
        return result

    def triplet(path, prefix, parts=('MAJOR', 'MINOR', 'PATCH')):
        return '.'.join(str(macro(path, f'{prefix}_{part}')) for part in parts)

    if enabled('v8_enable_i18n_support'):
        raise RuntimeError('Build-time version reporting requires --with-intl=none.')
    shared = [name for name in ('ada', 'brotli', 'cares', 'libuv', 'merve', 'nghttp2',
                               'nghttp3', 'ngtcp2', 'openssl', 'simdjson',
                               'simdutf', 'sqlite', 'uvwasi', 'zlib', 'zstd')
              if enabled(f'node_shared_{name}')]
    if shared:
        raise RuntimeError(f'Cannot report runtime versions of shared dependencies: {shared}')

    node = triplet('src/node_version.h', 'NODE', ('MAJOR_VERSION', 'MINOR_VERSION', 'PATCH_VERSION'))
    if not macro('src/node_version.h', 'NODE_VERSION_IS_RELEASE'):
        node += '-pre'
    versions = {
        'node': node,
        'mobile': f'{node}-{macro("src/node_mobile_version.h", "NODE_MOBILE_REVISION")}',
        'modules': str(variables['node_module_version']),
        'napi': str(macro('src/node_version.h', 'NODE_API_SUPPORTED_VERSION_MAX')),
        'uv': triplet('deps/uv/include/uv/version.h', 'UV_VERSION'),
        'brotli': triplet('deps/brotli/c/common/version.h', 'BROTLI_VERSION'),
        'llhttp': triplet('deps/llhttp/include/llhttp.h', 'LLHTTP_VERSION'),
        'uvwasi': triplet('deps/uvwasi/include/uvwasi.h', 'UVWASI_VERSION'),
        'zstd': triplet('deps/zstd/lib/zstd.h', 'ZSTD_VERSION', ('MAJOR', 'MINOR', 'RELEASE')),
    }
    if not macro('deps/uv/include/uv/version.h', 'UV_VERSION_IS_RELEASE'):
        versions['uv'] += '-' + macro('deps/uv/include/uv/version.h', 'UV_VERSION_SUFFIX')
    v8_header = 'deps/v8/include/v8-version.h'
    versions['v8'] = triplet(v8_header, 'V8', ('MAJOR_VERSION', 'MINOR_VERSION', 'BUILD_NUMBER'))
    patch = macro(v8_header, 'V8_PATCH_LEVEL')
    if patch:
        versions['v8'] += f'.{patch}'
    common = ast.literal_eval((source / 'common.gypi').read_text(encoding='utf-8'))['variables']
    versions['v8'] += variables.get('v8_embedder_string', common['v8_embedder_string'])
    if macro(v8_header, 'V8_IS_CANDIDATE_VERSION'):
        versions['v8'] += ' (candidate)'

    headers = {
        'acorn': ('src/acorn_version.h', 'ACORN_VERSION'),
        'ada': ('deps/ada/ada.h', 'ADA_VERSION'),
        'ares': ('deps/cares/include/ares_version.h', 'ARES_VERSION_STR'),
        'nbytes': ('deps/nbytes/include/nbytes.h', 'NBYTES_VERSION'),
        'nghttp2': ('deps/nghttp2/lib/includes/nghttp2/nghttp2ver.h', 'NGHTTP2_VERSION'),
        'simdjson': ('deps/simdjson/simdjson.h', 'SIMDJSON_VERSION'),
        'simdutf': ('deps/simdutf/simdutf.h' if (source / 'deps/simdutf').is_dir()
                    else 'deps/v8/third_party/simdutf/simdutf.h', 'SIMDUTF_VERSION'),
        'zlib': ('src/zlib_version.h', 'ZLIB_VERSION'),
    }
    if 'node_shared_merve' in variables:
        headers['merve'] = ('deps/merve/merve.h', 'MERVE_VERSION')
    else:
        headers['cjs_module_lexer'] = ('src/cjs_module_lexer_version.h', 'CJS_MODULE_LEXER_VERSION')
    if 'node_use_quic' in variables:
        versions.update(ngtcp2='', nghttp3='')
    if not variables.get('node_shared_builtin_undici_undici_path'):
        headers['undici'] = ('src/undici_version.h', 'UNDICI_VERSION')
    if enabled('node_use_amaro') and not variables.get('node_shared_builtin_amaro_dist_index_path'):
        headers['amaro'] = ('src/amaro_version.h', 'AMARO_VERSION')
    if enabled('node_use_sqlite'):
        headers['sqlite'] = ('deps/sqlite/sqlite3.h', 'SQLITE_VERSION')
    if enabled('node_use_openssl'):
        arch = {
            'android': {'arm': 'linux-armv4', 'arm64': 'linux-aarch64', 'x64': 'linux-x86_64'},
            'ios': {'arm64': 'darwin64-arm64-cc', 'x64': 'darwin64-x86_64-cc'},
        }[variables['OS']][variables['target_arch']]
        mode = 'no-asm' if enabled('openssl_no_asm') else 'asm'
        headers['openssl'] = (f'deps/openssl/config/archs/{arch}/{mode}/include/openssl/opensslv.h',
                              'OPENSSL_FULL_VERSION_STR')
        headers['ncrypto'] = ('deps/ncrypto/ncrypto.h', 'NCRYPTO_VERSION')
        if enabled('openssl_quic') or enabled('node_use_quic'):
            headers['ngtcp2'] = ('deps/ngtcp2/ngtcp2/lib/includes/ngtcp2/version.h', 'NGTCP2_VERSION')
            headers['nghttp3'] = ('deps/ngtcp2/nghttp3/lib/includes/nghttp3/version.h', 'NGHTTP3_VERSION')
    for name, (path, define) in headers.items():
        versions[name] = str(macro(path, define))
    return dict(sorted(versions.items()))
