"""Applies a new Minecraft version to a checked out repository.

A repository is expected to have the layout of hmc-specifics / mc-runtime-test-mod:
a ci-data.json in its root and one Gradle project per Minecraft version (e.g. 26_2, 1_21_10).
"""
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .versions import McVersion

DEFAULT_NEO_VERSION = '0-beta'
DEFAULT_RUN_DATA = [
    {"type": "fabric", "modloader": "fabric", "regex": ".*fabric.*"},
    {"type": "neoforge", "modloader": "neoforge", "regex": ".*neoforge.*"},
    {"type": "lexforge", "modloader": "forge", "regex": ".*forge.*"},
]
IGNORED_DIRS = ('build', 'out', 'run', 'bin', '.gradle', '.idea')


@dataclass
class RepoOptions:
    # How the version table in the README groups versions into rows:
    # "minor": one row per minor version (1.21 - 1.21.11 | 26.1 - 26.1.2 | 26.2)
    # "major": one row per major version (26.1 - 26.3)
    readme_group: str = 'minor'
    readme: str = 'README.md'
    neo: str = DEFAULT_NEO_VERSION


@dataclass
class UpdateResult:
    previous_version: str
    version: str
    dir: str
    new_dir: bool


def modify_file(file_path: Path, func: Callable[[str], str]):
    content = file_path.read_text(encoding='utf-8')
    new_content = func(content)
    if new_content != content:
        file_path.write_text(new_content, encoding='utf-8')


def format_version(major: int, minor: int, components: int) -> str:
    """Formats major.minor with the given amount of components, padded with zeros, e.g. 26.2.0."""
    return '.'.join([str(major), str(minor)] + ['0'] * max(components - 2, 0))


def modify_gradle_properties(content: str, latest: str, lex: str, neo: Optional[str]) -> str:
    content = re.sub(r'(?m)^(\s*minecraft_version\s*=\s*).*$', lambda m: m.group(1) + latest, content)
    content = re.sub(r'(?m)^(\s*lexforge_version\s*=\s*).*$', lambda m: m.group(1) + lex, content)
    if neo is not None:
        content = re.sub(r'(?m)^(\s*neoforge_version\s*=\s*).*$', lambda m: m.group(1) + neo, content)
    return content


def modify_fabric_mod_json(content: str, version: McVersion) -> str:
    # "minecraft": "~26.2.0" or "minecraft": "~26.3", keeps the operator and the amount of components
    def replace(match: re.Match) -> str:
        components = match.group(3).count('.') + 1
        return f'{match.group(1)}{match.group(2)}{format_version(version.major, version.minor, components)}"'

    return re.sub(r'("minecraft"\s*:\s*")([~^<>=]*)(\d+(?:\.\d+)*)"', replace, content)


def modify_mods_toml(content: str, version: McVersion) -> str:
    # only touch the versionRange of the minecraft dependency, e.g. [26.2.0,) or [26.3,26.4)
    def replace(match: re.Match) -> str:
        lower, upper = match.group(3), match.group(4)
        if lower.strip():
            lower = format_version(version.major, version.minor, lower.count('.') + 1)
        if upper.strip():
            upper = format_version(version.major, version.minor + 1, upper.count('.') + 1)
        return f'{match.group(1)}{match.group(2)}{lower},{upper}{match.group(5)}"'

    sections = re.split(r'(?m)^(?=[ \t]*\[)', content)
    for i, section in enumerate(sections):
        if re.search(r'(?m)^\s*modId\s*=\s*"minecraft"', section):
            sections[i] = re.sub(r'(versionRange\s*=\s*")([\[(])([^,"]*),([^,"]*?)([)\]])"', replace, section)

    return ''.join(sections)


def prepare_new_dir(root: Path, curr_dir: str, version: McVersion, latest: str, lex: str, neo: Optional[str]) -> str:
    new_dir = version.dir_name
    if not (root / new_dir).exists():
        shutil.copytree(root / curr_dir, root / new_dir, ignore=shutil.ignore_patterns(*IGNORED_DIRS))

    for dir_path, dir_names, file_names in os.walk(root / new_dir):
        dir_names[:] = [d for d in dir_names if d not in IGNORED_DIRS]
        for file_name in file_names:
            file_path = Path(dir_path) / file_name
            if file_name == 'gradle.properties':
                modify_file(file_path, lambda c: modify_gradle_properties(c, latest, lex, neo))
            elif file_name == 'fabric.mod.json':
                modify_file(file_path, lambda c: modify_fabric_mod_json(c, version))
            elif file_name.endswith('mods.toml'):
                modify_file(file_path, lambda c: modify_mods_toml(c, version))

    return new_dir


def find_current_version(build_data: list) -> tuple[McVersion, dict]:
    versioned = [(McVersion.parse(entry['mc']), entry) for entry in build_data if McVersion.parse(entry.get('mc', ''))]
    if not versioned:
        raise ValueError('ci-data.json does not contain any Minecraft versions')
    return max(versioned, key=lambda pair: pair[0])


def create_run_data(run_data: list, latest: str, java: str) -> list:
    """Copies the run_data entries of the newest Minecraft version for the new version."""
    versions = [McVersion.parse(entry.get('mc', '')) for entry in run_data]
    versions = [v for v in versions if v is not None]
    if versions:
        newest = str(max(versions))
        templates = [entry for entry in run_data if McVersion.parse(entry.get('mc', '')) == McVersion.parse(newest)]
    else:
        templates = DEFAULT_RUN_DATA

    result = []
    for template in templates:
        entry = {"mc": latest}
        entry.update({key: value for key, value in template.items() if key != 'mc'})
        entry['java'] = java
        result.append(entry)
    return result


def update_ci_data(ci_data: dict, template: dict, curr_dir: str, latest: str, lex: str, neo: str):
    build_data = ci_data['build_data']
    entry = {key: value for key, value in template.items()}
    entry.update({"dir": curr_dir, "mc": latest, "lex": lex})
    if 'neo' in template:
        entry['neo'] = neo
    # insert before the first version entry, so entries like the api project stay at the top
    index = next((i for i, e in enumerate(build_data) if McVersion.parse(e.get('mc', ''))), 0)
    build_data.insert(index, entry)

    run_data = ci_data.get('run_data')
    if run_data is not None and not any(e.get('mc') == latest for e in run_data):
        run_data[0:0] = create_run_data(run_data, latest, template['java'])


def update_current_version_json(file_path: Path, version: McVersion, curr_dir: str):
    with open(file_path, encoding='utf-8') as f:
        current_version = json.load(f)

    current_version['major'] = version.major
    current_version['minor'] = version.minor
    current_version['patch'] = version.patch
    current_version['dir'] = curr_dir
    file_path.write_text(json.dumps(current_version, indent='\t'), encoding='utf-8')


def _split_first_cell(line: str) -> Optional[tuple[str, str, str]]:
    """Returns (prefix, cell, rest) for a markdown table row like '| 26.1 - 26.3 | ...'."""
    match = re.match(r'^(\s*\|)([^|]*)(\|.*)$', line, re.S)
    if match is None:
        return None
    return match.group(1), match.group(2), match.group(3)


def _replace_first_cell(line: str, text: str) -> str:
    prefix, cell, rest = _split_first_cell(line)
    leading = cell[:len(cell) - len(cell.lstrip())] or ' '
    new_cell = f"{leading}{text}"
    # keep the column aligned if the original cell was padded
    new_cell = new_cell.ljust(len(cell)) if len(new_cell) < len(cell) else new_cell + ' '
    return prefix + new_cell + rest


def modify_readme(content: str, current: str, latest: str, group: str) -> str:
    current_version, latest_version = McVersion.parse(current), McVersion.parse(latest)
    if group == 'major':
        same_row = current_version.major == latest_version.major
    else:
        same_row = current_version.same_minor(latest_version)

    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        split = _split_first_cell(line)
        if split is None:
            continue

        cell = split[1].strip()
        range_match = re.fullmatch(r'(\S+)\s*-\s*(\S+)', cell)
        if cell == current:
            start = current
        elif range_match is not None and range_match.group(2) == current:
            start = range_match.group(1)
        else:
            continue

        if same_row:
            lines[i] = _replace_first_cell(line, f"{start} - {latest}")
        else:
            lines.insert(i, _replace_first_cell(line, latest))
        break

    content = ''.join(lines)
    # usage examples like "mc: 26.1.1"
    return re.sub(r'(?m)^(\s*mc:\s*)\d+\.\d+(?:\.\d+)?(\s*)$', lambda m: m.group(1) + latest + m.group(2), content)


def update_repository(root: Path, latest: str, lex: str, options: RepoOptions = RepoOptions()) -> Optional[UpdateResult]:
    """Updates the repository at root to the given Minecraft version.

    Returns None if the repository already contains the given version or a newer one.
    """
    latest_version = McVersion.parse(latest)
    if latest_version is None:
        raise ValueError(f"Not a release version: {latest}")

    ci_data_path = root / 'ci-data.json'
    ci_data_content = ci_data_path.read_text(encoding='utf-8')
    ci_data = json.loads(ci_data_content)
    current_version, template = find_current_version(ci_data['build_data'])
    if latest_version <= current_version:
        return None

    curr_dir = template['dir']
    neo = options.neo if 'neo' in template else None
    new_dir = not current_version.same_minor(latest_version)
    if new_dir:
        curr_dir = prepare_new_dir(root, curr_dir, latest_version, latest, lex, neo)

    update_ci_data(ci_data, template, curr_dir, latest, lex, options.neo)
    trailing_newline = '\n' if ci_data_content.endswith('\n') else ''
    ci_data_path.write_text(json.dumps(ci_data, indent='\t') + trailing_newline, encoding='utf-8')

    current_version_json = root / 'current-version.json'
    if current_version_json.exists():
        update_current_version_json(current_version_json, latest_version, curr_dir)

    readme = root / options.readme
    if readme.exists():
        modify_file(readme, lambda c: modify_readme(c, template['mc'], latest, options.readme_group))

    return UpdateResult(previous_version=template['mc'], version=latest, dir=curr_dir, new_dir=new_dir)
