"""Softcatala model hygiene (29 Sep 2026): one copy, no TensorFlow weights,
nothing left in the page cache Railway bills as memory."""
import os

from scripts import catalan_translate as ct


def _model(root, name):
    base = root / name / "eng-cat"
    for sub in ("ctranslate2", "tokenizer", "tensorflow/variables"):
        (base / sub).mkdir(parents=True)
    (base / "ctranslate2" / "model.bin").write_bytes(b"x")
    (base / "tensorflow" / "variables" / "variables.data").write_bytes(b"x" * 10)
    return root / name


def test_unused_tensorflow_weights_are_pruned(tmp_path):
    m = _model(tmp_path, "softcatala-en-ca")
    ct.prune_unused_model_files(str(m))
    assert not (m / "eng-cat" / "tensorflow").exists()
    assert (m / "eng-cat" / "ctranslate2" / "model.bin").exists()


def test_release_page_cache_never_raises(tmp_path):
    m = _model(tmp_path, "softcatala-en-ca")
    ct.release_model_page_cache(str(m))  # no-op on macOS, fadvise on Linux


def test_existing_sibling_copy_is_reused_not_downloaded_again(tmp_path, monkeypatch):
    sibling = _model(tmp_path, "softcatala-eng-cat")
    monkeypatch.setattr(ct, "SOFTCATALA_MODEL_DIR", str(tmp_path / "softcatala-en-ca"))
    def _no_download(*a, **k):
        raise AssertionError("must not download when the sibling copy exists")
    monkeypatch.setattr("urllib.request.urlretrieve", _no_download)
    assert ct._ensure_softcatala_model() == str(sibling)
