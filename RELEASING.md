# Release Instructions

These instructions describe historical releases. This branch currently provides [workflow artifacts](README.md#download).

1. Start a new Git branch for this release
2. In `src/node_version.h`, flag `NODE_VERSION_IS_RELEASE` to 1
3. In `src/node_mobile_version.h`, set the MAJOR/MINOR/PATCH version numbers
4. git commit as `release: nodejs-mobile $X.$Y.$Z`, replacing `$X`, `$Y`, `$Z`
5. Push this branch to GitHub and create a PR for it
6. Allow CI some time to compile all binaries successfully
7. Download binaries, and smoke test a sample project on devices and simulators/emulators
8. Merge the PR as a single commit (squash)
9. git tag as `v$X.$Y.$Z`, replacing `$X`, `$Y`, `$Z`
10. `git push origin --tags`
11. Rename downloaded zip file `nodejs-mobile-v$X.$Y.$Z-ios.zip` containing:
    - include
      - node
        - (each header file)
    - NodeMobile.xcframework
      - ios-arm64
        - NodeMobile.framework
      - ios-arm64_x86_64-simulator
        - NodeMobile.framework
12. Rename downloaded zip file `nodejs-mobile-v$X.$Y.$Z-android.zip` containing:
    - bin
      - (each architecture)
        - libnode.so
    - include
      - node
        - (each header file)
13. Create a GitHub release based on the git tag, upload zips and write release notes
14. Opposite of first step: unflag `NODE_VERSION_IS_RELEASE`
15. git commit as `src: unflag NODE_VERSION_IS_RELEASE`
