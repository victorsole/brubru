"""The trigger-matrix data files must be well-formed: six questions per topic, real guides.

No matcher is run here (that is `scripts/check_trigger_matrix.py`, which loads every guide); this
only stops a malformed data file from turning the check into a pass over fewer questions.
"""
import json
import pathlib

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_every_matrix_file_is_well_formed():
    files = sorted((_BACKEND / "data" / "trigger_matrix").glob("*.json"))
    assert files, "no trigger-matrix data file found"
    for f in files:
        spec = json.loads(f.read_text(encoding="utf-8"))
        langs = spec["languages"]
        assert len(langs) == 6
        assert spec["topics"], f.name
        for key, questions in spec["topics"].items():
            gid = key.split("#")[0]
            assert (_BACKEND / "knowledge_base" / "guides" / f"{gid}.md").exists(), (f.name, gid)
            assert len(questions) == len(langs), (f.name, key)
            assert all(isinstance(q, str) and q.strip() for q in questions), (f.name, key)
        assert spec["negatives"], f.name
