import os
import sys

PATCH_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if PATCH_BACKEND not in sys.path:
    sys.path.insert(0, PATCH_BACKEND)
