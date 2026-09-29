from importlib.metadata import PackageNotFoundError, version

from .cli import main
from .constants import APP_NAME

try:
    __version__ = version(APP_NAME)
except PackageNotFoundError:
    __version__ = "0.0.1"

__all__ = [
    "__version__",
    "main",
]
