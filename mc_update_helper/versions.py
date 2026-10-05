import re
from dataclasses import dataclass
from typing import Optional

import requests

VERSION_MANIFEST_URL = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
LEXFORGE_INDEX_URL = 'https://meta.prismlauncher.org/v1/net.minecraftforge/index.json'

_VERSION_PATTERN = re.compile(r'(\d+)\.(\d+)(?:\.(\d+))?')


@dataclass(frozen=True, order=True)
class McVersion:
    major: int
    minor: int
    patch: int = 0

    @staticmethod
    def parse(version: str) -> Optional['McVersion']:
        """Parses release versions like 1.21, 1.21.11 or 26.1.2, returns None for anything else."""
        match = _VERSION_PATTERN.fullmatch(str(version).strip())
        if match is None:
            return None
        return McVersion(int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))

    def same_minor(self, other: 'McVersion') -> bool:
        return self.major == other.major and self.minor == other.minor

    @property
    def dir_name(self) -> str:
        return f"{self.major}_{self.minor}"

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}" if self.patch == 0 else f"{self.major}.{self.minor}.{self.patch}"


def fetch_latest_release() -> str:
    response = requests.get(VERSION_MANIFEST_URL, timeout=30)
    response.raise_for_status()
    return response.json()['latest']['release']


def fetch_lexforge_version(mc_version: str) -> Optional[str]:
    """Returns the newest Forge version for the given Minecraft version, or None if Forge has not released one yet."""
    response = requests.get(LEXFORGE_INDEX_URL, timeout=30)
    response.raise_for_status()
    # versions are sorted newest first, each looks like:
    # {"requires": [{"equals": "1.21.10", "uid": "net.minecraft"}], "version": "60.0.18", ...}
    for version in response.json()['versions']:
        for require in version.get('requires', []):
            if require.get('uid') == 'net.minecraft' and require.get('equals') == mc_version:
                return version['version']

    return None
