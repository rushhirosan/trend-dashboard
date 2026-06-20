"""Tests for utils.shutdown_errors."""

from utils.shutdown_errors import is_interpreter_shutdown_error


def test_is_interpreter_shutdown_error_matches():
    assert is_interpreter_shutdown_error(
        RuntimeError("cannot schedule new futures after interpreter shutdown")
    )
    assert is_interpreter_shutdown_error(
        RuntimeError("Cannot schedule new futures after shutdown")
    )


def test_is_interpreter_shutdown_error_other_runtime_error():
    assert not is_interpreter_shutdown_error(RuntimeError("something else"))


def test_is_interpreter_shutdown_error_non_runtime():
    assert not is_interpreter_shutdown_error(ValueError("interpreter shutdown"))
