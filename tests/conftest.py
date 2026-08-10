"""Make the package importable when tests run from the code/ directory without
an editable install. pyproject also sets pythonpath=["src"]; this is a belt-and-
suspenders fallback so `python -m pytest` works out of the box.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
