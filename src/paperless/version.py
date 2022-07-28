from typing import Final
from typing import Tuple

__version__: Final[Tuple[int, int, int]] = (1, 8, 0)
# Version string like X.Y.Z
__full_version_str__: Final[str] = ".".join(map(str, __version__))
# Version string like X.Y
__major_minor_version_str__: Final[str] = ".".join(map(str, __version__[:-1]))
