"""GET /api/report/<id>/download: the Markdown as an attachment, with no temp file left behind."""

import tempfile
from types import SimpleNamespace

import pytest

from app import create_app
from app.api import report as report_api

CONTENT = "# Report\n\nBuyers in São Paulo liked it — 72% would try it.\n"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(report_api.ReportManager, "get_report",
                        classmethod(lambda _cls, report_id: SimpleNamespace(markdown_content=CONTENT)))
    monkeypatch.setattr(report_api.ReportManager, "_get_report_markdown_path",
                        classmethod(lambda _cls, report_id: str(tmp_path / "reports" / report_id / "full_report.md")))
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_download_without_full_report_leaves_no_temp_file(client, monkeypatch, tmp_path):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    r = client.get("/api/report/rep_1/download")
    assert r.status_code == 200
    assert r.data.decode("utf-8") == CONTENT
    assert 'filename=rep_1.md' in r.headers["Content-Disposition"]
    r.close()
    assert list(scratch.iterdir()) == []


def test_download_with_full_report_sends_the_saved_file(client, tmp_path):
    path = tmp_path / "reports" / "rep_2" / "full_report.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Saved\n", encoding="utf-8")
    r = client.get("/api/report/rep_2/download")
    assert r.status_code == 200
    assert r.data == b"# Saved\n"
    assert 'filename=rep_2.md' in r.headers["Content-Disposition"]
    r.close()


def test_download_of_a_report_without_content_is_empty(client, monkeypatch):
    monkeypatch.setattr(report_api.ReportManager, "get_report",
                        classmethod(lambda _cls, report_id: SimpleNamespace(markdown_content=None)))
    r = client.get("/api/report/rep_3/download")
    assert r.status_code == 200
    assert r.data == b""
    r.close()
