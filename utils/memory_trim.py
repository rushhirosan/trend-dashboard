"""RSS 返却の補助（gc.collect 後に Linux で malloc_trim を試みる）。"""

import gc
import sys


def try_release_rss(*, collect: bool = True) -> bool:
    """
    解放済みヒープを OS に返す（Linux/glibc のみ best-effort）。
    Returns True if malloc_trim was invoked successfully.
    """
    if collect:
        gc.collect()
    if sys.platform != "linux":
        return False
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        return True
    except Exception:
        return False
