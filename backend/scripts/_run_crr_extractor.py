"""Wrapper: pre-aliases backend.X → X to bypass the codebase's mixed-import style, then runs the requirements extractor on cluster 22 (CRR)."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Pre-load the canonical modules under backend.X, then alias to bare names
# so that the service-side `from models.eu_law import ...` finds the SAME module
# instance as the script-side `from backend.models.eu_law import ...`.
import backend.core.database
sys.modules["core"] = sys.modules["backend.core"]
sys.modules["core.database"] = sys.modules["backend.core.database"]

import backend.models
sys.modules["models"] = sys.modules["backend.models"]

import backend.models.eu_law
sys.modules["models.eu_law"] = sys.modules["backend.models.eu_law"]

import backend.models.user
sys.modules["models.user"] = sys.modules["backend.models.user"]

# Now safe to import the extractor
from backend.scripts.extract_requirements_for_cluster import extract_requirements_for_cluster

if __name__ == "__main__":
    extract_requirements_for_cluster(cluster_id=22)
