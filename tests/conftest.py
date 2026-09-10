"""Shared fixtures for testing app/pipeline.py and scripts/simple_yaml.py.

Both modules are imported directly (not installed as packages), so this
file's only job before collection is making sure they're importable --
pytest.ini's `pythonpath = app scripts` setting handles that.
"""
import pytest

import pipeline


@pytest.fixture
def project(tmp_path, monkeypatch):
    """An isolated md/yaml/pdf/assets tree, with pipeline's module-level
    path constants (normally derived once from the real CWD at import
    time -- see pipeline.py's own PROJECT_ROOT comment) redirected at it,
    so tests never touch the real repo's md/, yaml/, pdf/, or assets/.
    """
    for name in ("md", "yaml", "pdf", "assets"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "MD_DIR", tmp_path / "md")
    monkeypatch.setattr(pipeline, "YAML_DIR", tmp_path / "yaml")
    monkeypatch.setattr(pipeline, "PDF_DIR", tmp_path / "pdf")
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    return tmp_path
