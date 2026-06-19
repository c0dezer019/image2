import img2log


def test_log_invocation_and_get_last_command():
    img2log.log_invocation(["img2", "ascii", "in.png"])
    img2log.log_invocation(["img2", "bug", "oops"])
    assert img2log.get_last_command() == "img2 ascii in.png"


def test_get_last_command_no_history():
    assert img2log.get_last_command() is None


def test_get_last_command_skips_feedback_too():
    img2log.log_invocation(["img2", "ansi", "in.png"])
    img2log.log_invocation(["img2", "feedback", "great tool"])
    assert img2log.get_last_command() == "img2 ansi in.png"


def test_read_log_tail_returns_last_n_lines(tmp_path):
    log = tmp_path / "custom.log"
    log.write_text("\n".join(f"line{i}" for i in range(10)))
    assert img2log.read_log_tail(3, log) == "line7\nline8\nline9"


def test_read_log_tail_missing_file(tmp_path):
    assert img2log.read_log_tail(10, tmp_path / "missing.log") == ""


def test_read_log_tail_default_path_uses_log_file():
    img2log.LOG_FILE.write_text("a\nb\nc\n")
    assert img2log.read_log_tail(2) == "b\nc"


def test_get_logger_writes_to_log_file():
    logger = img2log.get_logger()
    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()
    assert "hello" in img2log.LOG_FILE.read_text()
