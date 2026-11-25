"""Malformed numeric settings are reported by name at startup instead of crashing the import."""

import os
import subprocess
import sys

import pytest

from app import config
from app.config import Config

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def errors(monkeypatch):
    found = []
    monkeypatch.setattr(config, "_SETTING_ERRORS", found)
    return found


def test_valid_and_missing_values(monkeypatch, errors):
    monkeypatch.setenv("MM_TEST_INT", " 7 ")
    monkeypatch.setenv("MM_TEST_FLOAT", "0.25")
    monkeypatch.setenv("MM_TEST_BLANK", "")
    monkeypatch.delenv("MM_TEST_UNSET", raising=False)
    assert config._env_int("MM_TEST_INT", 5) == 7
    assert config._env_float("MM_TEST_FLOAT", 0.5) == 0.25
    assert config._env_int("MM_TEST_BLANK", 5) == 5
    assert config._env_float("MM_TEST_UNSET", 0.5) == 0.5
    assert errors == []


@pytest.mark.parametrize("raw", ["four", "4.5", "1e3"])
def test_bad_int_names_the_setting_and_value(monkeypatch, errors, raw):
    monkeypatch.setenv("LOCAL_GRAPH_EXTRACT_WORKERS", raw)
    assert config._env_int("LOCAL_GRAPH_EXTRACT_WORKERS", 4) == 4
    assert errors == [f"LOCAL_GRAPH_EXTRACT_WORKERS must be a whole number (got {raw!r})"]


@pytest.mark.parametrize("raw", ["warm", "nan", "inf"])
def test_bad_float_names_the_setting_and_value(monkeypatch, errors, raw):
    monkeypatch.setenv("REPORT_AGENT_TEMPERATURE", raw)
    assert config._env_float("REPORT_AGENT_TEMPERATURE", 0.5) == 0.5
    assert errors == [f"REPORT_AGENT_TEMPERATURE must be a number (got {raw!r})"]


@pytest.mark.parametrize("raw", ["0", "65536", "port"])
def test_port_must_be_in_range(monkeypatch, errors, raw):
    monkeypatch.setenv("FLASK_PORT", raw)
    assert config._env_int("FLASK_PORT", 5001, 1, 65535) == 5001
    assert errors == [f"FLASK_PORT must be a whole number between 1 and 65535 (got {raw!r})"]


def test_validate_and_local_startup_report_setting_errors(monkeypatch, errors):
    import run
    errors.append("COGNEE_INGEST_BATCH must be a whole number (got 'x')")
    assert errors[0] in Config.validate()
    assert run.startup_errors("127.0.0.1", False, local_app=True) == errors


def test_run_py_exits_1_with_one_line_per_bad_setting(tmp_path):
    env = dict(os.environ, REPORT_AGENT_TEMPERATURE="warm", LOCAL_GRAPH_EXTRACT_WORKERS="four",
               FLASK_HOST="127.0.0.1", MM_TASK_DB_PATH=str(tmp_path / "t.sqlite"),
               LLM_API_KEY=os.environ.get("LLM_API_KEY") or "test-key")
    env.pop("MM_ENV", None)
    p = subprocess.run([sys.executable, os.path.join(BACKEND_DIR, "run.py")], cwd=BACKEND_DIR, env=env,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    assert "Traceback" not in p.stdout + p.stderr
    lines = p.stdout.splitlines()
    assert "  - REPORT_AGENT_TEMPERATURE must be a number (got 'warm')" in lines
    assert "  - LOCAL_GRAPH_EXTRACT_WORKERS must be a whole number (got 'four')" in lines
