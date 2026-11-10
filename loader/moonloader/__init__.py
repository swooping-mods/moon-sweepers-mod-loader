"""Moon Sweepers desktop loader with an exact, repository-owned API snapshot."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vendored/api/python"))
__version__ = "0.1.0"
