import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import img2ui


def test_check_docker_found():
    with patch("shutil.which", return_value="/usr/bin/docker"):
        assert img2ui.check_docker() is True


def test_check_docker_not_found():
    with patch("shutil.which", return_value=None):
        assert img2ui.check_docker() is False


def test_check_port_free_when_free():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.connect.side_effect = ConnectionRefusedError
    with patch("socket.socket", return_value=mock_sock):
        assert img2ui.check_port_free(8000) is True


def test_check_port_free_when_in_use():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.connect.return_value = None
    with patch("socket.socket", return_value=mock_sock):
        assert img2ui.check_port_free(8000) is False


def test_wait_for_server_success():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert img2ui.wait_for_server(timeout=5) is True


def test_wait_for_server_timeout():
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("err"),
    ):
        with patch("time.sleep"):
            result = img2ui.wait_for_server(timeout=1)
    assert result is False


def test_start_stack_calls_compose_up():
    with patch("subprocess.run") as mock_run:
        with patch.object(img2ui, "_ensure_compose_file"):
            img2ui.start_stack()
    args = mock_run.call_args[0][0]
    assert "docker" in args
    assert "compose" in args
    assert "up" in args
    assert "-d" in args


def test_stop_stack_calls_compose_down():
    with patch("subprocess.run") as mock_run:
        with patch.object(img2ui, "_ensure_compose_file"):
            img2ui.stop_stack()
    args = mock_run.call_args[0][0]
    assert "down" in args


def test_open_ui_no_session():
    with patch("webbrowser.open") as mock_open:
        img2ui.open_ui()
    mock_open.assert_called_once_with(img2ui.WEB_URL)


def test_open_ui_with_session_and_params():
    with patch("webbrowser.open") as mock_open:
        img2ui.open_ui(
            session_id="abc",
            params={"mode": "ascii", "contrast": "1.2"},
        )
    url = mock_open.call_args[0][0]
    assert "session=abc" in url
    assert "mode=ascii" in url
    assert "contrast=1.2" in url


def test_upload_file_returns_session_id(tmp_path):
    png = tmp_path / "test.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {"session_id": "test-uuid", "expires_in": 3600}
    ).encode()

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        session_id = img2ui.upload_file(str(png))

    assert session_id == "test-uuid"


def test_cmd_ui_stop():
    args = MagicMock()
    args.stop = True
    args.no_docker = False
    with patch.object(img2ui, "stop_stack") as mock_stop:
        img2ui.cmd_ui(args)
    mock_stop.assert_called_once()


def test_cmd_ui_exits_when_docker_missing():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=False):
        with pytest.raises(SystemExit):
            img2ui.cmd_ui(args)


def test_cmd_ui_exits_on_port_conflict():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=True):
        with patch.object(img2ui, "check_port_free", return_value=False):
            with pytest.raises(SystemExit):
                img2ui.cmd_ui(args)


def test_cmd_ui_full_happy_path():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=True), \
         patch.object(img2ui, "check_port_free", return_value=True), \
         patch.object(img2ui, "start_stack"), \
         patch.object(img2ui, "wait_for_server", return_value=True), \
         patch.object(img2ui, "open_ui") as mock_open:
        img2ui.cmd_ui(args)
    mock_open.assert_called_once_with()


def test_cmd_ui_with_file_happy_path(tmp_path):
    png = tmp_path / "img.png"
    png.write_bytes(b"data")
    with patch.object(img2ui, "check_docker", return_value=True), \
         patch.object(img2ui, "check_port_free", return_value=True), \
         patch.object(img2ui, "start_stack"), \
         patch.object(img2ui, "wait_for_server", return_value=True), \
         patch.object(img2ui, "upload_file", return_value="sess-xyz"), \
         patch.object(img2ui, "open_ui") as mock_open:
        img2ui.cmd_ui_with_file(str(png), "ascii", {"contrast": "1.2"})
    mock_open.assert_called_once_with(
        session_id="sess-xyz",
        params={"mode": "ascii", "contrast": "1.2"},
    )
