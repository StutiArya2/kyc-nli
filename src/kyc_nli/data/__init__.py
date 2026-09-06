"""Dataset construction: fabricated identities, MRZ encoding, instance generation."""

from kyc_nli.data.generate import GeneratorConfig, Identity, InstanceGenerator
from kyc_nli.data.io import load_instances, save_instances, write_manifest

__all__ = [
    "GeneratorConfig",
    "Identity",
    "InstanceGenerator",
    "load_instances",
    "save_instances",
    "write_manifest",
]
