"""Regenerate the same v1 figures, tables and prose-number macros."""
from __future__ import annotations

from pathlib import Path

from kyc_nli.paper_v1 import run

if __name__ == "__main__":
    print(run(Path("configs/experiments/paper_v1.yaml")))
