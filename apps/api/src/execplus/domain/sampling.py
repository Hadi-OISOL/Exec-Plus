"""Use case: Chooses a bounded, reproducible row sample of a big snapshot.

What it does: Picks row positions uniformly without replacement (Floyd's algorithm driven by
splitmix64 with a fixed seed), so the same file always yields the same sample on any Python
or DuckDB version, and names the sample in receipts and user-facing labels.
"""

from execplus.domain.ingestion import IngestionError

METHOD = "floyd-splitmix64-v1"
SEED = 20261026
_MASK = (1 << 64) - 1


def _splitmix64(state: int) -> tuple[int, int]:
    state = (state + 0x9E3779B97F4A7C15) & _MASK
    value = ((state ^ (state >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK
    return state, value ^ (value >> 31)


def sample_positions(total: int, size: int, seed: int = SEED) -> tuple[int, ...]:
    """Sorted zero-based positions of `size` distinct rows out of `total`."""
    if size >= total:
        return tuple(range(total))
    state = seed & _MASK
    chosen: set[int] = set()
    for upper in range(total - size, total):
        state, value = _splitmix64(state)
        candidate = value % (upper + 1)
        chosen.add(upper if candidate in chosen else candidate)
    return tuple(sorted(chosen))


def spec(size: int) -> str:
    return f"{METHOD}/{SEED}/{size}"


def parse_spec(value: str) -> tuple[int, int]:
    """Seed and size of a recorded sample; refuses methods this version cannot reproduce."""
    try:
        method, seed, size = value.split("/")
        if method != METHOD or int(size) < 1:
            raise ValueError
        return int(seed), int(size)
    except ValueError:
        raise IngestionError(
            "unsupported_version", "This saved sample method is unavailable.", 409
        ) from None


def label(size: int, total: int) -> str:
    return (
        f"Based on a fixed random sample of {size:,} of {total:,} rows "
        f"(method {METHOD}, seed {SEED}); sampled figures are estimates, not exact totals."
    )
