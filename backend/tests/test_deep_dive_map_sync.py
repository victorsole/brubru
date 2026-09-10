"""The Python deep-dive map must not drift from its TypeScript source of truth.

On 10 September 2026 the TS map declared 12 deep-dives and
services/comparator/deep_dives.py held 8, missing affordable-housing-act,
chips-act-2, cloud-ai-act and critical-medicines-act -- the four newest. That
module is what /search, /my-files and /resolve consult to tell a user "a Brubru
deep-dive exists for this law", so for a third of the corpus they never said it.

The module's own header had predicted it: "Keep this list in sync manually until
we wire a build-time exporter."

The copy cannot simply be deleted in favour of reading the TS at import:
backend/railway.json sets the Docker build context to `backend/`, so `frontend/`
is absent from the production image and the import would raise on boot. Hence a
generated artefact plus this test.
"""
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from scripts.generate_deep_dive_map import (  # noqa: E402
    TS_MAP, celex_from_com, current_block, parse_ts, render,
)
from services.comparator.deep_dives import DEEP_DIVES, deep_dive_for_file_ref  # noqa: E402


def test_generated_block_matches_the_ts_source():
    if not TS_MAP.exists():
        pytest.skip(f"{TS_MAP} absent (backend-only checkout or container)")
    assert current_block() == render(parse_ts()), (
        "the Python deep-dive map has drifted from frontend/src/utils/deep_dive_map.ts. "
        "Run: python3.12 -m backend.scripts.generate_deep_dive_map --write"
    )


def test_every_ts_entry_is_resolvable_from_the_backend():
    """The drift's actual symptom: a deep-dive that exists but that no backend
    surface will mention."""
    if not TS_MAP.exists():
        pytest.skip("TS source of truth absent")
    unreachable = []
    for entry in parse_ts():
        ref = entry["procedure_ref"]
        if not ref:
            continue
        if deep_dive_for_file_ref(ref) is None:
            unreachable.append((entry["base_path"], ref))
    assert not unreachable, f"deep-dives no backend surface can resolve: {unreachable}"


def test_com_reference_to_celex_is_exact():
    """Checked against all eight hand-written entries this replaced."""
    assert celex_from_com("COM(2026) 321") == ["52026PC0321"]
    assert celex_from_com("COM(2025) 1022") == ["52025PC1022"]
    assert celex_from_com("COM(2026) 16") == ["52026PC0016"]
    assert celex_from_com("COM(2023) 192 + COM(2023) 193") == ["52023PC0192", "52023PC0193"]
    assert celex_from_com("") == []


def test_the_map_is_never_silently_empty():
    """An empty index removes every deep-dive cross-link with nothing looking
    broken, which is the failure mode this whole file exists to prevent."""
    assert len(DEEP_DIVES) >= 12
    assert all(d["base_path"] for d in DEEP_DIVES)
