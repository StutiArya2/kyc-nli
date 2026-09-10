"""Train the cross-encoder. Entry point for the M3 CPU run.

Usage:
    python scripts/train_cross_encoder.py [--epochs 3] [--max-train 0]

On a GPU, pass --device cuda --no-freeze-embeddings for the real run; see
notebooks/m3_colab.ipynb.
"""

from __future__ import annotations

import argparse
import sys

from kyc_nli.nli.train import TrainConfig, train


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--max-train", type=int, default=0, help="0 = all")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--base-model", default=TrainConfig.base_model)
    parser.add_argument("--output-dir", default=TrainConfig.output_dir)
    parser.add_argument("--no-freeze-embeddings", action="store_true")
    args = parser.parse_args()

    config = TrainConfig(
        base_model=args.base_model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_length=args.max_length,
        learning_rate=args.learning_rate,
        max_train=args.max_train,
        device=args.device,
        freeze_embeddings=not args.no_freeze_embeddings,
    )
    summary = train(config)
    print(f"\nbest dev macro-F1: {summary['best_dev_macro_f1']:.4f}")
    print(f"took {summary['minutes']:.1f} minutes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
