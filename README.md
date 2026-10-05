# mc-update-helper

Checks every day for a new Minecraft release and opens a pull request in each repository
listed in [`repositories.json`](repositories.json) that does not support it yet.

Currently, we are updating 
- [mc-runtime-test](https://github.com/headlesshq/mc-runtime-test)
- [hmc-specifics](https://github.com/headlesshq/hmc-specifics)
- [hmc-optimizations](https://github.com/headlesshq/hmc-optimizations)

Example Pull-Request: https://github.com/headlesshq/hmc-specifics/pull/64
