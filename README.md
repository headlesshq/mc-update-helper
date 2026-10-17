# mc-update-helper

Checks every day for a new Minecraft release and opens a pull request in each repository
listed in [`repositories.json`](repositories.json) that does not support it yet.

Currently, we are updating 
- [mc-runtime-test-mod](https://github.com/headlesshq/mc-runtime-test-mod)
- [hmc-specifics](https://github.com/headlesshq/hmc-specifics)
- [hmc-optimizations](https://github.com/headlesshq/hmc-optimizations)

Each repository has a `ci-data.json` in its root and one Gradle project per Minecraft version in `versions`,
e.g. `versions/26_3`. For a new minor version the project of the previous version is copied, e.g. to `versions/26_4`.

Example Pull-Request: https://github.com/headlesshq/hmc-specifics/pull/65
