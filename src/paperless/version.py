from typing import Final

__version__: Final[tuple[int, int, int]] = (2, 13, 5)
# Version string like X.Y.Z
__full_version_str__: Final[str] = ".".join(map(str, __version__))
# Version string like X.Y
__major_minor_version_str__: Final[str] = ".".join(map(str, __version__[:-1]))
