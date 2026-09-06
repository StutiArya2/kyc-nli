"""KYC-NLI: document-level natural language inference for identity-document verification."""

__version__ = "0.1.0"

from kyc_nli.schema import (
    Field,
    FieldObservation,
    Instance,
    Label,
    Script,
    Zone,
)

__all__ = [
    "Field",
    "FieldObservation",
    "Instance",
    "Label",
    "Script",
    "Zone",
    "__version__",
]
