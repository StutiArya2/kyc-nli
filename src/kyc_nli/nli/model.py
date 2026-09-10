"""Cross-encoder NLI model, exposing the same interface as the rule baselines.

Deliberately shaped so it drops into ``kyc_nli.baselines.BASELINES`` and is
scored by the existing harness with no special-casing. A model evaluated by a
different code path than its baseline is a model whose comparison nobody can
trust.

``predict_all`` exists because the harness scores instance-by-instance and a
transformer is an order of magnitude faster batched. It returns the same
Predictions in the same order; it is a performance detail, not a different
computation.
"""

from __future__ import annotations

from pathlib import Path

from kyc_nli.languages import repo_root
from kyc_nli.nli.dataset import LABELS, serialise_hypothesis, serialise_premise
from kyc_nli.schema import Instance, Prediction

DEFAULT_MODEL_DIR = "results/models/cross_encoder"
#: Small enough to fine-tune on a CPU, multilingual enough to tokenise all five
#: scripts. Not the best available model -- that is the point of M3 running on a
#: GPU later. See docs/m3-model-findings.md.
DEFAULT_BASE_MODEL = "distilbert-base-multilingual-cased"


class CrossEncoderNLI:
    """A fine-tuned sequence-classification model over (premise, hypothesis)."""

    name = "cross_encoder"

    def __init__(
        self,
        model_dir: str | Path | None = None,
        max_length: int = 256,
        batch_size: int = 32,
        device: str = "cpu",
    ) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        path = Path(model_dir) if model_dir else repo_root() / DEFAULT_MODEL_DIR
        if not path.is_dir():
            raise FileNotFoundError(
                f"No trained model at {path}. Train one with `kyc-nli train-nli`, "
                f"or point --model-dir at a checkpoint."
            )
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self.model.eval()
        self.model.to(device)
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size

    # -- interface shared with the rule baselines --------------------------

    def predict(self, instance: Instance) -> Prediction:
        return self.predict_all([instance])[0]

    def predict_all(self, instances: list[Instance]) -> list[Prediction]:
        torch = self._torch
        out: list[Prediction] = []
        for start in range(0, len(instances), self.batch_size):
            chunk = instances[start : start + self.batch_size]
            encoded = self.tokenizer(
                [serialise_premise(i) for i in chunk],
                [serialise_hypothesis(i) for i in chunk],
                truncation=True,
                max_length=self.max_length,
                padding=True,
                return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                logits = self.model(**encoded).logits
            probs = torch.softmax(logits, dim=-1)
            best = probs.argmax(dim=-1)
            for row, inst in enumerate(chunk):
                idx = int(best[row])
                out.append(
                    Prediction(
                        instance_id=inst.id,
                        label=LABELS[idx],
                        confidence=float(probs[row, idx]),
                        rationale=(
                            "Cross-encoder over the serialised document and claim. "
                            "Probabilities: "
                            + ", ".join(
                                f"{lab.value}={float(probs[row, i]):.3f}"
                                for i, lab in enumerate(LABELS)
                            )
                        ),
                    )
                )
        return out
