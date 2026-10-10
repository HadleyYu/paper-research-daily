#!/usr/bin/env python3
"""Run from a clone or an installed skill without editable installation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from paper_daily.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
