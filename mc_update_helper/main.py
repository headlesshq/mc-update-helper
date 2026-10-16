"""Checks for a new Minecraft release and opens a pull request in every configured repository that lacks it."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional

from .github import GitHub
from .updater import RepoOptions, update_repository
from .versions import McVersion, fetch_latest_release, fetch_lexforge_version

DEFAULT_CONFIG = Path(__file__).parent.parent / 'repositories.json'
BOT_NAME = 'github-actions[bot]'
BOT_EMAIL = '41898282+github-actions[bot]@users.noreply.github.com'


def log(message: str):
    print(message, flush=True)


def summary(message: str):
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')


def git(*args: str, cwd: Optional[Path] = None) -> str:
    result = subprocess.run(['git', *args], cwd=cwd, text=True, stdout=subprocess.PIPE)
    if result.returncode != 0:
        # do not include the arguments, the clone url contains the token
        raise RuntimeError(f'git {args[0]} failed with exit code {result.returncode}')
    return result.stdout


def process_repository(github: GitHub, config: dict, defaults: dict, latest: str, lex: str,
                       workdir: Path, dry_run: bool) -> str:
    repo = config['repo']
    base = config.get('branch') or github.default_branch(repo)
    branch = f'version-{latest}'
    if not dry_run and github.branch_exists(repo, branch):
        return f'branch {branch} already exists, skipping'

    checkout = workdir / repo.replace('/', '_')
    git('clone', '--quiet', '--depth', '1', '--branch', base, github.clone_url(repo), str(checkout))

    options = RepoOptions(
        readme=config.get('readme', 'README.md'),
        neo=config.get('neo', defaults.get('neo', RepoOptions.neo)),
    )
    result = update_repository(checkout, latest, lex, options)
    if result is None:
        return 'already up to date'

    git('add', '--all', cwd=checkout)
    log(git('diff', '--cached', '--stat', cwd=checkout))
    if dry_run:
        return f'would update {result.previous_version} -> {latest} in {result.dir} (dry run)'

    title = f'feat: {latest}'
    git('checkout', '--quiet', '-b', branch, cwd=checkout)
    git('-c', f'user.name={BOT_NAME}', '-c', f'user.email={BOT_EMAIL}',
        'commit', '--quiet', '-m', title, cwd=checkout)
    git('push', '--quiet', 'origin', branch, cwd=checkout)

    body = f'Automatic commit: build and run {latest} in {result.dir}'
    if result.new_dir:
        body += f'\n\nCreated `{result.dir}` as a copy of the project for {result.previous_version}.'
    pull_request = github.create_pull_request(repo, branch, base, title, body)
    github.add_assignees(repo, pull_request['number'], config.get('assignees', defaults.get('assignees', [])))
    return f'opened {pull_request["html_url"]}'


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG, help='repositories.json to use')
    parser.add_argument('--repo', action='append', help='only process this repository (can be repeated)')
    parser.add_argument('--version', help='use this Minecraft version instead of the latest release')
    parser.add_argument('--lex', help='use this Forge version instead of looking it up')
    parser.add_argument('--dry-run', action='store_true', help='apply the changes locally but do not push')
    parser.add_argument('--workdir', type=Path, help='directory to clone into, a temporary one by default')
    args = parser.parse_args(argv)

    with open(args.config, encoding='utf-8') as f:
        config = json.load(f)
    defaults = config.get('defaults', {})

    latest = args.version or fetch_latest_release()
    log(f'Latest release: {latest}')
    if McVersion.parse(latest) is None:
        raise ValueError(f'Cannot handle Minecraft version {latest}')

    lex = args.lex or fetch_lexforge_version(latest)
    if lex is None:
        # Forge usually needs a few days for a new version, we will try again on the next run
        log(f'::warning::No Forge version for {latest} found yet, skipping.')
        summary(f'No Forge version for {latest} found yet.')
        return 0

    token = os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
    if not token and not args.dry_run:
        raise RuntimeError('GH_TOKEN is required to push and open pull requests')
    github = GitHub(token)

    failed = False
    summary(f'## Minecraft {latest} (Forge {lex})\n')
    with tempfile.TemporaryDirectory() as tmp:
        workdir = args.workdir or Path(tmp)
        workdir.mkdir(parents=True, exist_ok=True)
        for repo_config in config['repositories']:
            repo = repo_config['repo']
            if args.repo and repo not in args.repo:
                continue
            if not repo_config.get('enabled', True) and not args.repo:
                log(f'{repo}: disabled')
                continue

            log(f'::group::{repo}')
            try:
                message = process_repository(github, repo_config, defaults, latest, lex, workdir, args.dry_run)
            except Exception as e:
                traceback.print_exc()
                message = f'failed: {e}'
                failed = True
            log('::endgroup::')
            log(f'{repo}: {message}')
            summary(f'- **{repo}**: {message}')

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
