"""Profile assembly. OWNER B. See docs/trd-b-profile.md.

load_profile() is what C and D call. Keep that signature stable.
"""

from palate import contracts, db  # noqa: F401


def build_profile() -> dict:
    """Run every metric, assemble, validate evidence, write a taste_profile row.

    Before writing:
        missing = contracts.profile_is_sourced(profile)
        if missing: raise ValueError(f"unsourced profile keys: {missing}")

    Fail loudly. An unsourced number must never reach the stage.
    """
    raise NotImplementedError


def load_profile() -> dict | None:
    """Latest taste_profile row, parsed. THE CROSS-OWNER SEAM — do not rename."""
    raise NotImplementedError


def explain(key: str) -> str:
    """Print the rows behind one metric. Settles a 3 AM argument in ten seconds."""
    raise NotImplementedError
