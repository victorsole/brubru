#!/usr/bin/env python3
"""Check ChromaDB status and collection counts"""

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import sys
sys.path.insert(0, _REPO_ROOT)

from backend.services.vector_db.vector_store import get_vector_store

def check_status():
    try:
        vector_store = get_vector_store()

        print("=== ChromaDB Status ===\n")

        for collection_name, collection in vector_store.collections.items():
            count = collection.count()
            print(f"{collection_name}: {count} documents")

        print("\n✅ ChromaDB is accessible")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_status()
