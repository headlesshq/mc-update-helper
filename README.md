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

## Development container

The repository contains a [development container](https://containers.dev) in
[`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json). It uses Python 3.11, like the CI,
includes the GitHub CLI and installs `requirements.txt` and `requirements-dev.txt` when the container is created.
The pip cache is kept in a Docker volume, so rebuilding the container does not download every package again.

Open the repository in GitHub Codespaces or with "Dev Containers: Reopen in Container" in VS Code,
or use the [devcontainer CLI](https://github.com/devcontainers/cli):

```shell
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . python -m pytest
```

The container does not contain any credentials. To push branches and open pull requests,
provide a `GITHUB_TOKEN` (or `GH_TOKEN`) yourself, for example as a
[Codespaces secret](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces)
or by running `gh auth login` and then `export GITHUB_TOKEN=$(gh auth token)`.
Use `--dry-run` to only show the changes.
