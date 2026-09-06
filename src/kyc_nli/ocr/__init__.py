"""OCR-side modelling. Currently simulation only; no real engine is wired in."""

from kyc_nli.ocr.noise import NOISE_PRESETS, NoiseConfig, OCRNoiser

__all__ = ["NOISE_PRESETS", "NoiseConfig", "OCRNoiser"]
