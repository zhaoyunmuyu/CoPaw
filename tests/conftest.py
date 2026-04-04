# -*- coding: utf-8 -*-
"""Root conftest: ensure worktree src is importable before collection."""
import sys
from pathlib import Path

_WORKTREE_SRC = str(Path(__file__).resolve().parent.parent / "src")

# Prepend worktree src so it takes priority over the installed package.
if _WORKTREE_SRC not in sys.path:
    sys.path.insert(0, _WORKTREE_SRC)

# Evict any already-cached copaw modules so they reload from worktree src.
_stale = [k for k in sys.modules if k == "copaw" or k.startswith("copaw.")]
for k in _stale:
    del sys.modules[k]
