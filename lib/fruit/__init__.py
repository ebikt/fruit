from .decoder import decode
from .encoder import encode
from .logging import *
# TOML is not required for library
try:
    from .ftoml   import dump, load
except ImportError:
    pass
