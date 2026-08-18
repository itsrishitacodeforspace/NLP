"""Streamlit dashboard entrypoint."""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running `streamlit run`.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("STREAMLIT_THEME_BASE", "light")
