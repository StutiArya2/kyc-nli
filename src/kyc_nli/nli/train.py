"""Fine-tune the cross-encoder. Runs on a CPU, slowly, or a GPU, quickly.

Written as a plain torch loop rather than with ``Trainer`` because the loop is
twenty lines, and because the two decisions that make CPU training viable --
freezing the embedding matrix and selecting on dev macro-F1 rather than loss --
are both clearer stated explicitly than configured indirectly.

FREEZING THE EMBEDDINGS. In distilbert-base-multilingual-cased, 92M of 135M
parameters are the embedding table. Freezing it halves wall-clock time per step
and costs little here: the task is not about learning new word meanings, it is
about learning a relation between two spans of text whose vocabulary the
pretrained model already covers. On a GPU, unfreeze it -- pass
``--no-freeze-embeddings``.

WHAT THIS IS AND IS NOT. A distilled multilingual model fine-tuned on CPU is a
floor, not a ceiling. It answers "does a learned model beat the rule engine at
all, and where", which is the question M3 exists to answer. It does not answer
"how good can this get" -- that needs the GPU run in notebooks/m3_colab.ipynb.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from kyc_nli.data.io import load_instances
from kyc_nli.languages import repo_root
from kyc_nli.nli.dataset import LABELS, to_pairs


@dataclass
class TrainConfig:
    base_model: str = "distilbert-base-multilingual-cased"
    train_path: str = "data/processed/synth_v0.train.jsonl"
    dev_path: str = "data/processed/synth_v0.dev.jsonl"
    output_dir: str = "results/models/cross_encoder"
    max_length: int = 192
    batch_size: int = 16
    epochs: int = 3
    learning_rate: float = 3e-5
    weight_decay: float = 0.01
    warmup_fraction: float = 0.1
    freeze_embeddings: bool = True
    seed: int = 20260906
    device: str = "cpu"
    #: Cap on training instances, for a quick smoke run. 0 = use all.
    max_train: int = 0


def _macro_f1(gold: list[int], pred: list[int], n_classes: int = 3) -> float:
    total = 0.0
    for k in range(n_classes):
        tp = sum(1 for g, p in zip(gold, pred, strict=True) if g == k and p == k)
        fp = sum(1 for g, p in zip(gold, pred, strict=True) if g != k and p == k)
        fn = sum(1 for g, p in zip(gold, pred, strict=True) if g == k and p != k)
        denom = 2 * tp + fp + fn
        total += (2 * tp / denom) if denom else 0.0
    return total / n_classes


def train(config: TrainConfig, log=print) -> dict:
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.manual_seed(config.seed)
    root = repo_root()

    train_instances = load_instances(root / config.train_path)
    dev_instances = load_instances(root / config.dev_path)
    if config.max_train:
        train_instances = train_instances[: config.max_train]

    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        config.base_model, num_labels=len(LABELS)
    )

    if config.freeze_embeddings:
        base = getattr(model, model.base_model_prefix)
        for param in base.embeddings.parameters():
            param.requires_grad = False

    trainable = [p for p in model.parameters() if p.requires_grad]
    log(
        f"{sum(p.numel() for p in trainable) / 1e6:.0f}M trainable of "
        f"{sum(p.numel() for p in model.parameters()) / 1e6:.0f}M total"
    )

    def encode(instances):
        premises, hypotheses, labels = to_pairs(instances)
        enc = tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=config.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        return TensorDataset(
            enc["input_ids"], enc["attention_mask"], torch.tensor(labels)
        )

    train_loader = DataLoader(
        encode(train_instances), batch_size=config.batch_size, shuffle=True
    )
    dev_loader = DataLoader(encode(dev_instances), batch_size=config.batch_size * 2)

    optimiser = torch.optim.AdamW(
        trainable, lr=config.learning_rate, weight_decay=config.weight_decay
    )
    total_steps = len(train_loader) * config.epochs
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimiser,
        max_lr=config.learning_rate,
        total_steps=total_steps,
        pct_start=config.warmup_fraction,
    )

    model.to(config.device)
    output = root / config.output_dir
    output.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    best_f1 = -1.0
    started = time.time()

    for epoch in range(1, config.epochs + 1):
        model.train()
        running = 0.0
        for step, (ids, mask, labels) in enumerate(train_loader, start=1):
            out = model(
                input_ids=ids.to(config.device),
                attention_mask=mask.to(config.device),
                labels=labels.to(config.device),
            )
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            optimiser.step()
            scheduler.step()
            optimiser.zero_grad()
            running += float(out.loss.detach())
            if step % 25 == 0:
                elapsed = time.time() - started
                log(
                    f"  epoch {epoch} step {step}/{len(train_loader)} "
                    f"loss {running / step:.4f} ({elapsed / 60:.1f} min)"
                )

        model.eval()
        gold: list[int] = []
        pred: list[int] = []
        with torch.no_grad():
            for ids, mask, labels in dev_loader:
                logits = model(
                    input_ids=ids.to(config.device), attention_mask=mask.to(config.device)
                ).logits
                pred += logits.argmax(dim=-1).tolist()
                gold += labels.tolist()
        dev_f1 = _macro_f1(gold, pred)
        history.append(
            {"epoch": epoch, "train_loss": running / len(train_loader), "dev_macro_f1": dev_f1}
        )
        log(
            f"epoch {epoch}: train loss {running / len(train_loader):.4f}  "
            f"dev macro-F1 {dev_f1:.4f}"
        )

        # Select on dev macro-F1, not on loss. Loss is dominated by the majority
        # class; macro-F1 is what the evaluation protocol reports.
        if dev_f1 > best_f1:
            best_f1 = dev_f1
            model.save_pretrained(output)
            tokenizer.save_pretrained(output)
            log(f"  saved (best so far) to {output}")

    summary = {
        "config": asdict(config),
        "history": history,
        "best_dev_macro_f1": best_f1,
        "minutes": (time.time() - started) / 60,
        "n_train": len(train_instances),
        "n_dev": len(dev_instances),
    }
    (output / "training_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
