"""Shared pytest fixtures. All tests run against the backend in demo mode."""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure demo mode + an isolated data dir BEFORE importing the app.
os.environ["OMR_DASHBOARD_DEMO"] = "true"
_TMP = tempfile.mkdtemp(prefix="omr-dash-test-")
os.environ["OMR_DASHBOARD_DATA_DIR"] = _TMP

from fastapi.testclient import TestClient  # noqa: E402

import omr_dashboard_api  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(omr_dashboard_api.app) as c:
        yield c
