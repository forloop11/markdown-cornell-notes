"""Shared fixtures for the editor app's tests (app/pipeline.py, app/api.py).

Both modules are imported directly (not installed as packages) --
pytest.ini's `pythonpath = app scripts` makes them importable.
"""
import pytest


@pytest.fixture
def project(tmp_path):
    """An isolated md/yaml/pdf/assets project directory, so tests never
    touch the real repo's md/, yaml/, pdf/, or assets/.
    """
    root = tmp_path / "project"
    for name in ("md", "yaml", "pdf", "assets"):
        (root / name).mkdir(parents=True)
    return root
