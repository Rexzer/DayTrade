"""Pytest bootstrap.

Ensures the repository root is on ``sys.path`` so the pure-Python engine
packages (``strategy_engine``, ``risk_engine``, ...) and the ``backend``
package can be imported in tests without an editable install. This keeps the
core-logic test suite runnable in offline environments where web/database
dependencies are not installed.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
