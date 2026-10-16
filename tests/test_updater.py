import json
from pathlib import Path

import pytest

from mc_update_helper.updater import (modify_fabric_mod_json, modify_mods_toml, modify_readme,
                                      update_repository)
from mc_update_helper.versions import McVersion

GRADLE_PROPERTIES = """org.gradle.jvmargs = -Xmx2G

minecraft_version = {mc}
mapping_version = 1
neoforge_version = 8-beta
lexforge_version = 65.0.3
fabric_version = 0.19.5
"""

FABRIC_MOD_JSON = """{{
  "depends": {{
    "fabricloader": ">=0.14.19",
    "minecraft": "{range}",
    "java": ">=8"
  }}
}}
"""

MODS_TOML = """modLoader = "javafml"
loaderVersion = "[1,)"

[[mods]]
modId = "test"

[[dependencies.test]]
modId = "minecraft"
mandatory = true
versionRange = "{range}"
ordering = "NONE"
"""

README = """| Version         | Forge | Fabric | NeoForge |
|-----------------|-------|--------|----------|
| 26.1 - 26.3     | ✅    | ✅     | ✅       |
| 1.21 - 1.21.11  | ✅    | ✅     | ✅       |

        with:
          mc: 26.1.1
          modloader: fabric
"""


def create_repo(root: Path, mc: str, dir_name: str, fabric_range: str, toml_range: str, readme: str,
                current_version_json: bool = False) -> Path:
    project = root / dir_name
    (project / 'src' / 'fabric' / 'resources').mkdir(parents=True)
    (project / 'src' / 'lexforge' / 'resources' / 'META-INF').mkdir(parents=True)
    (project / 'src' / 'neoforge' / 'resources' / 'META-INF').mkdir(parents=True)
    (project / 'gradle.properties').write_text(GRADLE_PROPERTIES.format(mc=mc))
    (project / 'src' / 'fabric' / 'resources' / 'fabric.mod.json').write_text(
        FABRIC_MOD_JSON.format(range=fabric_range))
    (project / 'src' / 'lexforge' / 'resources' / 'META-INF' / 'mods.toml').write_text(
        MODS_TOML.format(range=toml_range))
    (project / 'src' / 'neoforge' / 'resources' / 'META-INF' / 'neoforge.mods.toml').write_text(
        MODS_TOML.format(range=toml_range))
    (root / 'README.md').write_text(readme)
    ci_data = {
        "build_data": [
            {"mc": "api", "dir": "api", "java": "8"},
            {"dir": dir_name, "mc": mc, "lex": "65.0.3", "neo": "8-beta", "java": "25"},
            {"dir": "1_12", "mc": "1.12.2", "lex": "14.23.5.2860", "java": "8"},
        ],
        "run_data": [
            {"mc": "26.1.2", "type": "fabric", "modloader": "fabric", "regex": ".*fabric.*", "java": "25"},
            {"mc": "26.1.2", "type": "neoforge", "modloader": "neoforge", "regex": ".*neoforge.*", "java": "25"},
            {"mc": "1.12.2", "type": "lexforge", "modloader": "forge", "regex": ".*orge.*", "java": "8"},
        ],
    }
    (root / 'ci-data.json').write_text(json.dumps(ci_data, indent='\t'))
    if current_version_json:
        major, minor, *patch = (int(part) for part in mc.split('.'))
        (root / 'current-version.json').write_text(json.dumps(
            {"major": major, "minor": minor, "patch": patch[0] if patch else 0, "dir": dir_name, "java": "25"}))
    return root


def test_parse_version():
    assert McVersion.parse('1.21') == McVersion(1, 21, 0)
    assert McVersion.parse('26.1.2') == McVersion(26, 1, 2)
    assert McVersion.parse('api') is None
    assert McVersion.parse('26.1-snapshot-1') is None
    assert McVersion.parse('1.21.11') > McVersion.parse('1.21.2')
    assert McVersion.parse('26.1') > McVersion.parse('1.21.11')
    assert str(McVersion.parse('26.3')) == '26.3'


def test_fabric_mod_json_keeps_format():
    version = McVersion(26, 4)
    assert '"minecraft": "~26.4.0"' in modify_fabric_mod_json('"minecraft": "~26.2.0",', version)
    assert '"minecraft": "~26.4"' in modify_fabric_mod_json('"minecraft": "~26.3"', version)
    assert '"fabricloader": ">=0.14.19"' in modify_fabric_mod_json('"fabricloader": ">=0.14.19"', version)


def test_mods_toml_only_changes_minecraft_dependency():
    version = McVersion(26, 4)
    open_range = modify_mods_toml(MODS_TOML.format(range='[26.2.0,)'), version)
    assert 'versionRange = "[26.4.0,)"' in open_range
    assert 'loaderVersion = "[1,)"' in open_range
    closed_range = modify_mods_toml(MODS_TOML.format(range='[26.3,26.4)'), version)
    assert 'versionRange = "[26.4,26.5)"' in closed_range


def test_modify_readme():
    same_major = modify_readme(README, '26.3', '26.4')
    assert '| 26.1 - 26.4     | ✅' in same_major
    assert 'mc: 26.4\n' in same_major
    patch = modify_readme(README, '26.3', '26.3.1')
    assert '| 26.1 - 26.3.1   | ✅' in patch
    new_major = modify_readme(README, '26.3', '27.1')
    assert '| 27.1            | ✅    | ✅     | ✅       |\n' \
           '| 26.1 - 26.3     |' in new_major


def test_new_minor_version(tmp_path):
    root = create_repo(tmp_path, '26.2', '26_2', '~26.2.0', '[26.2.0,)', README.replace('26.3', '26.2'), current_version_json=True)
    result = update_repository(root, '26.3', '66.0.0')

    assert result.new_dir and result.dir == '26_3' and result.previous_version == '26.2'
    gradle_properties = (root / '26_3' / 'gradle.properties').read_text()
    assert 'minecraft_version = 26.3\n' in gradle_properties
    assert 'lexforge_version = 66.0.0\n' in gradle_properties
    assert 'neoforge_version = 0-beta\n' in gradle_properties
    assert 'minecraft_version = 26.2\n' in (root / '26_2' / 'gradle.properties').read_text()
    assert '"~26.3.0"' in (root / '26_3' / 'src' / 'fabric' / 'resources' / 'fabric.mod.json').read_text()
    assert '"[26.3.0,)"' in (root / '26_3' / 'src' / 'neoforge' / 'resources' / 'META-INF' /
                             'neoforge.mods.toml').read_text()

    ci_data = json.loads((root / 'ci-data.json').read_text())
    assert ci_data['build_data'][0]['dir'] == 'api'
    assert ci_data['build_data'][1] == {"dir": "26_3", "mc": "26.3", "lex": "66.0.0", "neo": "0-beta", "java": "25"}
    assert [(e['mc'], e['type'], e['java']) for e in ci_data['run_data'][:2]] == \
           [('26.3', 'fabric', '25'), ('26.3', 'neoforge', '25')]
    assert ci_data['run_data'][2]['mc'] == '26.1.2'

    current_version = json.loads((root / 'current-version.json').read_text())
    assert (current_version['major'], current_version['minor'], current_version['dir']) == (26, 3, '26_3')
    assert '| 26.1 - 26.3     |' in (root / 'README.md').read_text()


def test_new_patch_version(tmp_path):
    root = create_repo(tmp_path, '26.3', '26_3', '~26.3', '[26.3,26.4)', README)
    result = update_repository(root, '26.3.1', '66.1.0', )

    assert not result.new_dir and result.dir == '26_3'
    assert not (root / '26_3_1').exists()
    assert 'minecraft_version = 26.3\n' in (root / '26_3' / 'gradle.properties').read_text()
    ci_data = json.loads((root / 'ci-data.json').read_text())
    assert ci_data['build_data'][1]['mc'] == '26.3.1' and ci_data['build_data'][1]['dir'] == '26_3'
    assert '| 26.1 - 26.3.1   |' in (root / 'README.md').read_text()


@pytest.mark.parametrize('latest', ['26.3', '26.2', '1.21.11'])
def test_already_up_to_date(tmp_path, latest):
    root = create_repo(tmp_path, '26.3', '26_3', '~26.3', '[26.3,26.4)', README)
    ci_data = (root / 'ci-data.json').read_text()
    assert update_repository(root, latest, '66.0.0') is None
    assert (root / 'ci-data.json').read_text() == ci_data
