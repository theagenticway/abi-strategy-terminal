# ABI Strategy Terminal Engine Package
import os
import importlib.util

try:
    from . import archive
except (ImportError, ModuleNotFoundError):
    _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive.py")
    if os.path.exists(_f):
        _s = importlib.util.spec_from_file_location("engine.archive", _f)
        archive = importlib.util.module_from_spec(_s)
        _s.loader.exec_module(archive)
