# Node.js for Mobile Apps

This is a *fork* of the [main repository](https://github.com/RockinChaos/nodejs-mobile) for *Node.js for Mobile Apps*, a toolkit for integrating Node.js into mobile applications.

## Resources for Newcomers

* [Frequently Asked Questions](./FAQ.md)
* [Issues and questions](https://github.com/RockinChaos/nodejs-mobile/issues/new/choose)
* [(Old) Website](https://code.janeasystems.com/nodejs-mobile)

The core library is built from the official Node.js source pinned in `node/`, with the ordered mobile patches in `patches/series`. Mobile-owned source lives in `src/` and `tools/`. If you are looking for the *source code* for the plugins, you can find it at:

* [React Native plugin source repo](https://github.com/nodejs-mobile/nodejs-mobile-react-native)
* [Cordova plugin source repo](https://github.com/nodejs-mobile/nodejs-mobile-cordova)


## Project Goals

1. To provide the fixes necessary to run Node.js on mobile operating systems.
1. To investigate which features need to be added to Node.js in order to make it a useful tool for mobile app development.
1. To diverge as little as possible from nodejs/node, while fulfilling goals (1) and (2).

## Download

See this fork's [releases page](https://github.com/RockinChaos/nodejs-mobile/releases) for published releases. For CI builds, download the `nodejs-mobile-android` or `nodejs-mobile-ios` artifact from a successful [Build workflow run](https://github.com/RockinChaos/nodejs-mobile/actions/workflows/build-mobile.yml). For historical binaries, see the [original project's releases](https://github.com/nodejs-mobile/nodejs-mobile/releases).

The combined Android package contains `bin/<ABI>/libnode.so`; the iOS package contains `NodeMobile.xcframework`. Both include public headers under `include/node`, upstream notices in `LICENSE`, the [project license](LICENSE) in `LICENSE-nodejs-mobile`, and source metadata in `build-info.json`.

## Documentation

The [build](BUILDING.md), [testing](TESTING.md) and [contribution](CONTRIBUTING.md) guides cover this fork's current workflows. The [release](RELEASING.md) guide describes the earlier source layout.

Original project documentation and sample code are available on the [old project website](https://code.janeasystems.com/nodejs-mobile) and in the [samples repository](https://github.com/janeasystems/nodejs-mobile-samples/).

## Versioning

The mobile version follows the upstream Node.js release with an additional mobile revision.

The upstream version, release tag, commit and reconstructed source tree are recorded in [node-source.json](node-source.json). `process.version` reports the upstream version, and `process.versions.mobile` reports `<upstream-version>-<mobile-revision>`. The mobile revision is defined in [src/node_mobile_version.h](src/node_mobile_version.h).

## Build Instructions

Android builds run on x86_64 Linux; iOS builds run on macOS. Install the toolchains listed in [BUILDING.md](BUILDING.md#prerequisites) before building.

Clone the repository and initialize its upstream submodule, then run build commands from the repository root:

```sh
git clone https://github.com/RockinChaos/nodejs-mobile.git
cd nodejs-mobile
git submodule update --init --depth 1
```

Build an ARM64 Android library on Linux:

```sh
python3 scripts/build.py android \
  --ndk /path/to/android-ndk \
  --arch arm64 \
  --source .build/sources/android-arm64 \
  --output .build/android-arm64
```

Build an ARM64 iOS device framework on macOS:

```sh
python3 scripts/build.py ios \
  --target arm64 \
  --source .build/sources/ios-arm64 \
  --output .build/ios-arm64
```

Android architectures are `arm`, `arm64` and `x64`. iOS targets are `arm64`, `arm64-simulator` and `x64-simulator`; the x64 simulator slice requires an Intel Mac. Each invocation needs fresh `--source` and `--output` directories. The build reconstructs and verifies a separate source tree, leaving the submodule pristine.

See [Build Android](BUILDING.md#build-android) and [Build iOS](BUILDING.md#build-ios) for all targets and package assembly. The [Build workflow](https://github.com/RockinChaos/nodejs-mobile/actions/workflows/build-mobile.yml) verifies source reconstruction, builds the platform matrix, and uploads the combined packages named above. It does not publish releases.

## Running tests

With the submodule initialized, prepare a fresh source directory and run the checks:

```sh
python3 scripts/prepare.py --output .build/check
python3 scripts/verify.py --source .build/check --unit-tests
```

These checks validate source reconstruction and run upstream GYP unit tests. Native builds additionally check addon exports and Android ELF architecture/page alignment. Automated mobile runtime tests are not yet configured; see [TESTING.md](TESTING.md) for coverage and manual validation. iOS runs V8 without JIT and retains the WebAssembly-dependent `fetch` limitation.

## Reporting issues

Use this fork's [issue templates](https://github.com/RockinChaos/nodejs-mobile/issues/new/choose) for runtime bugs, build failures, feature requests and questions. Include the release or commit, target platform and steps needed to reproduce the problem. If a plugin is involved, include its name and version.

## Contributing

Keep `node/` pristine. Edit upstream files in a generated source tree, export the changes with `python3 scripts/regenerate.py --source .build/<target>`, and verify a fresh reconstruction before review. Changes to upstream files belong in `patches/`; mobile-owned files belong in `src/` or `tools/`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for patch ownership, new files, upstream updates and pull request requirements.
