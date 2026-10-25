# Contributing to Node.js for Mobile Apps

This guide covers contributions. See [BUILDING.md](BUILDING.md) for setup and platform requirements, and [TESTING.md](TESTING.md) for verification and runtime testing.

## Code Contributions

Keep changes within the [project goals](README.md#project-goals), with as few differences from upstream Node.js as practical.

For a major feature or behavior change, [open an issue](https://github.com/RockinChaos/nodejs-mobile/issues/new/choose) for discussion first. For minor fixes, open a pull request directly.

### Commit guidelines

Use `type(scope): description`, with a lowercase, imperative description and a title of about 72 characters or fewer. For example: `fix(android): restrict addon flags to target builds`.

Keep independent Android and iOS fixes in separate commits and identify the platform in the scope.

## Source layout

* `node/` is the pristine upstream Node.js submodule. Its commit must match `node-source.json` and the parent repository's gitlink.
* `patches/` contains changes to upstream files. `patches/series` controls their application order.
* `src/` and `tools/` contain mobile-owned files copied into the generated source tree at the same paths. An overlay cannot replace an upstream file; use a patch for that.
* `scripts/` and `.github/workflows/` contain this project's source preparation, build, verification and CI tooling.
* `.build/` contains generated source trees and build outputs. These are local working files.

## Editing mobile source

Run commands from the repository root. Initialize the pinned submodule and prepare a separate source tree:

```sh
git submodule update --init --depth 1
python3 scripts/prepare.py --output .build/contribute
```

Use a fresh output path for each reconstruction. Preparation refuses existing directories and leaves failed attempts available for inspection.

Edit upstream files and existing mobile overlays inside `.build/contribute`, leaving `node/` clean. Export the edits back to the repository:

```sh
python3 scripts/regenerate.py --source .build/contribute
```

Regeneration updates the existing patches, mobile overlays and the expected source tree hash in `node-source.json`. Review that diff, then reconstruct without `--update-lock` to confirm the patched source can be reproduced:

```sh
python3 scripts/prepare.py --output .build/contribute-check
python3 scripts/verify.py --source .build/contribute-check --unit-tests
```

Edit project tooling directly in `scripts/` or `.github/`; those files are outside the reconstructed Node.js tree.

### Patch ownership and new files

Each modified upstream file must belong to exactly one patch. Regeneration exports the complete diff for the files already assigned to each patch; it does not create patches or split a file's changes between patches.

For an upstream file not yet covered, add its diff to an appropriate patch or create a patch and list it in `patches/series`. Follow the existing patch format, using Git diffs against the pinned upstream commit with full object IDs and binary support (`--full-index --binary`). Preserve existing source attribution and license notices when porting inherited fixes.

Put new mobile-owned files in the root `src/` or `tools/` directories. After adding an overlay or editing patches directly, review the source changes and explicitly record the new tree:

```sh
python3 scripts/prepare.py --output .build/source-review --update-lock
python3 scripts/verify.py --source .build/source-review --unit-tests
python3 scripts/prepare.py --output .build/source-check
python3 scripts/verify.py --source .build/source-check
```

Use `--update-lock` only for an intentional source change. A normal reconstruction must match the recorded tree. If a patch becomes empty or unnecessary, remove it and its entry in `patches/series` explicitly.

## Updating upstream Node.js

1. Select an official release for this branch's Node.js major version. Fetch and check out that exact release commit in `node/`, keeping the submodule free of local changes.
2. Update `version`, `tag` and `commit` in `node-source.json` to match the release. Keep `repository` pointed at the official Node.js repository.
3. Stage the submodule pointer with `git add -- node`. Preparation checks the parent index, so checking out the release in the submodule alone is insufficient.
4. Review every patch against the new upstream source. Port conflicts, remove fixes already supplied upstream, and check that the root overlays still apply. Preparation stops on patch failures; it does not resolve conflicts automatically.
5. Reconstruct with `--update-lock` to record the reviewed tree, then verify and reconstruct again without that flag, as shown above. Use a fresh output path for each attempt.
6. Build and test Android and iOS using [BUILDING.md](BUILDING.md) and [TESTING.md](TESTING.md). Review the submodule pointer, manifest, patches, mobile version information and affected documentation together.

The submodule branch configured in `.gitmodules` is an update convenience. Builds always use the exact recorded commit. Upstream updates are explicit source changes; the build workflow does not advance the pin.

## Pull requests and verification

Explain the problem, the resulting behavior and the platforms affected. Include the checks run and their results, and identify any platform or runtime testing still outstanding.

A source change should reproduce from a fresh tree and pass `scripts/verify.py`. The optional `--unit-tests` flag runs upstream GYP tooling tests. Native builds and device or simulator tests provide separate coverage; follow [TESTING.md](TESTING.md) for the checks relevant to the change.

By contributing, you certify the terms below. Preserve attribution for inherited code.

<a id="developers-certificate-of-origin"></a>

## Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

* (a) The contribution was created in whole or in part by me and I
  have the right to submit it under the open source license
  indicated in the file; or

* (b) The contribution is based upon previous work that, to the best
  of my knowledge, is covered under an appropriate open source
  license and I have the right under that license to submit that
  work with modifications, whether created in whole or in part
  by me, under the same open source license (unless I am
  permitted to submit under a different license), as indicated
  in the file; or

* (c) The contribution was provided directly to me by some other
  person who certified (a), (b) or (c) and I have not modified
  it.

* (d) I understand and agree that this project and the contribution
  are public and that a record of the contribution (including all
  personal information I submit with it, including my sign-off) is
  maintained indefinitely and may be redistributed consistent with
  this project or the open source license(s) involved.
