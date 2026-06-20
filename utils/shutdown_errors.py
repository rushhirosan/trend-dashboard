"""Worker / interpreter 終了時に出やすい例外の判定。"""


def is_interpreter_shutdown_error(exc: BaseException) -> bool:
    """gunicorn ローリングデプロイや SIGTERM 中の ThreadPoolExecutor 失敗。"""
    if not isinstance(exc, RuntimeError):
        return False
    msg = str(exc).lower()
    return (
        "interpreter shutdown" in msg
        or "cannot schedule new futures" in msg
    )
