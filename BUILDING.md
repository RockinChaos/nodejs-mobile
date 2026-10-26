# Building nodejs-mobile

This guide builds the Android and iOS libraries. Run the commands from the repository root.

## Prerequisites

Install Git, Python 3.13, Clang, Clang++, Ninja, and Rust 1.86 or newer with Cargo, and make them available on `PATH`. The commands below use `python3`; it must resolve to the intended Python installation.

### Android prerequisites

Use an x86_64 Linux host with Android NDK r29. Android builds target API 24 by default; `--api` can select a newer API, with 24 as the minimum.

Use Clang 19.1 or newer for the host tools. The `arm` build also requires 32-bit host C/C++ support. On Ubuntu or Debian, install it with:

```sh
sudo apt-get install -y clang-19 gcc-multilib g++-multilib
export CC_host=clang-19
export CXX_host=clang++-19
```

Install the Rust targets used by the Android builds:

```sh
rustup target add armv7-linux-androideabi aarch64-linux-android x86_64-linux-android i686-unknown-linux-gnu
```

Set `ANDROID_NDK_HOME` to the extracted NDK directory before building:

```sh
export ANDROID_NDK_HOME=/path/to/android-ndk-r29
```

### iOS prerequisites

Use macOS with Xcode 26.3 and its iOS SDKs. Builds target iOS 14 or newer. The `x64-simulator` target requires an Intel Mac; CI builds the ARM64 device and simulator targets on Apple Silicon.

If multiple Xcode versions are installed, select Xcode 26.3 for the build:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.3.app/Contents/Developer
xcrun --sdk iphoneos --show-sdk-path
xcrun --sdk iphonesimulator --show-sdk-path
```

Install the Rust targets for the iOS slices you will build on this Mac:

```sh
rustup target add aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios
```

Adjust `DEVELOPER_DIR` if Xcode is installed at a different path. Use the same Xcode version when building and combining framework slices.

## Get the source

```sh
git clone https://github.com/RockinChaos/nodejs-mobile.git
cd nodejs-mobile
git submodule update --init --depth 1
```

The `node` submodule and `node-source.json` select the exact upstream Node release. Build commands reconstruct a separate source tree, apply `patches/series`, copy this project's `src` and `tools` files, and verify the resulting tree hash. Keep the submodule clean; make upstream source edits in a generated tree as described in [Contributing](README.md#contributing).

Each build requires a new `--source` directory and a new `--output` directory inside this repository. The scripts refuse existing directories and never clean previous builds automatically. Choose new paths when repeating these examples.

## Build Android

The supported architectures are:

| `--arch` | Android ABI |
| --- | --- |
| `arm` | `armeabi-v7a` |
| `arm64` | `arm64-v8a` |
| `x64` | `x86_64` |

Build all three architectures and combine them into one package:

```sh
for arch in arm arm64 x64; do
  python3 scripts/build.py android \
    --ndk "$ANDROID_NDK_HOME" \
    --arch "$arch" \
    --source ".build/sources/android-$arch" \
    --output ".build/artifacts/android/$arch"
done

python3 scripts/build.py combine-android \
  --inputs .build/artifacts/android \
  --output .build/packages/nodejs-mobile-android
```

For a single architecture, replace `arm arm64 x64` in the loop with the desired value and skip the combine command. Combining requires all three architectures.

The combined package contains `bin/<ABI>/libnode.so`, public headers under `include/node`, upstream notices in `LICENSE`, the project license in `LICENSE-nodejs-mobile`, and `build-info.json`. Its single `include/node/config.gypi` comes from the actual x64 build.

Android builds check the ELF architecture, 16 KB segment alignment and required native-addon exports before packaging.

## Build iOS

Build the device and ARM64 simulator slices on a Mac configured with the prerequisites above:

```sh
python3 scripts/build.py ios \
  --target arm64 \
  --source .build/sources/ios-arm64 \
  --output .build/artifacts/ios/arm64

python3 scripts/build.py ios \
  --target arm64-simulator \
  --source .build/sources/ios-arm64-simulator \
  --output .build/artifacts/ios/arm64-simulator
```

On an Intel Mac, check out the same project revision and build the Intel simulator slice:

```sh
python3 scripts/build.py ios \
  --target x64-simulator \
  --source .build/sources/ios-x64-simulator \
  --output .build/artifacts/ios/x64-simulator
```

Copy the complete `x64-simulator` output directory into `.build/artifacts/ios` on the Mac assembling the package. Preserve its headers, framework, license files and `build-info.json` alongside those of the other slices.

Combine all three slices:

```sh
python3 scripts/build.py combine-ios \
  --inputs .build/artifacts/ios \
  --output .build/packages/nodejs-mobile-ios
```

The combined package contains `NodeMobile.xcframework` with an ARM64 device framework and an ARM64/x86_64 simulator framework, plus public headers, upstream notices in `LICENSE`, the project license in `LICENSE-nodejs-mobile`, and `build-info.json`. V8 runs without JIT on iOS.

## Verify the source

Source reconstruction and verification can be run separately from compilation:

```sh
python3 scripts/prepare.py --output .build/verify-source
python3 scripts/verify.py --source .build/verify-source
```

Add `--unit-tests` to the verification command to run the upstream GYP unit tests, as CI does. Build commands also validate target configuration and exported symbols. Combining checks that all required architectures are present, source pins and public headers match between slices, and configuration and binary hashes are intact. These checks are separate from device runtime tests.

## Build options

Add `--jobs N` to an Android or iOS build command to limit parallel compilation. The default is the host CPU count.

## GitHub Actions artifacts

The [Build workflow](https://github.com/RockinChaos/nodejs-mobile/actions/workflows/build-mobile.yml) reconstructs and verifies the source, builds the platform matrix, then combines and uploads `nodejs-mobile-android` and `nodejs-mobile-ios` artifacts. Each package includes source metadata and the upstream license.
