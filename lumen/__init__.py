"""LUMEN Science: a local research workbench."""
import sys
from pathlib import Path
_vendor = Path(__file__).resolve().parent.parent / ".vendor"
if _vendor.is_dir() and not getattr(sys, "frozen", False):
    sys.path.insert(0,str(_vendor))
__version__ = "0.2.1"
