# Testing nodejs-mobile

This guide describes the checks that cover source reconstruction, build tooling, native binaries and packaging. Automated Android/iOS runtime testing on devices, emulators or simulators is not yet implemented in this repository.

## Prerequisites

Use Git and Python 3.13, initialize the `node` submodule, and run commands from the repository root. See [Get the source](BUILDING.md#get-the-source) for checkout instructions and [Prerequisites](BUILDING.md#prerequisites) for native build requirements.

## Source reconstruction and verification

Prepare a fresh source tree and verify it:

```sh
python3 scripts/prepare.py --output .build/testing-source
python3 scripts/verify.py --source .build/testing-source
```

Preparation checks that the submodule and gitlink match `node-source.json`, requires a clean upstream checkout, applies the ordered patch series, copies mobile-owned files and compares the resulting tree with the expected hash.

Verification checks:

- The generated source index matches the expected tree and has no unstaged tracked-file changes.
- Node's version matches `node-source.json`.
- Changed GYP/Python files and this project's Python scripts have valid syntax.
- Changes relative to upstream pass Git's whitespace checks.

The preparation output directory must not already exist. Verification can be repeated against the same generated tree.

## GYP unit tests

Run the upstream GYP unit tests alongside source verification:

```sh
python3 scripts/verify.py --source .build/testing-source --unit-tests
```

The Build workflow runs this check on Ubuntu 24.04 with Python 3.13. These Python tests exercise GYP build tooling. They do not compile or execute Node's JavaScript runtime tests or C++ tests.

## Checking source changes

After intentionally editing a generated source tree, export those changes before checking a fresh reconstruction:

```sh
python3 scripts/regenerate.py --source .build/testing-source
python3 scripts/prepare.py --output .build/testing-reconstructed
python3 scripts/verify.py --source .build/testing-reconstructed
```

`regenerate.py` writes the patch files, mobile-owned source files and expected tree hash in `node-source.json`. Review the exported changes. New upstream files must be assigned to a patch; see the [contribution workflow](README.md#contributing).

## Native build and package checks

The [Android](BUILDING.md#build-android) and [iOS](BUILDING.md#build-ios) build commands perform these checks automatically:

| Area | Checks |
| --- | --- |
| Android | Target OS/architecture/shared-library configuration, ELF architecture, LOAD segment alignment of at least 16 KB, and required native-addon API exports. |
| iOS | Target OS/architecture/static-library configuration, required native-addon API exports, and the framework's `node_start` export. |
| Public headers | Required public header and GYP files are present in the packaged headers. |
| Combined packages | Exactly the required targets, matching source version/commit/tree, consistent public headers, intact configuration/binary hashes and expected platform configuration. |

Android package assembly also verifies that only one `config.gypi` is distributed, taken from the actual x64 build. Symbol checks inspect binary exports; loading an addon still requires runtime testing in an application.

## CI coverage

The [Build workflow](https://github.com/RockinChaos/nodejs-mobile/actions/workflows/build-mobile.yml) is configured to:

1. Reconstruct the source and run verification plus GYP unit tests.
2. Build Android `arm`, `arm64` and `x64` on Linux.
3. Build iOS ARM64 device, ARM64 simulator and Intel x64 simulator slices on macOS.
4. Validate and combine platform outputs, then upload the artifacts.

The upstream runtime test sources remain in the generated Node tree, but this workflow does not build or run the JavaScript test suite, C++ runtime tests or mobile integration tests.

## Manual runtime validation

Use a consuming application to exercise the built library on the device and emulator/simulator targets you intend to support. This repository currently provides no test application or automated mobile test runner.

Suggested smoke tests include:

- Load the library, start Node and execute JavaScript. Check `process.version` and `process.versions.mobile` against the build being tested.
- Read and write files in the application's writable sandbox, and exercise timers and worker threads used by the application.
- Test the networking and TLS APIs the application uses.
- Cross-compile and load a representative native addon for each shipped architecture.
- Exercise Android on a device or emulator with 16 KB pages when validating that compatibility, and exercise both device and simulator frameworks on iOS.

iOS runs V8 without JIT. The existing WebAssembly-dependent `fetch` limitation is described in the [runtime notes](README.md#running-tests).

When [reporting a failure](https://github.com/RockinChaos/nodejs-mobile/issues/new/choose), include the release or commit, mobile version, OS/device and architecture, integration plugin version if relevant, reproduction steps and logs.
