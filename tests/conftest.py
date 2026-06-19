import pytest

import img2log
import img2webhook


@pytest.fixture(autouse=True)
def _isolate_img2_dir(tmp_path, monkeypatch):
    """Redirect img2log's/img2webhook's files into tmp_path so tests
    never read or write the real ~/.image2 directory."""
    monkeypatch.setattr(img2log, "IMAGE2_DIR", tmp_path)
    monkeypatch.setattr(img2log, "HISTORY_FILE", tmp_path / "history.log")
    monkeypatch.setattr(img2log, "LOG_FILE", tmp_path / "img2.log")
    monkeypatch.setattr(img2log, "_logger", None)
    monkeypatch.setattr(img2webhook, "IMAGE2_DIR", tmp_path)
    monkeypatch.setattr(img2webhook, "CONFIG_FILE", tmp_path / "config.json")
