"""Every column an endpoint filters ?updated_from= on must exist ON THE MODEL.

/parliament/ep-documents answered 500 to every windowed call on 28 Sep 2026: the
amendment_documents TABLE had updated_at and a trigger guarding it, but the SQLAlchemy
model never declared the column, so AmendmentDocument.updated_at raised AttributeError.
Only the windowed call broke, so the unwindowed 200 hid it.

A table column and a model column are two different facts. This test reads the filters
out of api/ and resolves each one against the model that is actually imported.
"""
import importlib
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
FILTER = re.compile(r"\b([A-Z][A-Za-z_]+)\.([a-z_]+)\s*>=\s*(?:w\[\"updated_from\"\]|updated_from)")


def _filters():
    """(model name, column) for every incremental filter under api/."""
    found = set()
    for path in (BACKEND / "api").rglob("*.py"):
        for model, col in FILTER.findall(path.read_text(errors="ignore")):
            found.add((model, col))
    return sorted(found)


def _model_modules():
    """model class name -> dotted module path, read from models/."""
    out = {}
    for path in (BACKEND / "models").rglob("*.py"):
        mod = "models." + str(path.relative_to(BACKEND / "models")).replace("/", ".")[:-3]
        mod = mod.replace(".__init__", "")
        for name in re.findall(r"^class (\w+)\(", path.read_text(errors="ignore"), re.M):
            out.setdefault(name, mod)
    return out


def test_there_are_incremental_filters_to_check():
    """Guard the guard: a regex that matches nothing would pass every assertion."""
    assert len(_filters()) >= 15, f"only found {len(_filters())} filters; the regex has drifted"


@pytest.mark.parametrize("model_name,column", _filters())
def test_the_filter_column_exists_on_the_model(model_name, column):
    modules = _model_modules()
    if model_name not in modules:
        pytest.skip(f"{model_name} is a local alias, not a model class")
    mod = importlib.import_module(modules[model_name])
    model = getattr(mod, model_name)
    assert hasattr(model, column), (
        f"{model_name}.{column} is filtered on by an endpoint but the model does not "
        f"declare it; every ?updated_from= call on that route answers 500")
