"""External (measured) datasets and their provenance.

No third-party data is bundled with PumpGuard AI. Loaders read files that the
user has obtained from the original source under its own licence.
"""

from .provenance import REQUIRED_FIELDS, ProvenanceError, validate_provenance

__all__ = ["REQUIRED_FIELDS", "ProvenanceError", "validate_provenance"]
