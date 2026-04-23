"""
Shared pytest fixtures for MelodyMind tests.
"""

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def local_tmp_path():
    """
    Create a temporary directory inside the repository to avoid system temp
    permission issues in sandboxed environments.
    """
    root = Path(__file__).resolve().parent.parent / ".test_tmp"
    root.mkdir(exist_ok=True)

    path = root / str(uuid.uuid4())
    path.mkdir()

    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
