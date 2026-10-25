# Release Instructions

The [Build workflow](https://github.com/RockinChaos/nodejs-mobile/actions/workflows/build-mobile.yml) prepares draft releases after successful push or manual builds. Pull requests build and validate packages without creating releases. Publishing is manual.

## Version and tag

The upstream version comes from `node-source.json`. The mobile revision is `NODE_MOBILE_REVISION` in `src/node_mobile_version.h`.

- Revision zero uses release version `<node-version>` and tag `v<node-version>`.
- A later revision uses `<node-version>-<revision>` and tag `v<node-version>-<revision>`.
- The release title is the release version without the leading `v`.

Increment the mobile revision when rebuilding the same Node release with mobile changes. Reset it to zero when updating to a different upstream release. Source changes must pass the preparation and tree-hash checks described in [Contributing](CONTRIBUTING.md).

`process.versions.mobile` includes the mobile revision, including `-0`. The first release tag and title omit that zero suffix.

## Draft creation

1. Push the intended source changes, or run the Build workflow manually on that commit's branch.
2. An existing published release or published prerelease skips the build. A missing release or an existing draft allows it to proceed.
3. After each combined package uploads successfully, its three intermediate artifacts are removed from that workflow run. Fork pull requests retain intermediates because their tokens cannot delete artifacts. Cleanup failures leave the intermediates available and do not prevent drafting.
4. After both platforms and `versions.txt` are ready, CI generates release notes and creates or updates the draft. It rechecks publication status before updating it.

Each draft receives:

- `nodejs-mobile-v<release-version>-android.zip`
- `nodejs-mobile-v<release-version>-ios.zip`
- `versions.txt`

The release ZIPs are the combined workflow archives, renamed without unpacking or repackaging. This preserves their contents and file permissions. Existing draft notes and matching assets are replaced by the next successful build.

The notes list the supported platforms, project commits since the closest previous version tag on the branch, and the single dependency-version map. The current release tag is excluded from the comparison base when refreshing a draft. Formatting is configured in `.github/cliff.toml`; no changelog file is maintained in the repository.

## Review and publish

Open the draft on this fork's [releases page](https://github.com/RockinChaos/nodejs-mobile/releases). Review the generated notes and download the assets. Test them in consuming apps on the supported devices and simulators, including Android with 16 KB pages, before publishing.

Publish the draft in GitHub when it is ready. Later builds of the same release version will skip; increment the mobile revision or update the upstream version for another release.
