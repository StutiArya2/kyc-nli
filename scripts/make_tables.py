"""Regenerate current paper outputs from pinned v1 records, never legacy caches."""
from __future__ import annotations

from pathlib import Path

from kyc_nli.paper_v1 import run

if __name__ == "__main__":
    print(run(Path("configs/experiments/paper_v1.yaml")))
